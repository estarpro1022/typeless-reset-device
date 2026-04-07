# typeless-reset-device

**解除 Typeless 设备登录限制 — 一条命令重置设备标识**

[English](#english) · [中文](#中文)

---

## 中文

### 背景

Typeless 新注册账号可以免费试用 Pro 一个月。但当你在同一台设备上登录多个账号后，会出现以下报错：

```
The number of users logged into this device has exceeded the limit.
```

这是因为 Typeless 会在每次请求服务端时携带一个 **Device ID**，服务端通过这个标识来限制单台设备的登录账号数量。

### 原理（逆向分析）

Device ID 来自原生动态库 `libUtilHelper.dylib`（macOS）/ 对应 Windows 模块，读取顺序如下：

```
1. 读 Keychain（macOS）/ Credential Manager（Windows）
   └─ 找到 → 使用该值
   └─ 未找到 ↓
2. 读本地 cache 文件
   └─ 找到 → 使用该值，并同步回 Keychain
   └─ 未找到 ↓
3. 生成新 UUID
   └─ 写入 Keychain + 本地 cache
```

Device ID 的存储位置：

| 平台 | 存储 | 位置 |
|------|------|------|
| macOS | Keychain | service: `now.typeless.desktop` · account: `.deviceIdentifier` |
| macOS | 本地 cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |
| Windows | Credential Manager | `Typeless.deviceIdentifier` |
| Windows | 本地 cache | `%APPDATA%\Typeless\Cache\device.cache` |

把这两处清干净，下次启动 Typeless 就会生成全新的 Device ID，服务端将其视为一台新设备。

### 使用方法

**macOS**

```bash
bash reset-device-macos.sh
```

> 如果 Typeless 安装在非默认路径，可设置环境变量覆盖：
> ```bash
> TYPELESS_APP_PATH=/path/to/Typeless.app bash reset-device-macos.sh
> ```

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File reset-device-windows.ps1
```

### 脚本做了什么

| 步骤 | 说明 |
|------|------|
| 1 | 强制退出 Typeless |
| 2 | 删除 `device.cache`（服务端下发的设备 UUID） |
| 3 | 移除 Keychain / Credential Manager 中的设备标识条目 |
| 4 | 删除 `user-data.json`（加密的登录态文件） |
| 5 | 清除 `app-storage.json` 中的 `userData` / `quotaUsage` 字段 |
| 6 | 删除登录 Cookie 及 Local Storage（仅 macOS） |
| 7 | 重新启动 Typeless（自动生成新 Device ID） |

运行后需要重新登录 Typeless 账号。

### 文件结构

```
├── reset-device-macos.sh       # macOS 重置脚本（bash）
└── reset-device-windows.ps1    # Windows 重置脚本（PowerShell）
```

### 许可证

MIT

---

## English

### Background

New Typeless accounts come with a one-month free Pro trial. After logging into multiple accounts on the same machine, you may see:

```
The number of users logged into this device has exceeded the limit.
```

This happens because Typeless sends a **Device ID** with every server request. The server uses this fingerprint to enforce a per-device account cap.

### How it works (reverse-engineered)

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

### Usage

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

### What the script does

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

### File structure

```
├── reset-device-macos.sh       # macOS reset script (bash)
└── reset-device-windows.ps1    # Windows reset script (PowerShell)
```

### License

MIT
