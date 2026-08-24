# 号池（Account Pool）

Typeless 免费账号每个 8000 字/周配额。号池让你同时管理多个账号，API 请求自动走配额最充足的号，突破单号限制。

## 快速开始

```bash
# 1. 当前 Typeless 已登录 → 提取到号池
uv run python3 account_pool.py extract --alias slot1

# 2. 在 Typeless 里登出，登入下一个号，提取
uv run python3 account_pool.py extract --alias slot2

# 3. 重复 N 次...

# 4. 查看号池状态
uv run python3 account_pool.py status

# 5. 刷新所有配额
uv run python3 account_pool.py refresh
```

## 命令

| 命令 | 说明 |
|---|---|
| `extract --alias <名>` | 从当前 Typeless 会话提取凭证入库 |
| `status` | 查看所有号及其配额 |
| `refresh` | 刷新所有号的配额数据 |
| `request -p <路径> -d <JSON>` | 通过号池发 API 请求（自动选最优号） |
| `restore --alias <名>` | 将某号的凭证恢复到 Typeless App |
| `remove --alias <名>` | 从号池删除某号 |

## 在代码里用

```python
from account_pool import AccountPool

pool = AccountPool()

# 自动选配额最多的号发请求
result = pool.request("/user/dictionary/add", {"term": "hello"})
# → {"success": True, "slot_alias": "slot3", ...}

# 指定某个号
result = pool.request("/user/usage_stats", slot=pool.accounts["slot1"])

# 获取有配额余量的号
available = pool.get_all_with_quota(min_words=500)
```

## 原理

每个号的凭证（`user_id`、`refresh_token`）存在 `~/.typeless-pool/pool.json`。请求签名用的 `device_id` 不校验，可以所有号共用同一个。API 配额通过 `/user/usage_stats` 实时查询。
