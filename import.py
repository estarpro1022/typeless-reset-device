#!/usr/bin/env python3
"""
Import Typeless data into a new account.

Usage:
    uv run python3 import.py <backup_dir>

Imports:
    - Dictionary words (cloud API)
    - Migrates history records to new user_id (SQLite)
    - Copies recordings if not already present
"""

import argparse
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

import requests

from crypto_utils import (
    API_BASE,
    TYPELESS_DIR,
    build_security_headers,
    decrypt_user_data,
    get_device_id,
)


def get_proxy():
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return {"https": proxy} if proxy else None


def kill_typeless():
    """Ensure Typeless is not running before modifying local data."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "Typeless.app"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("[kill] Typeless is not running")
            return

        print("[kill] Stopping Typeless...")
        subprocess.run(
            ["osascript", "-e", 'quit app "Typeless"'],
            capture_output=True, timeout=5
        )
        # Wait for it to actually quit
        for _ in range(10):
            check = subprocess.run(
                ["pgrep", "-f", "Typeless.app"],
                capture_output=True, text=True
            )
            if check.returncode != 0:
                print("[kill] Typeless stopped")
                return
            time.sleep(0.5)

        # Force kill if still running
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid:
                os.kill(int(pid), signal.SIGKILL)
        print("[kill] Typeless force killed")
    except Exception as e:
        print(f"[kill] Warning: {e}")


def import_dictionary(backup_dir):
    """Import dictionary words from backup into the current account via API."""
    dict_path = os.path.join(backup_dir, "dictionary_backup.json")
    if not os.path.isfile(dict_path):
        print("[dict] No dictionary_backup.json found, skipping.")
        return

    with open(dict_path) as f:
        backup = json.load(f)

    words = backup.get("data", {}).get("words", [])
    if not words:
        print("[dict] No words in backup, skipping.")
        return

    user = decrypt_user_data()
    token = user["refresh_token"]
    user_id = user["user_id"]
    device_id = get_device_id()
    proxy = get_proxy()

    old_user_id = backup.get("backup_user_id")
    print(f"[dict] Target account: {user['email']}")
    print(f"[dict] Words to import: {len(words)}")
    if old_user_id and old_user_id == user_id:
        print("[dict] Warning: backup and current account have the same user_id.")

    success = 0
    skipped = 0
    failed = []

    for i, word in enumerate(words, 1):
        term = word.get("term", "").strip()
        if not term:
            skipped += 1
            continue

        headers = build_security_headers("/user/dictionary/add", user_id, token, device_id)
        body = {"term": term}
        if "lang" in word:
            body["lang"] = word["lang"]
        if "category" in word:
            body["category"] = word["category"]

        try:
            resp = requests.post(
                f"{API_BASE}/user/dictionary/add",
                json=body,
                headers=headers,
                proxies=proxy,
                timeout=15,
            )
            if resp.json().get("status") == "OK":
                success += 1
                if success % 20 == 0:
                    print(f"[dict]   {success}/{len(words)} imported...")
            else:
                failed.append(term)
                print(f"[dict]   x {term}: {resp.text[:80]}")
        except Exception as e:
            failed.append(term)
            print(f"[dict]   x {term}: {e}")

        time.sleep(0.15)

    print(f"[dict] Imported {success}/{len(words)} words")
    if failed:
        print(f"[dict] Failed ({len(failed)}): {failed[:5]}{'...' if len(failed) > 5 else ''}")


def migrate_database(backup_dir):
    """Migrate history records from old user_id to new user_id in typeless.db.

    Handles both 'history' and 'history_v2' tables (v1.8.0 added history_v2).
    """
    meta_path = os.path.join(backup_dir, "export_meta.json")
    old_user_id = None
    if os.path.isfile(meta_path):
        with open(meta_path) as f:
            old_user_id = json.load(f).get("user_id")

    db_path = os.path.join(TYPELESS_DIR, "typeless.db")
    if not os.path.isfile(db_path):
        print("[db] typeless.db not found, skipping.")
        return

    # Get new user_id from the logged-in account (not from history table)
    user = decrypt_user_data()
    new_user_id = user.get("user_id")

    if not new_user_id:
        print("[db] Could not get new user_id, skipping.")
        return

    if not old_user_id:
        # Try to find it in the backup database
        backup_db = os.path.join(backup_dir, "typeless.db")
        if os.path.isfile(backup_db):
            bconn = sqlite3.connect(backup_db)
            for table in ("history", "history_v2"):
                bcur = bconn.execute(
                    f"SELECT DISTINCT user_id FROM {table} WHERE user_id IS NOT NULL LIMIT 1"
                )
                brow = bcur.fetchone()
                if brow:
                    old_user_id = brow[0]
                    break
            bconn.close()

    if not old_user_id:
        print("[db] Could not determine old user_id, skipping migration.")
        return

    conn = sqlite3.connect(db_path)

    if old_user_id == new_user_id:
        print(f"[db] Already on the same user_id ({new_user_id}), nothing to migrate.")
        conn.close()
        return

    # Migrate all history tables that exist in the current DB
    migrated = 0
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('history', 'history_v2')"
    )
    tables = [row[0] for row in cur.fetchall()]

    for table in tables:
        cur = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (old_user_id,)
        )
        count = cur.fetchone()[0]
        if count == 0:
            print(f"[db] No records in {table} with old user_id, skipping.")
            continue

        conn.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id = ?",
            (new_user_id, old_user_id),
        )
        conn.commit()
        migrated += count
        print(f"[db] Migrated {count} records in {table}: {old_user_id} → {new_user_id}")

    if migrated == 0:
        print("[db] No records to migrate.")
    else:
        print(f"[db] Total migrated: {migrated} history records")

    conn.close()


def restore_recordings(backup_dir):
    """Copy recordings from backup if the target dir is empty or missing."""
    src = os.path.join(backup_dir, "Recordings")
    if not os.path.isdir(src):
        print("[rec] No recordings in backup, skipping.")
        return

    dst = os.path.join(TYPELESS_DIR, "Recordings")
    existing = len([f for f in os.listdir(dst) if f.endswith(".ogg")]) if os.path.isdir(dst) else 0

    if existing > 0:
        # Only copy missing files
        copied = 0
        for f in os.listdir(src):
            src_file = os.path.join(src, f)
            dst_file = os.path.join(dst, f)
            if f.endswith(".ogg") and not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)
                copied += 1
        if copied > 0:
            print(f"[rec] Copied {copied} missing .ogg files (already had {existing})")
        else:
            print(f"[rec] All {existing} recordings already present, skipping.")
    else:
        shutil.copytree(src, dst, dirs_exist_ok=True)
        ogg_count = len([f for f in os.listdir(dst) if f.endswith(".ogg")])
        print(f"[rec] Copied {ogg_count} .ogg files")


def main():
    parser = argparse.ArgumentParser(description="Import Typeless data into current account")
    parser.add_argument("backup_dir", help="Path to the backup directory")
    parser.add_argument("--dict-only", action="store_true", help="Only import dictionary")
    parser.add_argument("--db-only", action="store_true", help="Only migrate database")
    args = parser.parse_args()

    backup_dir = args.backup_dir
    if not os.path.isdir(backup_dir):
        print(f"Error: {backup_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    kill_typeless()

    print(f"Importing from {backup_dir}/")
    print()

    if args.db_only:
        migrate_database(backup_dir)
        return

    if args.dict_only:
        import_dictionary(backup_dir)
        return

    # Full import
    import_dictionary(backup_dir)
    print()

    migrate_database(backup_dir)
    print()

    restore_recordings(backup_dir)
    print()

    # Verify
    user = decrypt_user_data()
    db_path = os.path.join(TYPELESS_DIR, "typeless.db")
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT COUNT(*) FROM history")
    total = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM history_v2")
    total_v2 = cur.fetchone()[0]
    conn.close()
    print(f"Done! Account: {user['email']}, History: {total} (v1), {total_v2} (v2)")


if __name__ == "__main__":
    main()
