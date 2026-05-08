# typeless-reset-device

**Reset the Typeless macOS device identifier + migrate account data to a new account**

[中文](README.md) | English

---

## Background

> Typeless v1.3.0, macOS

New Typeless accounts come with a one-month free Pro trial. After logging into multiple accounts on the same machine, you may see:

```
The number of users logged into this device has exceeded the limit.
```

This happens because Typeless sends a **Device ID** with every server request. The server uses this fingerprint to enforce a per-device account cap.

This tool provides two things:
1. **Reset Device ID** — makes the server treat your machine as a new device
2. **Migrate account data** — including personal dictionary (cloud API), history records, and recordings

If you just want to solve the device limit issue, simply run `bash reset-device-macos.sh` to reset the device ID. You can then login with a new account without seeing the error above (free trial!).

If you also want to migrate your data, keep reading ↓↓↓

## Requirements

- macOS / Windows
- Python 3.9+ (managed via uv)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

```bash
# Install uv (macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Install uv (Windows - PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync
```

## Usage

### Option 1: Graphical Interface (Recommended)

```bash
uv run python gui.py
```
After launching, simply follow "Step 1, 2, 3" in the window to complete the backup, reset, and restore process.

### Option 2: Command Line Workflow

```bash
# 1. Login to OLD account, export all data
uv run python export.py
# → creates backup_<timestamp>/ with dictionary, database, recordings, settings

# 2. Reset device ID
uv run python reset.py

# 3. Login to NEW account in Typeless

# 4. Import data to new account
uv run python import.py backup_<timestamp>/
```


## How it works (reverse-engineered)

### Device ID

Device ID storage locations:

| Platform | Location |
|-------|----------|
| macOS Keychain | service: `now.typeless.desktop.deviceIdentifier` · account: `now.typeless.desktop.security.auth_key` |
| macOS Local cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |
| Windows Local cache | `%APPDATA%\now.typeless.desktop\device.cache` |

Clean these spots, and the next time you start Typeless, it will generate a completely new Device ID, which the server will treat as a new device.

### Dictionary API

Dictionary data is stored only on Typeless servers — there is no local copy. `export.py` / `import.py` call the cloud API directly by reverse-engineering Typeless's API signing protocol:

1. Decrypt `user-data.json` (electron-store encryption: double PBKDF2 + AES-256-CBC)
2. Build API security headers (HMAC-SHA1 signature + CryptoJS AES encrypted `X-Authorization` header)
3. Call `/user/dictionary/list` (export) and `/user/dictionary/add` (import)

### Local database

Each row in `typeless.db`'s `history` table has a `user_id` field binding it to a specific account. Migration updates this field from the old `user_id` to the new one. Recording files (`.ogg`) require no modification.

### Encryption details

`user-data.json` is encrypted using Electron's `electron-store` (conf v13):

```
encryption_key = PBKDF2-SHA256(SHA256("darwin-{arch}").hex() + "Typeless", "typeless-user-service", 10000, 32)
value_key     = PBKDF2-SHA512(encryption_key, IV.toUtf8(), 10000, 32)
file format   = [16-byte IV] + ':' + [AES-256-CBC ciphertext]
```

Where `arch` is `arm64` (Apple Silicon) or `x64` (Intel Mac), auto-detected.

## What reset-device-macos.sh does

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
├── reset-device-macos.sh       # macOS reset script (bash)
├── export.py                   # Export all data (dictionary + db + recordings + settings)
├── import.py                   # Import all data into new account
├── crypto_utils.py             # Encryption & signing utilities
├── pyproject.toml              # Python project config
└── .gitignore
```

## References

Special thanks to the following repositories for reference:

* [mercy719/typeless-migrator](https://github.com/mercy719/typeless-migrator)
* [schummiking/free-typeless](https://github.com/schummiking/free-typeless)

## License

MIT
