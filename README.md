# typeless-reset-device

**解除 Typeless macOS 设备登录限制，一条命令重置设备标识**

中文 | [English](README.en.md)

---

## 背景

> Typeless 版本 v1.1.0，macOS版

Typeless 新注册账号可以免费试用 Pro 一个月。但当你在同一台设备上登录多个账号后，会出现以下报错：

```
The number of users logged into this device has exceeded the limit.
```

这是因为 Typeless 会在每次请求服务端时携带一个 **Device ID**，服务端通过这个标识来限制单台设备的登录账号数量。

## 原理（逆向分析）

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
| Keychain | service: `now.typeless.desktop` · account: `.deviceIdentifier` |
| 本地 cache | `~/Library/Application Support/now.typeless.desktop/device.cache` |

把这两处清干净，下次启动 Typeless 就会生成全新的 Device ID，服务端将其视为一台新设备。

## 使用方法

```bash
bash reset-device-macos.sh
```

> 如果 Typeless 安装在非默认路径，可设置环境变量覆盖：
> ```bash
> TYPELESS_APP_PATH=/path/to/Typeless.app bash reset-device-macos.sh
> ```

## 脚本做了什么

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
└── reset-device-macos.sh       # macOS 重置脚本（bash）
```

## 许可证

MIT
