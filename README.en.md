# typeless-reset-device

**Bypass Typeless (macOS / Windows) login limits + Migrate personal data to a new account**

[中文](README.md) | English

---

## Background

> Supports Typeless v1.3.0 (macOS & Windows)

New Typeless accounts include a one-month free Pro trial. However, logging into multiple accounts on the same device triggers the error:
`The number of users logged into this device has exceeded the limit.`

Typeless identifies devices using a **Device ID** generated from hardware fingerprints. This tool reverse-engineers the application's encryption and local storage mechanisms to provide:

1.  **Device Fingerprint Reset** — Makes the server treat your machine as a "brand new device," bypassing account limits.
2.  **Full Data Migration** — Includes cloud-based personal dictionaries (API-level export/import), local history (SQLite migration), voice recordings (.ogg), and app settings.

## Requirements

- **OS**: macOS / Windows 10+
- **Python**: 3.9+ (Highly recommend using [uv](https://docs.astral.sh/uv/))
- **Dependency Management**: Pre-configured via `pyproject.toml`

```bash
# Install uv (macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Install uv (Windows - PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Initialize environment
uv sync
```

## Usage

### Option 1: Graphical Interface (Recommended 🌟)

A user-friendly one-click GUI is provided for all users:

```bash
uv run python gui.py
```

Simply follow **Step 1 (Backup) -> Step 2 (Reset) -> Step 3 (Restore)** as shown in the interface.

### Option 2: CLI Workflow

1.  **Export Data**: `uv run python export.py` (Creates a `backup_<timestamp>/` folder)
2.  **Reset Device**: `uv run python reset.py` (Kills app processes and wipes identifiers)
3.  **Switch Account**: Open Typeless and log in to your **NEW account**.
4.  **Import Data**: `uv run python import.py backup_<timestamp>/`

## How it works (Reverse Engineering)

### 1. Device Fingerprint (Device ID)
The Device ID is stored in system credentials (Keychain/Credential Manager) and local `device.cache` files.
- **macOS**: `~/Library/Application Support/now.typeless.desktop/device.cache`
- **Windows**: `%APPDATA%\Typeless\Cache\device.cache`

### 2. Encryption
The app uses `electron-store` to encrypt `user-data.json`.
- **Key Derivation**: Based on platform identifiers (`win32-x64` or `darwin-arm64`) and app names (`Typeless.exe` or `Typeless`) using double PBKDF2 hashing.
- **Protocol Simulation**: We implemented the full HMAC-SHA1 signature and CryptoJS AES encryption protocols to communicate directly with the API for dictionary export.

### 3. Data Isolation Bypass
Each history record in `typeless.db` is bound to the old account's `user_id`. The migrator automatically updates all records to the new account's ID, ensuring a seamless transition.

## File Structure

- `gui.py`: Cross-platform graphical user interface.
- `reset.py`: Unified reset script (replaces the legacy bash script).
- `crypto_utils.py`: Core encryption/signing library, adapted for both platforms.
- `export.py` / `import.py`: Data extraction and restoration engines.
- `DEV_PLAN.md`: Detailed development roadmap and task history.


## License

MIT
