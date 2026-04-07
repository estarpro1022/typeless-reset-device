# typeless-reset-device

**Reset the Typeless macOS device identifier with one command**

[中文](README.md) | English

---

## Background

> Only the macOS script has been verified with Typeless v1.1.0. The Windows version has been removed, and other Typeless versions are not guaranteed to work correctly.

New Typeless accounts come with a one-month free Pro trial. After logging into multiple accounts on the same machine, you may see:

```
The number of users logged into this device has exceeded the limit.
```

This happens because Typeless sends a **Device ID** with every server request. The server uses this fingerprint to enforce a per-device account cap.

## How it works (reverse-engineered)

The Device ID comes from the macOS native library `libUtilHelper.dylib` and is resolved in this order:

```
1. Read from Keychain
   └─ found → use it
   └─ not found ↓
2. Read from local cache file
   └─ found → use it, sync back to Keychain
   └─ not found ↓
3. Generate a new UUID
   └─ write to Keychain + local cache
```

Device ID storage locations on macOS:

| Store | Location |
|-------|----------|
| Keychain | service: `now.typeless.desktop` · account: `.deviceIdentifier` |
| Local cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |

Wipe both locations and Typeless generates a brand-new Device ID on the next launch — the server sees a fresh machine.

## Usage

```bash
bash reset-device-macos.sh
```

> If Typeless is installed in a non-default location, set the path override:
> ```bash
> TYPELESS_APP_PATH=/path/to/Typeless.app bash reset-device-macos.sh
> ```

## What the script does

| Step | Action |
|------|--------|
| 1 | Force-quit Typeless |
| 2 | Delete `device.cache` (server-assigned device UUID) |
| 3 | Remove the Keychain entry |
| 4 | Delete `user-data.json` (encrypted login state) |
| 5 | Clear `userData` / `quotaUsage` from `app-storage.json` |
| 6 | Wipe login cookies and Local Storage |
| 7 | Relaunch Typeless → fresh Device ID generated on startup |

You will need to log back into your Typeless account after running the script.

## File structure

```
├── README.md                   # Chinese README
├── README.en.md                # English README
└── reset-device-macos.sh       # macOS reset script (bash)
```

## License

MIT
