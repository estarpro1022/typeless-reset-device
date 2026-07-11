# typeless-reset-device

**解除 Typeless macOS 设备登录限制 + 迁移个人词典到新账号**

中文 | [English](README.en.md)

---

## 背景

> Typeless v2.0.0，macOS 版

Typeless 新注册账号可以免费试用 Pro 一个月（**注意**：使用域名邮箱注册的账号不再享受免费试用，请用 Gmail 等常规邮箱注册）。但当你在同一台设备上登录多个账号后，会出现以下报错：

```
The number of users logged into this device has exceeded the limit.
```

这是因为 Typeless 会在每次请求服务端时携带一个 **Device ID**，服务端通过这个标识来限制单台设备的登录账号数量。

本工具提供两件事：
1. **重置 Device ID** — 让服务端把当前机器视为新设备
2. **迁移账号数据** — 包括个人词典（云端 API）、历史记录、录音文件

如果只是想解决多设备登录问题，那么直接 `bash reset-device-macos.sh` 重置设备ID即可，登录新账号不再出现报上述错误（可使用常规邮箱重新注册白嫖！域名邮箱不行）

如果想顺便把账号数据做迁移，可继续阅读↓↓↓

## 环境要求

- macOS
- Python 3.9+（通过 uv 管理依赖）
- [uv](https://docs.astral.sh/uv/)（Python 包管理器）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# 安装依赖
uv sync
```

## 使用方法

### 完整流程：重置设备 + 迁移数据

```bash
# 1. 登录旧账号，导出所有数据
uv run python3 export.py
# → 创建 backup_<时间戳>/ 目录，包含词典、数据库、录音、设置

# 2. 重置设备 ID
bash reset-device-macos.sh

# 3. 在 Typeless 中登录新账号

# 4. 导入数据到新账号
uv run python3 import.py backup_<时间戳>/
```

## 原理（逆向分析）

### Device ID

Device ID 来自 macOS 原生动态库 `libUtilHelper.dylib`，读取顺序如下：

```
1. 读 Keychain
   └─ 找到 → 使用该值
   └─ 未找到 ↓
2. 读本地 cache 文件
   └─ 找到 → 使用该值，并同步回 Keychain
   └─ 未找到 ↓
3. 生成新 UUID
   └─ 写入 Keychain + 本地 cache
```

Device ID 在 macOS 的存储位置：

| 存储 | 位置 |
|------|------|
| Keychain | service: `now.typeless.desktop.deviceIdentifier` · account: `now.typeless.desktop.security.auth_key` |
| 本地 cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |

把这两处清干净，下次启动 Typeless 就会生成全新的 Device ID，服务端将其视为一台新设备。

### 词典 API

词典数据仅存储在 Typeless 服务端，本地无任何副本。`export.py` / `import.py` 通过逆向 Typeless 的 API 签名协议直接调用云端接口：

1. 解密 `user-data.json`（electron-store 加密：双重 PBKDF2 + AES-256-CBC）
2. 构造 API 安全请求头（HMAC-SHA1 签名 + CryptoJS AES 加密的 `X-Authorization`）
3. 调用 `/user/dictionary/list`（导出）和 `/user/dictionary/add`（导入）

### 本地数据库

`typeless.db` 中 `history` 和 `history_v2` 表每行记录都有一个 `user_id` 字段，绑定到特定账号（v1.8.0 起实际使用 `history_v2`，`history` 为遗留表，v2.0.0 保持一致）。迁移时将该字段从旧 `user_id` 更新为新 `user_id`，录音文件（`.ogg`）无需修改。

### 加密细节

`user-data.json` 使用 Electron 的 `electron-store`（conf v13）加密：

```
加密密钥 = PBKDF2-SHA256(SHA256("darwin-{arch}").hex() + "Typeless", "typeless-user-service", 10000, 32)
逐值密钥 = PBKDF2-SHA512(加密密钥, IV.toUtf8(), 10000, 32)
文件格式 = [16字节 IV] + ':' + [AES-256-CBC 密文]
```

其中 `arch` 为 `arm64`（Apple Silicon）或 `x64`（Intel Mac），自动检测。

## reset-device-macos.sh 做了什么

| 步骤 | 说明 |
|------|------|
| 1 | 强制退出 Typeless |
| 2 | 删除 `device.cache`（服务端下发的设备 UUID） |
| 3 | 移除 Keychain 中的设备标识条目 |
| 4 | 删除 `user-data.json`（加密的登录态文件） |
| 5 | 清除 `app-storage.json` 中的 `userData` / `quotaUsage` 字段 |
| 6 | 删除登录 Cookie 及 Local Storage |
| 7 | 重新启动 Typeless（自动生成新 Device ID） |

运行后需要重新登录 Typeless 账号。

## 文件结构

```
├── README.md                   # 中文 README
├── README.en.md                # English README
├── reset-device-macos.sh       # macOS 重置脚本（bash）
├── export.py                   # 导出所有数据（词典 + 数据库 + 录音 + 设置）
├── import.py                   # 导入所有数据到新账号
├── crypto_utils.py             # 加密与签名工具库
├── pyproject.toml              # Python 项目配置
└── .gitignore
```

## 参考

这里感谢以下仓库，借鉴了其中的实现：

* [mercy719/typeless-migrator](https://github.com/mercy719/typeless-migrator)
* [schummiking/free-typeless](https://github.com/schummiking/free-typeless)

## 许可证

MIT
