# typeless-reset-device

**解除 Typeless (macOS / Windows) 设备登录限制 + 迁移个人数据到新账号**

中文 | [English](README.en.md)

---

## 背景

> 适配 Typeless v1.3.0 (macOS & Windows)

Typeless 新注册账号可以免费试用 Pro 一个月。但在同一台设备上登录多个账号后，会出现以下报错：
`The number of users logged into this device has exceeded the limit.`

这是因为 Typeless 会在请求服务端时携带由设备指纹生成的 **Device ID**。本工具通过逆向其加密协议与本地存储机制，实现以下功能：

1.  **重置设备指纹** — 让服务端将当前机器视为“全新设备”，从而绕过账号数量限制（白嫖 Pro 试用）。
2.  **全量数据迁移** — 包含云端个人词典（API 级导出/导入）、本地历史记录（SQLite 迁移）、录音文件（.ogg）及应用设置。

## 环境要求

- **操作系统**: macOS / Windows 10+
- **Python**: 3.9+ (建议通过 [uv](https://docs.astral.sh/uv/) 管理)
- **依赖管理**: 项目已配置好 `pyproject.toml`

```bash
# 安装 uv (macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh
# 安装 uv (Windows - PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 初始化环境
uv sync
```

## 使用方法

### 方式一：图形界面（推荐 🌟）

项目提供了一键式图形界面，适合所有用户：

```bash
uv run python gui.py
```

启动后，只需按照界面显示的 **步骤 1 (备份) -> 步骤 2 (重置) -> 步骤 3 (恢复)** 依次点击即可。

### 方式二：命令行流程

1.  **导出数据**: `uv run python export.py` (生成 `backup_<时间戳>/` 文件夹)
2.  **重置设备**: `uv run python reset.py` (自动强杀进程并清理标识)
3.  **切换账号**: 打开 Typeless 登录你的 **新账号**。
4.  **导入数据**: `uv run python import.py backup_<时间戳>/`

## 原理 (逆向分析)

### 1. 设备指纹 (Device ID)
Device ID 存储于系统凭据（Keychain/Credential Manager）及本地 `device.cache` 中。
- **macOS**: `~/Library/Application Support/now.typeless.desktop/device.cache`
- **Windows**: `%APPDATA%\Typeless\Cache\device.cache`

### 2. 加密逻辑 (Encryption)
应用使用 `electron-store` 加密 `user-data.json`。
- **密钥派生**: 基于平台标识 (`win32-x64` 或 `darwin-arm64`) 与应用名称 (`Typeless.exe` 或 `Typeless`) 进行双重 PBKDF2 哈希。
- **协议模拟**: 工具实现了完整的 HMAC-SHA1 签名与 CryptoJS AES 加密协议，直接与 API 通信以导出云端词典。

### 3. 数据隔离绕过
本地数据库 `typeless.db` 的每条历史记录都绑定了旧账号的 `user_id`。迁移工具会自动将数据库中的所有记录更新为新账号的 `user_id`，实现无缝对接。

## 文件结构

- `gui.py`: 跨平台图形化操作界面。
- `reset.py`: 统一的设备重置脚本（替代了旧版 bash 脚本）。
- `crypto_utils.py`: 核心加密/签名工具库，适配双端路径与盐值。
- `export.py` / `import.py`: 数据的导出与恢复引擎。
- `DEV_PLAN.md`: 详细的开发蓝图与任务历史。

## 许可证

MIT
