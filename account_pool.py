#!/usr/bin/env python3
"""
Typeless Account Pool Manager — CTF Edition.

Manages multiple free Typeless accounts (8000 words/week each) and
routes API requests through the account with the most remaining quota.

Usage:
    # Extract current session credentials into the pool
    uv run python3 account_pool.py extract --alias slot1

    # List all accounts and their quota status
    uv run python3 account_pool.py status

    # Refresh quota for all accounts
    uv run python3 account_pool.py refresh

    # Make a request through the pool
    uv run python3 account_pool.py request --path /user/dictionary/add --data '{"term":"test"}'
"""

import argparse
import json
import os
import random
import shutil
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from curl_cffi import requests as requests

from crypto_utils import (
    API_BASE,
    build_security_headers,
    decrypt_user_data,
    get_device_id,
)

POOL_DIR = Path.home() / ".typeless-pool"
POOL_CONFIG = POOL_DIR / "pool.json"
HISTORY_DIR = POOL_DIR / "history"
MASTER_DICT = POOL_DIR / "dictionary.json"
BACKUP_DIR = POOL_DIR / "backups"


@dataclass
class AccountSlot:
    """One account in the pool."""
    alias: str                          # Human-readable label (e.g., "slot1")
    email: str                          # Login email
    user_id: str                        # UUID
    refresh_token: str                  # JWT Bearer token
    device_id: str                      # Device UUID (can be shared or unique)
    quota_limit: int = 8000             # Weekly word limit
    quota_used: int = 0                 # Current weekly usage
    quota_updated_at: float = 0.0       # Last quota check timestamp
    login_time: float = 0.0             # When the account was logged in
    created_at: float = field(default_factory=time.time)


class AccountPool:
    """Manages a pool of Typeless accounts for quota rotation."""

    def __init__(self):
        self.accounts: dict[str, AccountSlot] = {}
        self._lock = threading.Lock()
        self._ensure_dirs()
        self._load()

    def _ensure_dirs(self):
        POOL_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if POOL_CONFIG.exists():
            data = json.loads(POOL_CONFIG.read_text())
            for alias, slot_data in data.get("accounts", {}).items():
                self.accounts[alias] = AccountSlot(**slot_data)

    def _save(self):
        with self._lock:
            data = {
                "version": 1,
                "updated_at": time.time(),
                "accounts": {
                    alias: asdict(slot) for alias, slot in self.accounts.items()
                },
            }
            POOL_CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ── Account management ──────────────────────────────────────────

    def extract_current(self, alias: str) -> AccountSlot:
        """Extract credentials from the currently logged-in Typeless session."""
        user = decrypt_user_data()
        device_id = get_device_id()

        slot = AccountSlot(
            alias=alias,
            email=user["email"],
            user_id=user["user_id"],
            refresh_token=user["refresh_token"],
            device_id=device_id,
            login_time=user.get("login_time", time.time() * 1000) / 1000,
        )

        # Refresh quota immediately
        self._refresh_quota(slot)

        self.accounts[alias] = slot
        self._save()

        # Backup the raw credential files
        self._backup_session(alias)
        return slot

    def _backup_session(self, alias: str):
        """Save raw session files for this account slot."""
        slot_dir = BACKUP_DIR / alias
        slot_dir.mkdir(parents=True, exist_ok=True)

        src_dir = Path.home() / "Library/Application Support/Typeless"
        for fname in ["user-data.json"]:
            src = src_dir / fname
            if src.exists():
                shutil.copy2(src, slot_dir / fname)

        cache = Path.home() / "Library/Application Support/now.typeless.desktop/device.cache"
        if cache.exists():
            shutil.copy2(cache, slot_dir / "device.cache")

    @staticmethod
    def skip_onboarding():
        """Patch app-onboarding.json to skip the setup/tutorial flow."""
        path = Path.home() / "Library/Application Support/Typeless/app-onboarding.json"
        if not path.exists():
            print("  app-onboarding.json not found, skipping.")
            return

        import json as _json
        with open(path) as f:
            data = _json.load(f)

        changed = False
        for key, val in [
            ("isCompleted", True),
            ("setUpStep", 999),
            ("step", 999),
            ("tryItStep", 999),
            ("tryItPlaygroundStep", 999),
            ("onboardingMaxReachedStep", "done"),
            ("onboardingStep", "done"),
        ]:
            if data.get(key) != val:
                data[key] = val
                changed = True

        if changed:
            with open(path, "w") as f:
                _json.dump(data, f, indent=2)
            print("  ✓ Onboarding skipped")
        else:
            print("  (onboarding already skipped)")

    def restore(self, alias: str):
        """Restore a saved session to the live Typeless app directory.

        Copies backed-up user-data.json and device.cache so Typeless
        opens as this account on next launch.
        """
        slot_dir = BACKUP_DIR / alias
        if not slot_dir.exists():
            raise FileNotFoundError(f"No backup for '{alias}' at {slot_dir}")

        # Kill Typeless first
        import subprocess, signal
        try:
            result = subprocess.run(
                ["pgrep", "-f", "Typeless.app"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  Stopping Typeless...")
                subprocess.run(["osascript", "-e", 'quit app "Typeless"'], capture_output=True, timeout=5)
                time.sleep(1)
                for pid in result.stdout.strip().split("\n"):
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except:
                        pass
        except Exception:
            pass

        # Restore user-data.json
        src_userdata = slot_dir / "user-data.json"
        dst_userdata = Path.home() / "Library/Application Support/Typeless/user-data.json"
        if src_userdata.exists():
            dst_userdata.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_userdata, dst_userdata)
            print(f"  ✓ Restored user-data.json for '{alias}'")

        # Restore device.cache
        src_cache = slot_dir / "device.cache"
        dst_cache = Path.home() / "Library/Application Support/now.typeless.desktop/device.cache"
        if src_cache.exists():
            dst_cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_cache, dst_cache)
            print(f"  ✓ Restored device.cache for '{alias}'")

        print(f"  → Launching Typeless as {self.accounts[alias].email}")
        subprocess.run(["open", "-a", "Typeless"], capture_output=True)
        print(f"  ✓ Typeless launched")

        # Auto-sync dictionaries in background
        if len(self.accounts) >= 2:
            from_alias = self._detect_current_alias()
            to_alias = alias
            if from_alias and from_alias != to_alias:
                threading.Thread(
                    target=self._auto_sync, args=(from_alias, to_alias), daemon=True
                ).start()

    def _auto_sync(self, from_alias: str, to_alias: str):
        """Background dict sync: pull from source, push to target only."""
        try:
            time.sleep(3)  # let Typeless finish launching
            result = self.sync_on_switch(from_alias, to_alias)
            imported = result.get("imported", {})
            for a, n in imported.items():
                print(f"  [dict] {a}: +{n} words synced")
        except Exception:
            pass

    def remove(self, alias: str):
        """Remove an account from the pool."""
        self.accounts.pop(alias, None)
        # Also remove backup
        slot_dir = BACKUP_DIR / alias
        if slot_dir.exists():
            shutil.rmtree(slot_dir)
        self._save()

    # ── Dictionary sync ─────────────────────────────────────────────

    def _load_master_dict(self) -> dict:
        """Load global dict: {"words": [...], "synced": {"slot1": [...], ...}}."""
        if MASTER_DICT.exists():
            return json.loads(MASTER_DICT.read_text())
        return {"words": [], "synced": {}}

    def _save_master_dict(self, data: dict):
        data["words"] = sorted(data["words"])
        MASTER_DICT.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _fetch_dict_terms(self, slot: AccountSlot) -> set[str]:
        """Fetch all dictionary terms for a slot via API."""
        terms = set()
        offset = 0
        page_size = 200
        while True:
            result = self.request(
                f"/user/dictionary/list?size={page_size}&offset={offset}",
                method="GET",
                slot=slot,
                use_stored_device=True,
            )
            if not result["success"]:
                raise RuntimeError(f"Fetch dict failed: {result.get('error')}")
            data = result["data"]
            words = data.get("data", {}).get("words", [])
            total = data.get("data", {}).get("total_count", 0)
            for w in words:
                if w.get("term"):
                    terms.add(w["term"])
            if len(terms) >= total or len(words) == 0:
                break
            offset += page_size
        return terms

    def _add_dict_terms(self, slot: AccountSlot, terms: set[str]):
        """Add dictionary terms to a slot via API."""
        count = 0
        for term in sorted(terms):
            result = self.request(
                "/user/dictionary/add",
                data={"term": term},
                slot=slot,
                use_stored_device=True,
            )
            if result["success"]:
                count += 1
            time.sleep(0.12)
        return count

    def _detect_current_alias(self) -> str | None:
        """Return the alias of the currently active account, if it's in the pool."""
        try:
            cur = decrypt_user_data()
            cur_id = cur.get("user_id")
            for alias, s in self.accounts.items():
                if s.user_id == cur_id:
                    return alias
        except Exception:
            pass
        return None

    def sync_on_switch(self, from_alias: str, to_alias: str) -> dict:
        """Sync dict when switching accounts: pull from source, push to target.

        Only queries the two relevant accounts — the rest are untouched.
        """
        if from_alias == to_alias:
            return {"master_total": 0, "imported": {from_alias: 0}}

        master = self._load_master_dict()
        synced = master.setdefault("synced", {})

        # Step 1: pull latest from the account we're leaving
        from_slot = self.accounts.get(from_alias)
        if from_slot:
            try:
                fresh = self._fetch_dict_terms(from_slot)
                synced[from_alias] = sorted(fresh)
                for w in fresh:
                    if w not in master["words"]:
                        master["words"].append(w)
                self._save_master_dict(master)
            except Exception as e:
                print(f"  [!] Dict pull from {from_alias} failed: {e}")

        # Step 2: push missing to the account we're switching to
        to_slot = self.accounts.get(to_alias)
        if to_slot:
            try:
                existing = set(synced.get(to_alias, []))
                all_words = set(master["words"])
                missing = all_words - existing
                if missing:
                    n = self._add_dict_terms(to_slot, missing)
                    synced[to_alias] = sorted(existing | missing)
                    self._save_master_dict(master)
                else:
                    n = 0
                return {"master_total": len(master["words"]), "imported": {to_alias: n}}
            except Exception as e:
                return {"master_total": len(master["words"]), "imported": {to_alias: f"FAILED: {e}"}}

        return {"master_total": len(master["words"]), "imported": {}}

    def sync_all_dicts(self) -> dict:
        """Full sync: pull all accounts, merge to master, push to all.  Use
        for initial sync or recovery — sync_on_switch is the daily driver."""
        if len(self.accounts) < 2:
            return {"error": "Need at least 2 slots to sync"}

        master = self._load_master_dict()
        synced = master.setdefault("synced", {})

        # Pull from all slots, merge into master
        for alias, slot in self.accounts.items():
            try:
                terms = self._fetch_dict_terms(slot)
                synced[alias] = sorted(terms)
                for w in terms:
                    if w not in master["words"]:
                        master["words"].append(w)
            except Exception as e:
                print(f"  [!] Dict pull from {alias} failed: {e}")
        self._save_master_dict(master)

        # Push missing to each slot
        all_words = set(master["words"])
        results = {}
        for alias, slot in self.accounts.items():
            existing = set(synced.get(alias, []))
            missing = all_words - existing
            if missing:
                try:
                    n = self._add_dict_terms(slot, missing)
                    synced[alias] = sorted(existing | missing)
                    results[alias] = n
                except Exception as e:
                    results[alias] = f"FAILED: {e}"
            else:
                results[alias] = 0
        self._save_master_dict(master)

        return {"master_total": len(master["words"]), "imported": results}

    # ── Quota management ────────────────────────────────────────────

    def _refresh_quota(self, slot: AccountSlot) -> bool:
        """Query usage_stats API for one account. Returns True on success."""
        try:
            temp_device_id = str(uuid.uuid4())
            headers = build_security_headers(
                "/user/usage_stats", slot.user_id, slot.refresh_token, temp_device_id
            )
            resp = requests.post(
                f"{API_BASE}/user/usage_stats",
                json={},
                headers=headers,
                timeout=15,
                impersonate="chrome124",
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get("voice_transcription", {})
                slot.quota_limit = data.get("week_word_usage_limit", 8000)
                slot.quota_used = data.get("week_word_usage_value", 0)
                slot.quota_updated_at = time.time()
                self._save()
                self._record_usage(slot.alias, slot.quota_used)
                return True
        except Exception as e:
            print(f"  [!] Quota refresh failed for {slot.alias}: {e}")
        return False

    # ── Usage history ─────────────────────────────────────────────

    @staticmethod
    def _history_file(year: str) -> Path:
        """Path to a yearly history shard, e.g. history/2026.json."""
        return HISTORY_DIR / f"{year}.json"

    @staticmethod
    def _load_history(year: str = None) -> dict:
        """Load snapshots from a yearly shard (default: current year)."""
        if year is None:
            year = time.strftime("%Y")
        path = AccountPool._history_file(year)
        if path.exists():
            return json.loads(path.read_text())
        return {"snapshots": []}

    @staticmethod
    def _save_history(history: dict, year: str = None):
        """Save snapshots to the current year's shard."""
        if year is None:
            year = time.strftime("%Y")
        AccountPool._history_file(year).write_text(
            json.dumps(history, indent=2, ensure_ascii=False)
        )

    def _record_usage(self, alias: str, quota_used: int):
        """Record the latest usage snapshot for today."""
        today = time.strftime("%Y-%m-%d")
        recorded_at = time.time()
        with self._lock:
            history = self._load_history()
            for entry in history["snapshots"]:
                if entry["date"] == today and entry["alias"] == alias:
                    entry["quota_used"] = quota_used
                    entry["recorded_at"] = recorded_at
                    break
            else:
                history["snapshots"].append({
                    "date": today,
                    "alias": alias,
                    "quota_used": quota_used,
                    "recorded_at": recorded_at,
                })
            self._save_history(history)

    def get_history(self, week_offset: int = 0) -> dict:
        """Return cumulative daily total for a given week (Mon → Sun).

        week_offset=0 is the current week, -1 is last week, +1 is next week.
        Each data point is total quota_used across all accounts for that day.
        """
        from datetime import date, timedelta

        today = date.today()
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        sunday = monday + timedelta(days=6)

        # Load year shards that overlap this week
        years = set()
        d = monday
        while d <= sunday:
            years.add(str(d.year))
            d += timedelta(days=1)

        snapshots = []
        for y in years:
            snapshots.extend(self._load_history(y).get("snapshots", []))

        # Per date, per account: latest quota_used. The weekly API counter can
        # decrease at reset time, so using max would pin Monday to Sunday's value.
        daily_per_account = {}
        for seq, entry in enumerate(snapshots):
            date = entry["date"]
            alias = entry["alias"]
            if date not in daily_per_account:
                daily_per_account[date] = {}
            current = daily_per_account[date].get(alias)
            entry_key = (entry.get("recorded_at", 0), seq)
            if current is None or entry_key >= current["key"]:
                daily_per_account[date][alias] = {
                    "quota_used": entry["quota_used"],
                    "key": entry_key,
                }

        WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        labels = []
        totals = []
        d = monday
        for i in range(7):
            date_str = d.strftime("%Y-%m-%d")
            labels.append(f"{d.strftime('%m-%d')} {WEEKDAY_ZH[i]}")
            if date_str in daily_per_account and d <= today:
                totals.append(
                    sum(entry["quota_used"] for entry in daily_per_account[date_str].values())
                )
            elif d <= today:
                totals.append(0)
            else:
                totals.append(None)  # future day, gap in chart
            d += timedelta(days=1)

        return {
            "labels": labels,
            "data": totals,
            "week_start": monday.strftime("%m-%d"),
            "week_end": sunday.strftime("%m-%d"),
            "has_prev": True,   # can always go back
            "has_next": week_offset < 0,
        }

    # ── Quota management (continued) ────────────────────────────────

    def refresh_all(self):
        """Refresh quota for all accounts in the pool."""
        print("Refreshing quotas...")
        for alias, slot in self.accounts.items():
            if self._refresh_quota(slot):
                remaining = slot.quota_limit - slot.quota_used
                print(f"  [{alias}] {slot.email}: {slot.quota_used}/{slot.quota_limit} ({remaining} remaining)")
            else:
                print(f"  [{alias}] {slot.email}: FAILED (token may be expired)")

    # ── Account selection ───────────────────────────────────────────

    def get_active(self) -> Optional[AccountSlot]:
        """Return the current sticky account, or pick the first one with quota.

        Uses a sticky strategy: keep using the same account until its quota
        drops below the threshold, then auto-switch to the next.
        """
        if not self.accounts:
            return None

        # Check if there's a sticky current account with quota left
        # The active account is the first one in insertion order that has quota
        for slot in self.accounts.values():
            if slot.quota_limit - slot.quota_used > 0:
                return slot
        return None

    def get_all_with_quota(self, min_words: int = 100) -> list[AccountSlot]:
        """Return all accounts with at least min_words remaining."""
        result = []
        for slot in self.accounts.values():
            if slot.quota_limit - slot.quota_used >= min_words:
                result.append(slot)
        return sorted(result, key=lambda s: s.quota_limit - s.quota_used, reverse=True)

    # ── API proxy ───────────────────────────────────────────────────

    def request(self, path: str, data: dict = None,
                method: str = "POST", slot: AccountSlot = None,
                timeout: int = 30, use_stored_device: bool = False) -> dict:
        """Make an API request through a pool account.

        Args:
            path: API path (e.g., "/user/usage_stats")
            data: JSON body
            method: HTTP method
            slot: Specific account to use (auto-selects best if None)
            timeout: Request timeout in seconds
            use_stored_device: Use slot's original device_id instead of random

        Returns:
            {"success": True, "status": 200, "data": {...}, "slot_alias": "..."}
        """
        if slot is None:
            slot = self.get_active()
            if slot is None:
                return {"success": False, "error": "No accounts with quota remaining"}

        device_id = slot.device_id if use_stored_device else str(uuid.uuid4())
        sign_path = path.split("?")[0]  # signature must NOT include query string
        headers = build_security_headers(
            sign_path, slot.user_id, slot.refresh_token, device_id
        )

        try:
            if method == "POST":
                resp = requests.post(
                    f"{API_BASE}{path}",
                    json=data or {},
                    headers=headers,
                    timeout=timeout,
                    impersonate="chrome124",
                )
            elif method == "GET":
                resp = requests.get(
                    f"{API_BASE}{path}",
                    headers=headers,
                    timeout=timeout,
                    impersonate="chrome124",
                )
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            success = resp.status_code < 400
            result = {
                "success": success,
                "status": resp.status_code,
                "data": resp.json() if resp.text else None,
                "slot_alias": slot.alias,
            }
            if not success:
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "slot_alias": slot.alias}

    # ── Display ──────────────────────────────────────────────────────

    def status(self):
        """Print pool status table."""
        if not self.accounts:
            print("Pool is empty. Use 'extract' to add the current session.")
            return

        print(f"{'Alias':<12} {'Email':<30} {'Quota Used':>10} {'Limit':>8} {'Remain':>8} {'Usage%':>7}")
        print("-" * 82)
        total_remaining = 0
        for alias, slot in sorted(self.accounts.items()):
            remaining = slot.quota_limit - slot.quota_used
            pct = (slot.quota_used / slot.quota_limit * 100) if slot.quota_limit else 0
            total_remaining += remaining
            bar = _quota_bar(slot.quota_used, slot.quota_limit)
            print(f"{alias:<12} {slot.email:<30} {slot.quota_used:>6}w   {slot.quota_limit:>5}w  {remaining:>5}w  {pct:>5.0f}%  {bar}")
        print("-" * 82)
        print(f"Pool total: {len(self.accounts)} accounts, {total_remaining} words remaining")


def _quota_bar(used: int, limit: int, width: int = 10) -> str:
    """Simple ASCII quota bar."""
    if limit == 0:
        return "[----------]"
    ratio = used / limit
    filled = round(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Typeless Account Pool Manager")
    sub = parser.add_subparsers(dest="command")

    # extract
    p = sub.add_parser("extract", help="Save current Typeless session to pool")
    p.add_argument("--alias", "-a", required=True, help="Slot name (e.g., slot1)")

    # status
    sub.add_parser("status", help="Show pool status and quotas")

    # refresh
    sub.add_parser("refresh", help="Refresh quotas for all accounts")

    # request
    p = sub.add_parser("request", help="Make API request through pool")
    p.add_argument("--path", "-p", required=True, help="API path")
    p.add_argument("--data", "-d", default="{}", help="JSON body")
    p.add_argument("--slot", "-s", help="Specific slot (default: auto-select best)")
    p.add_argument("--method", "-m", default="POST", help="HTTP method")

    # remove
    p = sub.add_parser("remove", help="Remove account from pool")
    p.add_argument("--alias", "-a", required=True)

    # restore
    p = sub.add_parser("restore", help="Restore backed-up session to live Typeless app")
    p.add_argument("--alias", "-a", required=True, help="Slot to restore")

    # sync-dict
    sub.add_parser("sync-dict", help="Merge dictionary words across all pool accounts")

    # skip-onboarding
    sub.add_parser("skip-onboarding", help="Patch onboarding flags to skip setup tutorial")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    pool = AccountPool()

    if args.command == "extract":
        print(f"Extracting current session as '{args.alias}'...")
        slot = pool.extract_current(args.alias)
        remaining = slot.quota_limit - slot.quota_used
        print(f"  ✓ {slot.email}")
        print(f"  ✓ Quota: {slot.quota_used}/{slot.quota_limit} ({remaining} remaining)")
        print(f"  ✓ Backed up to {BACKUP_DIR / args.alias}/")
        print()
        print(f"Now log out and log in with the NEXT account, then run:")
        print(f"  uv run python3 account_pool.py extract --alias slot2")

    elif args.command == "status":
        pool.status()

    elif args.command == "refresh":
        pool.refresh_all()

    elif args.command == "request":
        slot = None
        if args.slot:
            slot = pool.accounts.get(args.slot)
            if slot is None:
                print(f"Error: slot '{args.slot}' not found", file=sys.stderr)
                sys.exit(1)

        data = json.loads(args.data)
        result = pool.request(args.path, data, method=args.method, slot=slot)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "remove":
        pool.remove(args.alias)
        print(f"Removed '{args.alias}' from pool.")

    elif args.command == "restore":
        pool.restore(args.alias)

    elif args.command == "sync-dict":
        print("Syncing dictionaries across all slots...")
        results = pool.sync_all_dicts()
        if "error" in results:
            print(f"  {results['error']}")
        else:
            print(f"  Master total: {results['master_total']} words")
            total_imported = 0
            for alias, n in results["imported"].items():
                if isinstance(n, int):
                    print(f"  [{alias}] {n} new words imported")
                    total_imported += n
                else:
                    print(f"  [{alias}] {n}")
            print(f"  Total imported: {total_imported}")

    elif args.command == "skip-onboarding":
        AccountPool.skip_onboarding()


if __name__ == "__main__":
    main()
