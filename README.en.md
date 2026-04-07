# typeless-reset-device

**Reset the Typeless device identifier with one command**

[中文](README.md) | English

---

## Background

New Typeless accounts come with a one-month free Pro trial. After logging into multiple accounts on the same machine, you may see:

```
The number of users logged into this device has exceeded the limit.
```

This happens because Typeless sends a **Device ID** with every server request. The server uses this fingerprint to enforce a per-device account cap.

## How it works (reverse-engineered)

The Device ID comes from a native library (`libUtilHelper.dylib` on macOS) and is resolved in this order:

```
1. Read from Keychain (macOS) / Credential Manager (Windows)
   └─ found → use it
   └─ not found ↓
2. Read from local cache file
   └─ found → use it, sync back to Keychain
   └─ not found ↓
3. Generate a new UUID
   └─ write to Keychain + local cache
```

Device ID storage locations:

| Platform | Store | Location |
|----------|-------|----------|
| macOS | Keychain | service: `now.typeless.desktop` · account: `.deviceIdentifier` |
| macOS | Local cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |
| Windows | Credential Manager | `Typeless.deviceIdentifier` |
| Windows | Local cache | `%APPDATA%\Typeless\Cache\device.cache` |

Wipe both locations and Typeless generates a brand-new Device ID on the next launch — the server sees a fresh machine.

## Usage

**macOS**

```bash
bash reset-device-macos.sh
```

> If Typeless is installed in a non-default location, set the path override:
> ```bash
> TYPELESS_APP_PATH=/path/to/Typeless.app bash reset-device-macos.sh
> ```

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File reset-device-windows.ps1
```

## What the script does

| Step | Action |
|------|--------|
| 1 | Force-quit Typeless |
| 2 | Delete `device.cache` (server-assigned device UUID) |
| 3 | Remove the Keychain / Credential Manager entry |
| 4 | Delete `user-data.json` (encrypted login state) |
| 5 | Clear `userData` / `quotaUsage` from `app-storage.json` |
| 6 | Wipe login cookies and Local Storage (macOS only) |
| 7 | Relaunch Typeless → fresh Device ID generated on startup |

You will need to log back into your Typeless account after running the script.

## File structure

```
├── README.md                   # Chinese README
├── README.en.md                # English README
├── reset-device-macos.sh       # macOS reset script (bash)
└── reset-device-windows.ps1    # Windows reset script (PowerShell)
```

## License

MIT
