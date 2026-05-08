#!/usr/bin/env python3
"""
Unified cross-platform reset tool for Typeless device identifier.
Supports macOS and Windows.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import time

from crypto_utils import (
    DEVICE_CACHE_DIR,
    IS_MAC,
    IS_WIN,
    TYPELESS_DIR,
)


def log(msg):
    print(f"[reset-device] {msg}")


def kill_typeless():
    """Stop the Typeless application."""
    if IS_MAC:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "Typeless.app"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                log("Typeless is not running")
                return

            log("Stopping Typeless...")
            subprocess.run(
                ["osascript", "-e", 'quit app "Typeless"'],
                capture_output=True, timeout=5
            )
            # Wait for it to quit
            for _ in range(10):
                check = subprocess.run(
                    ["pgrep", "-f", "Typeless.app"],
                    capture_output=True, text=True
                )
                if check.returncode != 0:
                    log("Typeless stopped")
                    return
                time.sleep(0.5)

            # Force kill
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    os.kill(int(pid), signal.SIGKILL)
            log("Typeless force killed")
        except Exception as e:
            log(f"Warning during kill: {e}")
    elif IS_WIN:
        try:
            # Check if running
            check = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Typeless.exe"],
                capture_output=True, text=True
            )
            if "Typeless.exe" not in check.stdout:
                log("Typeless is not running")
                return

            log("Stopping Typeless...")
            subprocess.run(["taskkill", "/F", "/IM", "Typeless.exe", "/T"], capture_output=True)
            log("Typeless stopped")
        except Exception as e:
            log(f"Warning during kill: {e}")


def delete_file(path, description):
    if os.path.isfile(path):
        try:
            os.remove(path)
            log(f"Removed {description}")
        except Exception as e:
            log(f"Error removing {description}: {e}")
    else:
        log(f"{description} not found (already clean)")


def delete_dir(path, description):
    if os.path.isdir(path):
        try:
            shutil.rmtree(path)
            log(f"Cleared {description}")
        except Exception as e:
            log(f"Error clearing {description}: {e}")
    else:
        log(f"{description} not found (already clean)")


def main():
    log(f"Typeless device identifier reset tool ({sys.platform})")
    print("-" * 50)

    # 1. Kill Typeless
    kill_typeless()

    # 2. Delete device.cache
    delete_file(os.path.join(DEVICE_CACHE_DIR, "device.cache"), "device.cache (server-side UUID)")

    # 3. Delete Keychain (Mac only)
    if IS_MAC:
        try:
            res = subprocess.run(
                [
                    "security", "delete-generic-password",
                    "-s", "now.typeless.desktop.deviceIdentifier",
                    "-a", "now.typeless.desktop.security.auth_key"
                ],
                capture_output=True
            )
            if res.returncode == 0:
                log("Device identifier removed from Keychain")
            else:
                log("Device identifier not found in Keychain (already clean)")
        except Exception as e:
            log(f"Warning clearing Keychain: {e}")

    # 4. Delete user-data.json
    delete_file(os.path.join(TYPELESS_DIR, "user-data.json"), "user-data.json (encrypted login state)")

    # 5. Clear login state from app-storage.json
    storage_path = os.path.join(TYPELESS_DIR, "app-storage.json")
    if os.path.isfile(storage_path):
        try:
            with open(storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            modified = False
            if "userData" in data:
                del data["userData"]
                modified = True
            if "quotaUsage" in data:
                del data["quotaUsage"]
                modified = True
            
            if modified:
                with open(storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent="\t")
                log("Cleared login state from app-storage.json")
            else:
                log("app-storage.json already clean")
        except Exception as e:
            log(f"Could not clean app-storage.json: {e}")
    else:
        log("app-storage.json not found")

    # 6. Clear login session cookies
    for cookie_file in ["Cookies", "Cookies-journal"]:
        delete_file(os.path.join(TYPELESS_DIR, cookie_file), f"session cookie {cookie_file}")

    # 7. Clear frontend Local Storage
    delete_dir(os.path.join(TYPELESS_DIR, "Local Storage"), "Local Storage")

    # 8. Restart (optional)
    # On Windows, finding the exe path might be tricky if not in default Programs folder.
    # On Mac it's usually in /Applications.
    # We'll skip auto-restart for now to keep it safe, or just provide instructions.
    
    print("-" * 50)
    log("Done! Typeless will generate a new device identifier on next login.")
    log("You'll need to log in again in the Typeless app.")


if __name__ == "__main__":
    main()
