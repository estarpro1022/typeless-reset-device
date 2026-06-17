# 图书管理系统 — 设计文档

## 概述

全功能的图书管理系统，支持管理员端（图书管理、读者管理、借阅操作、统计看板）和读者端（浏览图书、借还书、查看借阅记录）。前后端分离，Docker Compose 一键部署。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React + Ant Design + React Router + Axios + ECharts |
| 后端 | Spring Boot + MyBatis-Plus + Spring Security + JWT |
| 数据库 | MySQL 8.0 |
| 部署 | Docker Compose（前端 nginx、后端 jar、MySQL） |

## 系统架构

```
┌──────────────┐          ┌──────────────┐          ┌───────────┐
│ React 前端    │   REST   │ Spring Boot  │   JDBC   │  MySQL 8  │
│ Nginx 托管    │ ──────→  │ MyBatis-Plus │ ───────→ │  (容器)   │
│ (容器)       │ ←──────  │ JWT 认证      │          │           │
└──────────────┘          └──────────────┘          └───────────┘
  管理端 /admin/*            /api/**                 Docker Volume
  读者端 /reader/*            返回 JSON               持久化数据
```

### 角色

| 角色 | 权限 |
|------|------|
| ADMIN | 管理图书（增删改查）、管理读者、帮读者借还书、查看统计数据 |
| READER | 浏览图书、自己借书、自己还书、查看自己的借阅记录 |

### 认证流程

```
用户登录 → POST /api/auth/login（用户名+密码）
         → 后端验证 BCrypt 密码
         → 签发 JWT（含 user_id + role）
         → 前端存 localStorage
         → 后续请求带 Authorization: Bearer <token>
```

## 数据模型

### book（图书）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键自增 |
| isbn | VARCHAR(20) | ISBN，唯一 |
| title | VARCHAR(200) | 书名 |
| author | VARCHAR(100) | 作者 |
| category | VARCHAR(50) | 分类 |
| publisher | VARCHAR(100) | 出版社 |
| publish_date | DATE | 出版日期 |
| stock | INT | 库存，借书 -1，还书 +1 |
| cover_url | VARCHAR(500) | 封面图地址 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### reader（读者）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键自增 |
| name | VARCHAR(50) | 姓名 |
| phone | VARCHAR(20) | 手机号 |
| email | VARCHAR(100) | 邮箱 |
| password | VARCHAR(200) | BCrypt 加密 |
| max_borrow | INT | 最大可借数，默认 5 |
| is_active | TINYINT | 启用/停用 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### borrow（借阅记录）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键自增 |
| book_id | BIGINT | 外键 → book.id |
| reader_id | BIGINT | 外键 → reader.id |
| borrow_date | DATE | 借书日期 |
| due_date | DATE | 应还日期，默认 +30 天 |
| return_date | DATE | 实际归还日期，NULL=未还 |
| status | VARCHAR(20) | BORROWING / RETURNED / OVERDUE |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### admin（管理员）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键自增 |
| username | VARCHAR(50) | 用户名，唯一 |
| password | VARCHAR(200) | BCrypt 加密 |
| role | VARCHAR(20) | ADMIN / OPERATOR |
| created_at | DATETIME | 创建时间 |

### 关系

```
book 1 ── N borrow N ── 1 reader
```

## API 设计

所有 API 以 `/api` 为前缀，返回 JSON。

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，返回 JWT |

### 图书
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/books` | 图书列表，支持分页和搜索（keyword / category） |
| GET | `/api/books/{id}` | 图书详情 |
| POST | `/api/books` | 新增图书（ADMIN） |
| PUT | `/api/books/{id}` | 编辑图书（ADMIN） |
| DELETE | `/api/books/{id}` | 删除图书（ADMIN，stock=0 才可删） |

### 读者
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/readers` | 读者列表（ADMIN） |
| GET | `/api/readers/{id}` | 读者详情 + 借阅历史（ADMIN） |
| POST | `/api/readers` | 管理员创建读者账号（ADMIN） |
| PUT | `/api/readers/{id}` | 编辑读者信息（ADMIN） |
| PATCH | `/api/readers/{id}/status` | 启用/停用读者（ADMIN） |

### 借阅
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/borrows` | 借书（检查 stock > 0 且未超 max_borrow） |
| PUT | `/api/borrows/{id}/return` | 还书（stock +1，设置 return_date） |
| GET | `/api/borrows` | 借阅记录列表（ADMIN 看全部，READER 看自己的） |

### 统计
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 总藏书/外借中/逾期/总读者数量（ADMIN） |
| GET | `/api/stats/popular` | 热门借阅 Top 10（ADMIN） |
| GET | `/api/stats/trend` | 近 30 天借阅趋势（ADMIN） |

### 借书业务规则

1. `book.stock > 0`，否则返回"库存不足"
2. 当前在借数 < `reader.max_borrow`，否则返回"已达最大借阅数"
3. 同一本书（book_id）同一读者（reader_id）不可重复借
4. 借阅创建 `status = BORROWING`，`due_date = borrow_date + 30天`

### 逾期处理

SQL 定时任务或查询时计算：当前日期 > due_date 且 status = BORROWING → 标记为 OVERDUE。

## 前端页面结构

### 布局

```
┌────────────────────────────────────────────┐
│  Logo  图书  读者  借阅  统计         [退出] │  ← 管理端导航
├────────────────────────────────────────────┤
│              内容区域                       │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  Logo  浏览图书  我的借阅            [退出]   │  ← 读者端导航
├────────────────────────────────────────────┤
│              内容区域                       │
└────────────────────────────────────────────┘
```

### 管理端页面

| 路径 | 页面 | 功能 |
|------|------|------|
| `/login` | 登录 | 统一登录，按角色跳转 |
| `/admin/books` | 图书管理 | 搜索、表格展示、新增/编辑抽屉、删除 |
| `/admin/readers` | 读者管理 | 搜索、表格展示、注册/编辑、启用停用 |
| `/admin/borrows` | 借阅管理 | Tab：借书 / 还书 / 全部记录（筛选状态） |
| `/admin/stats` | 统计看板 | 四卡片 + ECharts 热门排行 + 借阅趋势 |

### 读者端页面

| 路径 | 页面 | 功能 |
|------|------|------|
| `/reader/books` | 图书浏览 | 搜索、卡片/列表展示、点击借书 |
| `/reader/borrows` | 我的借阅 | 在借/已还/逾期列表，还书按钮 |

### 路由守卫

- 未登录 → 重定向到 `/login`
- 角色为 ADMIN 访问 `/reader/*` → 可访问（管理员也能用读者端）
- 角色为 READER 访问 `/admin/*` → 403

## 部署

### Docker Compose

```yaml
services:
  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: library
    ports: [3306:3306]
    volumes: [db_data:/var/lib/mysql]

  backend:
    build: ./backend
    ports: [8080:8080]
    depends_on: [db]
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://db:3306/library

  frontend:
    build: ./frontend
    ports: [80:80]
    depends_on: [backend]
```

### 初始化

- 启动时自动执行 Flyway/MyBatis 迁移脚本建表
- 预置一个 ADMIN 账号（admin / admin123）

## 不做的事情

- 不做验证码、OAuth 第三方登录
- 不做读者自助注册（由管理员创建）
- 不做图书副本/条码管理（用 stock 计数）
- 不做罚款/押金功能
- 不做操作日志审计
- 不做国际化 i18n

## 文件结构

```
library-management/
├── frontend/
│   ├── src/
│   │   ├── pages/           # 按角色分子目录
│   │   │   ├── admin/       # AdminBooks, AdminReaders, AdminBorrows, AdminStats
│   │   │   └── reader/      # ReaderBooks, ReaderBorrows
│   │   ├── components/      # BookForm, ReaderForm, BorrowCard...
│   │   ├── services/        # api.ts, auth.ts
│   │   ├── router/          # index.tsx, AuthGuard.tsx
│   │   └── App.tsx
│   ├── Dockerfile
│   └── nginx.conf
├── backend/
│   ├── src/main/java/com/library/
│   │   ├── config/          # SecurityConfig, MybatisPlusConfig
│   │   ├── controller/      # BookController, ReaderController...
│   │   ├── service/
│   │   ├── mapper/
│   │   ├── entity/
│   │   └── dto/
│   ├── src/main/resources/
│   │   └── application.yml
│   ├── Dockerfile
│   └── pom.xml
├── docker-compose.yml
└── README.md
```
