#!/usr/bin/env bash
#
# Reset Typeless device identifier on macOS.
# This makes Typeless treat the current machine as a new device,
# freeing up a device slot on your account.
#
# Usage:
#   bash reset-device-macos.sh
#
set -euo pipefail

echo "[reset-device] Typeless device identifier reset tool (macOS)"

TYPELESS_DIR="$HOME/Library/Application Support/Typeless"
DEVICE_CACHE_DIR="$HOME/Library/Application Support/now.typeless.desktop"

find_typeless_app() {
  if [ -n "${TYPELESS_APP_PATH:-}" ] && [ -d "$TYPELESS_APP_PATH" ]; then
    printf '%s\n' "$TYPELESS_APP_PATH"
    return 0
  fi

  local candidate
  for candidate in \
    "$HOME/Applications/Typeless.app" \
    "/Applications/Typeless.app"
  do
    if [ -d "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

TYPELESS_APP_PATH_FOUND="$(find_typeless_app || true)"

# 1. Kill Typeless if running
if pgrep -f "Typeless.app" > /dev/null 2>&1; then
  echo "[reset-device] Stopping Typeless..."
  osascript -e 'quit app "Typeless"' 2>/dev/null || true
  for i in $(seq 1 10); do
    pgrep -f "Typeless.app" > /dev/null 2>&1 || break
    sleep 0.5
  done
  echo "[reset-device] Typeless stopped"
else
  echo "[reset-device] Typeless is not running"
fi

# 2a. Delete device.cache (server-assigned device UUID)
if [ -f "$DEVICE_CACHE_DIR/device.cache" ]; then
  rm -f "$DEVICE_CACHE_DIR/device.cache"
  echo "[reset-device] Removed device.cache (server-side device UUID)"
else
  echo "[reset-device] device.cache not found (already clean)"
fi

# 2b. Delete device identifier from Keychain
if security delete-generic-password \
  -s "now.typeless.desktop.deviceIdentifier" \
  -a "now.typeless.desktop.security.auth_key" 2>/dev/null; then
  echo "[reset-device] Device identifier removed from Keychain"
else
  echo "[reset-device] Device identifier not found in Keychain (already clean)"
fi

# 3. Delete user-data.json (encrypted login state)
if [ -f "$TYPELESS_DIR/user-data.json" ]; then
  rm -f "$TYPELESS_DIR/user-data.json"
  echo "[reset-device] Removed user-data.json"
else
  echo "[reset-device] user-data.json not found (already clean)"
fi

# 4. Clear login state from app-storage.json (keep other settings)
if [ -f "$TYPELESS_DIR/app-storage.json" ]; then
  node -e "
    const fs = require('fs');
    try {
      const data = JSON.parse(fs.readFileSync('$TYPELESS_DIR/app-storage.json', 'utf8'));
      delete data.userData;
      delete data.quotaUsage;
      fs.writeFileSync('$TYPELESS_DIR/app-storage.json', JSON.stringify(data, null, '\t'));
      console.log('[reset-device] Cleared login state from app-storage.json');
    } catch(e) {
      console.log('[reset-device] Could not clean app-storage.json: ' + e.message);
    }
  "
else
  echo "[reset-device] app-storage.json not found"
fi

# 5. Clear login session cookies
for cookie_file in "$TYPELESS_DIR/Cookies" "$TYPELESS_DIR/Cookies-journal"; do
  if [ -f "$cookie_file" ]; then
    rm -f "$cookie_file"
    echo "[reset-device] Removed $(basename "$cookie_file")"
  fi
done

# 6. Clear frontend Local Storage (in-app session tokens)
if [ -d "$TYPELESS_DIR/Local Storage" ]; then
  rm -rf "$TYPELESS_DIR/Local Storage"
  echo "[reset-device] Cleared Local Storage"
else
  echo "[reset-device] Local Storage not found (already clean)"
fi

# 7. Restart Typeless
if [ -n "$TYPELESS_APP_PATH_FOUND" ]; then
  echo "[reset-device] Starting Typeless..."
  open "$TYPELESS_APP_PATH_FOUND"
  echo "[reset-device] Typeless started"
else
  echo "[reset-device] Typeless.app not found in ~/Applications or /Applications, please start it manually"
fi

echo ""
echo "[reset-device] Done! Typeless will generate a new device identifier on next login."
echo "[reset-device] You'll need to log in again in the Typeless app."
