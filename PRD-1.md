# InflatableModel.CN 产品需求文档 v2 (PRD-1)

> 生成日期：2026-06-02

---

# 第 1 章：项目概述与技术栈总览

## 1.1 产品定位

InflatableModel.CN 是一个面向**欧美市场**的充气模型（Inflatable Model）在线定制平台。用户上传参考图片或输入文字描述，系统通过 AI 技术自动生成可交互的 3D 模型（GLB/OBJ 格式），支持在线 360° 预览和下载。生成完成后，用户可与专属顾问 "Mia" 实时聊天沟通修改需求、确认生产细节并完成下单。

产品核心价值主张：**将充气模型的定制流程从"反复邮件沟通+手绘草图"压缩为"上传图片→AI生成3D→在线确认"，大幅降低沟通成本和打样周期。**

## 1.2 功能模块全景

系统由四大核心模块构成：

| 模块 | 核心功能 | 覆盖页面 |
|------|---------|---------|
| **认证系统** | 邮箱验证码登录/注册、Google OAuth 一键登录、30天免登录、退出清除 | `/login`、`/verify` |
| **3D 生成** | 图片/文字→3D模型生成、轮询任务状态、Three.js 在线预览、GLB/OBJ 下载 | `/generate`、`/result/<task_id>` |
| **聊天消息** | 客户-管理员实时聊天、图片发送、快捷回复、未读通知 | `/messages` |
| **管理后台** | 客户列表（搜索/排序/未读角标）、聊天面板、客户标签管理(D/C/B/A/S/SS/SSS)、模型列表查看、流量统计看板（PV/UV/页面分布/环比同比/多维度切换） | `/admin`（含聊天管理+流量统计两个独立板块） |

辅助模块：首页 Landing（`/`）、流量统计中间件（`@before_request track_traffic`）、邮件发送（`mailer.py`）、数据库自动备份（`backup.py`）、香港代理节点（`hk_proxy.py`）。

## 1.3 技术栈

| 层级 | 技术选型 | 版本要求 | 选型理由 |
|------|---------|---------|------|
| **后端框架** | Flask | ≥3.0 | 轻量、快速原型、适合中小规模 API 服务 |
| **Session** | Flask-Session (filesystem) | ≥0.7 | 零配置，单节点场景无需 Redis |
| **HTTP 客户端** | requests | ≥2.31 | 同步调用混元3D API，简单可靠 |
| **WSGI 服务器** | Gunicorn | ≥21.2 | 生产级多 worker，与 Flask 生态无缝集成 |
| **数据库** | SQLite (WAL 模式) | 内置 | 零运维、单文件备份、适合轻量场景 |
| **前端 JS** | Vanilla JS + Chart.js + Google Identity Services | CDN 引入 | 无构建工具链，直接部署，减少依赖 |
| **CSS** | 纯 CSS 变量系统 + Flexbox/Grid | — | 响应式，无预处理器 |
| **3D 渲染** | Three.js (GLTFLoader + OrbitControls) | ES Module Import Map | GLB 原生支持，ACES 色调映射 |
| **邮件** | smtplib (SSL) | Python 标准库 | 阿里云企业邮箱 SMTP，无需第三方库 |
| **反向代理** | Nginx | — | 静态文件缓存、CF Real IP、client_max_body_size |
| **CDN/Tunnel** | CloudFlare | Free Tier | DNS + CDN 缓存 + Tunnel 穿透，月费 $0 |

依赖清单（`requirements.txt`）：

```
flask>=3.0
flask-session>=0.7
requests>=2.31
gunicorn>=21.2
```

仅 4 个生产依赖，无异步框架、无 ORM、无消息队列，最大程度降低运维复杂度和攻击面。

## 1.4 配置项总览

所有配置通过 `config.py` 集中管理，支持环境变量覆盖（`.env` 文件加载）：

| 配置项 | 默认值 | 说明 |
|--------|-------|------|
| `SECRET_KEY` | 自动生成 32 位 hex | Flask Session 加密密钥 |
| `HUNYUAN_API_KEY` | `sk-kuuLt0x...` | 腾讯混元3D API 密钥 |
| `HUNYUAN_ENDPOINT` | `https://api.ai3d.cloud.tencent.com` | 混元3D API 地址 |
| `HUNYUAN_MODEL` | `3.0` | 混元3D 模型版本 |
| `HUNYUAN_PROXY_URL` | 空（不启用） | 香港代理节点 URL，设置后自动切换路由 |
| `HUNYUAN_PROXY_SECRET` | 空 | 代理鉴权密钥 |
| `GOOGLE_CLIENT_ID` | 空 | Google OAuth 客户端 ID |
| `SESSION_TYPE` | `filesystem` | Session 存储类型 |
| `SESSION_PERMANENT` | `True` | Session 持久化 |
| `PERMANENT_SESSION_LIFETIME` | 30 天 | 免登录有效期 |
| `DATABASE` | `data.db` | SQLite 数据库文件名 |
| `ADMIN_PASSWORD` | `admin` | 管理员后台密码 |
| `MAIL_SERVER` | `smtp.mxhichina.com` | 阿里云企业邮箱 SMTP |
| `MAIL_PORT` | 465 | SSL 端口 |
| `MAIL_USER` | `noreply@inflatablemodel.cn` | 发件邮箱 |
| `MAIL_PASSWORD` | 空 | 邮箱密码 |
| `MAIL_FROM` | `noreply@inflatablemodel.cn` | 发件人地址 |

---

# 第 2 章：页面路由与 API 设计

## 2.1 路由总表

| 路径 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | 无 | 首⻚（Landing Page），产品展示 |
| `/login` | GET/POST | 无 | 注册/登录，邮箱验证码或 Google OAuth |
| `/verify` | GET/POST | 无 | 邮箱验证码校验 |
| `/generate` | GET/POST | 需要 | 上传图片或输入文字进行 3D 生成 |
| `/messages` | GET | 需要 | 客户聊天页面，与顾问 Mia 实时沟通 |
| `/result/<task_id>` | GET | 需要 | 3D 模型结果页，预览 + 下载 |
| `/admin` | GET | 管理员 | 管理后台（含聊天管理 + 流量统计两个板块） |
| `/admin/traffic` | GET | 管理员 | 独立流量统计页（备用入口） |
| `/admin_login` | GET | 无 | 管理员登录页面（独立） |

## 2.2 API 端点

### 2.2.1 认证 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 发送邮箱验证码或 Google OAuth 登录 |
| POST | `/api/verify` | 提交验证码完成登录 |
| GET | `/api/me` | 获取当前用户信息（加 Session 过期判断） |
| POST | `/api/logout` | 登出（清除 Session + 客户端 Cookie） |
| POST | `/api/admin/login` | 管理员密码登录 |
| POST | `/api/admin/logout` | 管理员登出 |

### 2.2.2 3D 生成 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/proxy-3d` | 提交 3D 生成任务（图片/文字→混元 API） |
| GET | `/api/task-status/<task_id>` | 轮询任务状态 |
| GET | `/api/download-model` | 下载 GLB/OBJ 文件 |
| POST | `/api/upload-chat-image` | 上传聊天图片（生成时用） |

### 2.2.3 消息 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/notifications` | 通知列表（未读消息、模型完成等） |
| GET | `/api/quick-replies` | 获取快捷回复列表 |
| POST | `/api/send` | 发送消息（客户→顾问） |
| GET | `/api/messages` | 获取当前用户的所有消息 |

### 2.2.4 后台管理 API（管理员）

**聊天管理（`admin_chat.py`，Blueprint 前缀 `/api/admin`）：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/customers` | 获取所有客户列表（含未读数、排序） |
| GET | `/api/admin/customer/<customer_id>` | 获取单个客户详情 |
| GET | `/api/admin/customer/models` | 获取客户的 3D 模型列表 |
| GET | `/api/admin/messages/<customer_id>` | 获取与某个客户的消息历史 |
| POST | `/api/admin/reply` | 管理员回复客户消息 |
| POST | `/api/admin/customer/update` | 更新客户信息（标签、国家、WhatsApp 等） |
| GET | `/api/admin/unread-count` | 获取未读消息总数 |

**流量统计（`admin_traffic.py`，Blueprint 前缀 `/api/admin/traffic`）：**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/traffic/summary` | 流量汇总（支持 period=day/week/month/year 参数） |
| GET | `/api/admin/traffic/logs` | 流量原始日志 |
| GET | `/api/admin/traffic/page` | 页面维度数据 |

**流量统计 API 响应结构（/summary）：**

```json
{
  "pv": 49,
  "uv": 1,
  "total_all": 1023,
  "date_range": "2026-06-01 ~ 2026-06-02",
  "date": "2026-06-02",
  "period": "week",
  "pv_dod": 100.0,
  "pv_wow": -95,
  "pv_yoy": 100,
  "daily": [
    {"date": "2026-06-01", "pv": 0, "uv": 0},
    {"date": "2026-06-02", "pv": 49, "uv": 1}
  ],
  "page_distribution": [
    {"page": "首页", "path": "/messages", "count": 1},
    ...
  ],
  "monthly": [
    {"ym": "2026-05", "pv": 974, "uv": 2},
    {"ym": "2026-06", "pv": 49, "uv": 1}
  ]
}
```

---

# 第 3 章：管理后台（核心管理模块）

## 3.1 架构设计

管理后台采用**双 Blueprint 架构**，将聊天管理和流量统计拆分为独立的 Flask Blueprint：

- **聊天管理**（`admin_chat.py`）：`chat_bp`，管理客户列表、消息收发、客户资料编辑
- **流量统计**（`admin_traffic.py`）：`traffic_bp`，管理流量数据查询、统计计算

两个 Blueprint 统一注册到 `app.py`，共享同一 Session 认证机制。

## 3.2 导航与布局

管理后台使用**顶部横式选项卡导航**：

```
┌──────────────────────────────────────────────────────────┐
│ [InflatableModel]  [聊天管理] [流量统计]          [退出] │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Tab: 聊天管理                                           │
│  ┌──────────┬──────────────────────┬────────────────────┐ │
│  │ 客户列表 │  聊天消息区域        │  客户详情          │ │
│  │ (搜索框) │  (消息气泡)          │  - 姓名/邮箱/国家  │ │
│  │ 客户A    │                      │  - WhatsApp/电话   │ │
│  │ 客户B    │  [输入框] [发送]     │  - 标签(D/C/B/A/S/ │ │
│  │ 客户C    │                      │    SS/SSS)         │ │
│  │ ...      │                      │  - 公司/生成状态   │ │
│  │          │                      │  - 3D模型列表      │ │
│  └──────────┴──────────────────────┴────────────────────┘ │
│                                                          │
│  Tab: 流量统计                                           │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ [日] [周] [月] [年]  ← 时间维度切换                  │ │
│  │ PV浏览 UV访客 累计PV  环比  同比   ← 统计数字卡片   │ │
│  │ ┌─ 折线图 (每日PV/UV趋势) ──────────────────────┐   │ │
│  │ └─────────────────────────────────────────────────┘   │ │
│  │ ┌─ 饼图 (页面分布) ─────────────────────────────┐    │ │
│  │ └─────────────────────────────────────────────────┘   │ │
│  │ ┌─ 柱状图 (月度趋势) ───────────────────────────┐    │ │
│  │ └─────────────────────────────────────────────────┘   │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

## 3.3 聊天管理功能

### 3.3.1 客户列表（左侧面板）
- 按最后消息时间降序排列
- 搜索框支持按姓名/邮箱/公司筛选
- 显示未读消息红色角标
- 选中状态高亮
- 轮询刷新（每 4 秒自动刷新列表和消息）

### 3.3.2 聊天消息（中间面板）
- 管理员回复（A 头像）和客户消息（C 头像）区分显示
- 系统消息特殊样式
- 支持管理员发送图片（上传→预览→发送）
- Enter 发送，Shift+Enter 换行
- 消息自动滚动到底部
- 显示消息时间

### 3.3.3 客户详情（右侧面板）
- 姓名、邮箱（只读）
- 国家、WhatsApp（可编辑，失焦自动保存）
- 标签选择器：D / C / B / A / S / SS / SSS
- 电话、公司（只读）
- 生成状态（已完成/未生成）
- 3D 模型列表（显示模型ID前缀、完成时间、下载链接）

## 3.4 流量统计功能

### 3.4.1 时间维度
- **日**：查看最近 7 天每日数据
- **周**：本周（周一至今）数据 + 环比上周
- **月**：本月至今数据 + 环比上月
- **年**：年度月度趋势柱状图 + 同比

### 3.4.2 统计指标
| 指标 | 含义 | 数据来源 |
|------|------|---------|
| PV | 页面浏览次数 | `traffic_logs` 表按 URL 计数 |
| UV | 独立访客数 | 按 IP 去重计数 |
| 累计PV | 全站历史总 PV | `traffic_logs` 表总行数 |
| 环比 | 当前周期 vs 上一周期增长率 | 根据 period 自动计算（日:dod/周:wow/月:mom） |
| 同比 | 当前周期 vs 去年同期增长率 | `pv_yoy` 计算 |

### 3.4.3 数据永久记录
- 流量数据永久保存，按月、年维度自动聚合
- 已实现 1023 条历史数据回填
- `date` 字段用于按日统计，`created_at` 用于精确时间记录

---

# 第 4 章：数据库设计

## 4.1 表结构总览

```sql
-- 用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,              -- 邮箱作为 ID
    name TEXT DEFAULT '',
    password_hash TEXT DEFAULT '',     -- 备用密码（当前未使用）
    created_at TEXT DEFAULT (datetime('now')),
    country TEXT DEFAULT '',
    whatsapp TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    company TEXT DEFAULT '',
    tag TEXT DEFAULT 'B',             -- 标签: D/C/B/A/S/SS/SSS
    google_id TEXT DEFAULT ''          -- Google OAuth 用户 ID
);

-- 消息表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,          -- 关联 users.id
    content TEXT DEFAULT '',
    sender TEXT NOT NULL,               -- 'customer' | 'admin' | 'system'
    image_path TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (customer_id) REFERENCES users(id)
);

-- 生成任务表
CREATE TABLE generation_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    task_id TEXT NOT NULL UNIQUE,       -- 混元 API 返回的任务 ID
    prompt TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',      -- pending | processing | completed | failed
    model_url TEXT DEFAULT '',
    thumbnail_url TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 流量记录表
CREATE TABLE traffic_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    ip TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    referer TEXT DEFAULT '',
    date TEXT NOT NULL,                 -- YYYY-MM-DD 用于按日统计
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_traffic_date ON traffic_logs(date);
CREATE INDEX idx_traffic_path ON traffic_logs(path);

-- 通知表
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,                 -- 'model_complete' | 'admin_reply' | 'system'
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 快捷回复表
CREATE TABLE quick_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL
);
```

## 4.2 SQLite 注意事项
- 使用 WAL 模式提升并发读取性能
- `traffic_logs` 表的 `date` 字段已建索引，按日查询效率高
- 定期监控 `data.db-wal` 文件大小

---

# 第 5 章：部署与运维

## 5.1 主站部署（美国西岸 VPS）

### 5.1.1 Nginx 配置
（省略具体配置，与 v1 一致）

### 5.1.2 Systemd 服务
（省略具体配置，与 v1 一致）

### 5.1.3 部署脚本
（省略具体步骤，与 v1 一致）

## 5.2 香港代理节点

### 5.2.1 功能
当主站位于美国西岸时，通过香港节点代理混元 API 请求，降低中美网络延迟带来的不稳定因素。可选配置，默认直连。

### 5.2.2 代码结构
`hk_proxy.py` — 独立的 Flask 应用，仅转发混元 API 请求（submit + query），包含 IP 白名单鉴权。

### 5.2.3 代理 vs 直连模式对比
| 模式 | Submit 延迟 | Query 延迟 | 额外成本 |
|------|------------|-----------|---------|
| 直连（美西→腾讯云） | ~200ms | ~200ms | $0 |
| 代理（美西→香港→腾讯云） | ~200ms + <10ms | ~200ms + <10ms | 约$25/月 |

默认推荐直连模式。

## 5.3 运维注意事项

- 日志管理：Gunicorn + Nginx 日志按天轮转，保留 30 天
- 数据备份：`backup.py` 每日自动备份 SQLite 数据库
- 监控检查点：Flask 应用存活、Gunicorn worker 数、SQLite WAL 膨胀、API 响应
- 证书管理：CloudFlare 免费自动 TLS，无需手动续期
- 环境变量敏感信息：密钥、密码等通过 `.env` 或 systemd EnvironmentFile 管理，禁止提交到 Git

---

# 第 6 章：已修复的问题与安全改进

## 6.1 已修复的问题
1. **开放代理漏洞**：`hk_proxy.py` 添加 IP 白名单鉴权，移除无限制代理
2. **SQL 注入风险**：查询参数使用参数化查询（`?` 占位符）
3. **Three.js CDN 加载失败**：添加备用 CDN 源
4. **管理后台界面布局**：`app-layout` 使用 `flex-direction: row` 替代 column，修复三栏布局高度溢出；`body` 使用 `display: flex; flex-direction: column` 使标签页容器正确撑满剩余高度
5. **Chart.js 脚本未闭合**：CDN 引用缺少 `</script>` 标签，导致后续所有 JS 不执行
6. **流量统计选项卡嵌套**：`tabTraffic` div 嵌套在 `tabChat` 内部，导致切换时无法正确显示；已修复为同级兄弟节点
7. **标签系统更新**：客户标签从 Hot/Warm/Cold/Closed 改为 D/C/B/A/S/SS/SSS

## 6.2 界面优化
1. **中文界面**：管理后台所有 UI 文本改为中文，包括按钮文本、占位符、标签等
2. **流量统计维度**：支技日/周/月/年维度切换，包含环比（WoW/MoM/DoD）和同比（YoY）对比数据
3. **布局优化**：聊天面板回复栏固定在视口底部，不再溢出屏幕


---

# 第 7 章：改进建议与路线图

## 7.1 改进建议总览

| 优先级 | 编号 | 建议内容 | 对应模块 | 状态 |
|--------|------|---------|---------|------|
| P0 | 1 | 客户聊天页面增加"我的模型"展示 | 聊天消息 | ✅ 已实现 |
| P0 | 2 | 3D 模型预览优化（全屏按钮 + Loading动画） | 3D 生成 | ✅ 已实现 |
| P0 | 3 | 生成失败重试机制 | 3D 生成 | ❌ 尚未实现（需要result路由）|
| P1 | 4 | 未读通知红点角标 | 聊天消息 | ✅ 已实现 |
| P1 | 5 | 快捷回复后台管理（添加/删除/编辑） | 管理后台 | ✅ 已实现（右面板管理区）|
| P1 | 6 | 流量统计导出 CSV | 管理后台 | ✅ 已实现（/api/admin/traffic/export）|
| P1 | 7 | 标签筛选客户（D/C/B/A/S/SS/SSS） | 管理后台 | ✅ 已实现 |
| P2 | 8 | 管理员操作日志 | 管理后台 | ✅ 已实现（admin_logs表 + API）|
| P2 | 9 | 客户黑名单功能 | 管理后台 | ✅ 已实现（banned字段+界面按钮）|
| P2 | 10 | 批量操作（批量修改标签） | 管理后台 | ✅ 已实现（多选+批量修改标签）|
| P3 | 11 | 英文界面支持 | 全站 | ❌ 待实现 |
| P3 | 12 | 订单管理模块 | 新模块 | ❌ 待实现 |
| P3 | 13 | 工单系统 | 新模块 | ❌ 待实现 |

---

## 7.2 P0 — 核心功能增强

### 7.2.1 客户聊天页面增加"我的模型"展示

**现状**：客户登录后在 `/messages` 只能聊天，看不到自己的历史模型。

**需求**：
- 在聊天页面左侧或侧边栏显示用户的历史模型列表
- 展示模型缩略图、状态（生成中/已完成/失败）、完成时间
- 点击模型可跳转到模型详情页 `/result/<task_id>`
- 方便客户在聊天时随时回顾已生成的模型

**影响范围**：`templates/messages.html`、`app.py`（增加获取用户模型的 API）

### 7.2.2 3D 模型预览优化

**现状**：Three.js 预览框偏小，模型加载时缺少 Loading 动画。

**需求**：
- 在 `/result/<task_id>` 页面增加全屏预览按钮
- 全屏模式下 Three.js 预览占据整个视口，按 ESC 退出
- 模型加载时显示旋转的 Loading 动画（非白屏）
- 预览框默认尺寸扩大

**影响范围**：`templates/result.html`、Three.js 相关前端代码

### 7.2.3 生成失败重试机制

**现状**：混元 API 调用失败或超时时，用户只能刷新页面重新提交。

**需求**：
- 在 `/result` 页面检测任务状态为 "failed" 时，显示"重新生成"按钮
- 点击后调用 `/api/proxy-3d` 重新提交生成任务，使用原 prompt/图片
- 重试成功后将用户跳转到新任务的结果页
- 限制最多重试 3 次

**影响范围**：`templates/result.html`、`templates/generate.html`、后端 API

---

## 7.3 P1 — 体验优化

### 7.3.1 未读通知红点角标

**现状**：后端有 `/api/notifications` 轮询，但前端没有明显的通知提示。

**需求**：
- 在导航栏增加通知图标，显示未读数量红点
- 点击展开通知列表下拉框
- 通知类型：模型生成完成、管理员回复、系统通知
- 点击通知可跳转到对应页面
- 阅读后自动标记为已读

**影响范围**：`templates/messages.html`、`templates/generate.html`、前端 JS

### 7.3.2 快捷回复后台管理

**现状**：数据库中有 `quick_replies` 表，管理后台没有编辑入口。

**需求**：
- 在后台聊天管理右侧面板增加"快捷回复管理"区域
- 管理员可添加新的快捷回复、编辑已有的回复、删除
- 修改即时生效，所有管理员共享

**影响范围**：`templates/admin.html`、`admin_chat.py`（增加 API）

### 7.3.3 流量统计导出功能

**现状**：流量数据只能在页面查看。

**需求**：
- 在流量统计页面增加"导出 CSV"按钮
- 导出当前视图的 PV/UV 数据为 CSV 格式
- 包含日期、PV、UV、环比、同比等字段

**影响范围**：`templates/admin.html`、`admin_traffic.py`

### 7.3.4 标签筛选客户

**现状**：客户列表仅支持搜索框全文搜索。

**需求**：
- 在客户列表搜索框旁增加标签下拉筛选器
- 按 D/C/B/A/S/SS/SSS 标签筛选客户
- 筛选结果仅显示匹配标签的客户

**影响范围**：`templates/admin.html`、`admin_chat.py`

---

## 7.4 P2 — 运维与安全

### 7.4.1 管理员操作日志

**现状**：管理员的操作（回复、修改客户信息等）没有记录。

**需求**：
- 新建 `admin_logs` 表，记录管理员的关键操作
- 记录字段：操作时间、操作类型、目标客户、详情
- 在后台增加操作日志查看页面
- 日志仅可查看不可删除

**影响范围**：`admin_chat.py`（增加日志记录）、`admin_traffic.py`、`templates/admin.html`

### 7.4.2 客户黑名单功能

**现状**：无法屏蔽恶意或无效客户。

**需求**：
- 在客户详情中增加"加入黑名单"按钮
- 加入黑名单后：
  - 该客户的消息不再触发管理员通知
  - 客户在 `/messages` 页面看到"您已被限制使用"提示
  - 后台客户列表用灰色/斜体标记黑名单客户
- 支持从黑名单移除

**影响范围**：`users` 表增加 `banned` 字段、`admin_chat.py`、`templates/admin.html`、`templates/messages.html`

### 7.4.3 批量操作

**现状**：只能逐个操作客户。

**需求**：
- 后台客户列表增加复选框，支持多选
- 批量操作：
  - 批量修改标签
  - 批量发送系统消息/通知
- 批量操作前弹出确认对话框

**影响范围**：`templates/admin.html`、`admin_chat.py`

---

## 7.5 P3 — 长期规划

### 7.5.1 英文界面支持

**现状**：全站为中文界面，但目标用户是欧美市场。

**需求**：
- 实现 i18n 多语言框架（建议使用 Flask-Babel 或简单 JSON 字典）
- 首页、登录页、生成页、结果页支持英文
- 用户可根据浏览器语言自动切换
- 手动语言切换开关

**影响范围**：所有模板、后端文本

### 7.5.2 订单管理模块

**现状**：确认模型后无下单流程。

**需求**：
- 新建 `orders` 表：订单号、客户ID、模型ID、规格参数、数量、金额、状态
- 客户在结果页点击"确认下单"→填写规格→提交
- 管理员后台增加订单管理页面
- 订单状态：待确认、生产中、已发货、已完成

**影响范围**：新模块，涉及前后端

### 7.5.3 工单系统

**现状**：聊天记录无法追踪需求变更历史。

**需求**：
- 将客户每次需求变更转为工单
- 每个工单包含：需求描述、附件、状态、处理人、时间线
- 工单状态：待处理、处理中、已完成、已关闭
- 后台工单列表 + 详情页

**影响范围**：新模块，涉及前后端



# 第 8 章：用户反馈优化记录

## 8.1 用户反馈问题（13项）

以下为用户在测试过程中提出的13项问题及对应的解决方案：

| 编号 | 问题描述 | 解决方案 | 状态 |
|------|---------|---------|------|
| 1 | 后台聊天跟浏览数据分成两个项目 | 使用双Blueprint架构（admin_chat + admin_traffic）独立管理两个模块 | ✅ 已实现 |
| 2 | 浏览数据永久记录，按年月日分不同统计维度 | traffic_logs表永久保存，/summary接口支持day/week/month/year四维度 | ✅ 已实现 |
| 3 | 增加环比同比等常用对比数据及图表 | 环比（WoW/MoM/DoD）和同比（YoY）计算，Chart.js可视化 | ✅ 已实现 |
| 4 | 界面改为中文显示 | 管理后台、流量统计所有UI文本改为中文 | ✅ 已实现 |
| 5 | 标签内容换成D/C/B/A/S/SS/SSS | 系统标签从Hot/Warm/Cold改为D/C/B/A/S/SS/SSS | ✅ 已实现 |
| 6 | 后台聊天找不到流量统计入口 | 增加顶端横式选项卡切换（聊天管理/流量统计） | ✅ 已实现 |
| 7 | 流量统计里没有历史数据 | 修复admin_traffic.py数据查询问题，确保traffic表正确记录 | ✅ 已实现 |
| 8 | 希望通过顶端横式选项卡切换 | 顶部导航栏使用nav-tab实现chat/traffic切换 | ✅ 已实现 |
| 9 | 流量统计点不开/聊天选项卡里仍有流量统计模块 | 修复HTML结构，分离tabChat和tabTraffic为同级兄弟节点 | ✅ 已实现 |
| 10 | 流量统计没有数据/切换退出按钮还在 | 修复API数据查询，移除多余的切换按钮 | ✅ 已实现 |
| 11 | 聊天管理和流量管理没有数据 | 修复admin_traffic.py的endpoint冲突、SQL错误和前端渲染问题 | ✅ 已实现 |
| 12 | 点击会话在屏幕下方展开看不见 | 修复聊天面板布局，确保回复栏固定在视口底部 | ✅ 已实现 |
| 13 | 快捷回复管理出现在流量统计区域 | 将快捷回复管理移至聊天标签页的客户详情右面板 | ✅ 已实现 |

## 8.2 已修复的代码Bug

1. **admin_traffic.py重复endpoint**：`api_traffic_export`与已注册endpoint冲突，使用`endpoint="traffic_export_csv"`解决
2. **admin_traffic.py缺少_pv_total_all函数**：移除该调用，改用_pv_uv_for_range直接查询全部数据
3. **admin_traffic.py使用datetime.date.today()**：改为datetime.now().date()避免AttributeError
4. **admin_traffic.py的/page路由缺少视图函数**：补充api_traffic_page视图函数
5. **app.py中init_db的banned字段位置错误**：在CREATE TABLE前有悬挂的"banned INTEGER DEFAULT 0,"导致SQL语法错误
6. **app.py缺少if __name__ == '__main__'块**：无法直接运行服务器
7. **admin.html中快捷回复管理模块被嵌套在流量统计标签页内**：移到正确的聊天管理右面板
8. **admin.html中switchTab函数缺少</script>闭合标签**：修复HTML结构

---

# 第 9 章：版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1 | 2026-06-02 | 初始 PRD |
| v1.1 | 2026-06-02 | 重构管理后台：双 Blueprint 架构、中文界面、布局修复、标签系统更新 |
| v1.2 | 2026-06-02 | 新增改进路线图：13项优化建议（P0-P3） |
| v1.3 | 2026-06-02 | 用户反馈优化：修复8项代码Bug，实现13项用户反馈需求，完整中文界面 |

