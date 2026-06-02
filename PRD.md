# InflatableModel.CN 产品需求文档 (PRD)


> 📅 生成日期：2026-06-02


---


# 第 1 章：项目概述与技术栈总览

## 1.1 产品定位

InflatableModel.CN 是一个面向**欧美市场**的充气模型（Inflatable Model）在线定制平台。用户上传参考图片或输入文字描述，系统通过 AI 技术自动生成可交互的 3D 模型（GLB/OBJ/FBX 格式），支持在线 360° 预览和下载。生成完成后，用户可与专属顾问"Mia"实时聊天沟通修改需求、确认生产细节并完成下单。

产品核心价值主张：**将充气模型的定制流程从"反复邮件沟通+手绘草图"压缩为"上传图片→AI生成3D→在线确认"，大幅降低沟通成本和打样周期。**

## 1.2 功能模块全景

系统由四大核心模块构成：

| 模块 | 核心功能 | 覆盖页面 |
|------|---------|---------|
| **认证系统** | 邮箱验证码登录/注册、Google OAuth 一键登录、30天免登录、登出清除 | `/login`、`/verify` |
| **3D 生成** | 图片/文字→3D模型生成、轮询任务状态、Three.js 在线预览、GLB/OBJ 下载 | `/generate`、`/result/<task_id>` |
| **聊天消息** | 客户-管理员实时聊天、图片发送、快捷回复、未读通知 | `/messages` |
| **管理后台** | 客户列表（搜索/排序/未读角标）、聊天面板、客户标签管理、模型列表查看、7天流量统计看板（PV/UV/页面分布） | `/admin`、`/admin_login` |

辅助模块：首页 Landing（`/`）、流量统计中间件（`@before_request track_traffic`）、邮件发送（`mailer.py`）、数据库自动备份（`backup.py`）。

## 1.3 技术栈

| 层级 | 技术选型 | 版本要求 | 选型理由 |
|------|---------|---------|---------|
| **后端框架** | Flask | ≥ 3.0 | 轻量、快速原型、适合中小规模 API 服务 |
| **Session** | Flask-Session (filesystem) | ≥ 0.7 | 零配置，单节点场景无需 Redis |
| **HTTP 客户端** | requests | ≥ 2.31 | 同步调用混元3D API，简单可靠 |
| **WSGI 服务器** | Gunicorn | ≥ 21.2 | 生产级多 worker，与 Flask 生态无缝集成 |
| **数据库** | SQLite (WAL 模式) | 内置 | 零运维、单文件备份、适合轻量场景 |
| **前端 JS** | Vanilla JS + Three.js + Chart.js + Google Identity Services | CDN 引入 | 无构建工具链，直接部署，减少依赖 |
| **CSS** | 纯 CSS 变量系统 | — | 响应式 Grid/Flexbox，无预处理器 |
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
| `PERMANENT_SESSION_LIFETIME` | 30 天 | 免登录有效期 |
| `MAX_CONTENT_LENGTH` | 32 MB | 上传文件大小限制 |
| `MAIL_SERVER` | `smtp.mxhichina.com` | 阿里云企业邮箱 SMTP |
| `MAIL_PORT` | 465 | SSL 端口 |
| `ADMIN_PASSWORD` | `admin123` | 管理后台登录密码 |



---


# 第 2 章：用户角色与核心业务流程

## 2.1 用户角色定义

系统定义三类角色，权限逐级递升：

| 角色 | 标识方式 | 可访问页面 | 核心权限 |
|------|---------|-----------|---------|
| **访客** | 未登录 | `/`（首页）→ `/login` | 浏览 Landing 页，进入登录流程 |
| **客户** | `session.verified=True` | `/generate`、`/messages`、`/result/<id>` | 提交3D生成（限1次）、在线预览/下载模型、与管理员聊天 |
| **管理员** | `session.admin_logged_in=True` | `/admin` | 查看全部客户（含未读计数）、与任意客户聊天、编辑客户标签/信息、查看流量统计看板 |

Session 机制细节：客户和管理员使用独立的 session 字段（`verified` vs `admin_logged_in`），互不干扰。30天免登录仅对客户生效，管理员每次均需密码登录。

## 2.2 客户完整旅程

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Landing │───▶│  认证登录  │───▶│  3D 生成  │───▶│  结果预览  │───▶│  聊天沟通  │
│  (首页)   │    │ (/login) │    │(/generate)│    │(/result) │    │(/messages)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 阶段 1：Landing 与转化（`/` → `/login`）

1. 访客进入首页 `index.html`，看到 Hero 标题"Custom Inflatable Models — From Your Image to 3D"
2. 浏览 Features（4张特性卡片）、How It Works（4步流程）、Portfolio（示例作品网格）
3. 点击"Start Now"或 CTA Banner → 跳转 `/login`

**页面路由守卫**：若已登录用户访问 `/`，`before_request` 自动重定向到 `/generate`；若已用尽生成次数则跳转到 `/messages`。

### 阶段 2：认证登录（`/login` → `/verify`）

两条并行通道，用户择一即可：

**通道 A：邮箱验证码**
1. 填写 Email（必填）+ Phone/Name/Company（可选）
2. `POST /api/login` → 后端 `_ensure_customer()` 按 email 查/插 `customers` 表（id = email 的 URL-safe 编码）
3. 生成 6 位数字验证码，存入内存字典 `verification_codes[session.sid]`（5分钟有效期，最多5次错误，60秒重发间隔）
4. 调用 `mailer.send_verification_code()` 发送 HTML 邮件（紫色渐变头部 + 白色卡片 + 大号居中验证码）
5. 前端跳转 `/verify`，用户输入 6 位码（独立 digit 输入框，支持粘贴/自动聚焦/Backspace）
6. `POST /api/verify` → 校验通过后设 `session.verified=True` + 生成 30 天 `persistent_token` 入库 + 写 `auto_login` cookie

**通道 B：Google OAuth**
1. 点击 Google Sign-In 按钮，前端获取 `id_token`（credential）
2. `POST /api/auth/google` → 后端调 `https://oauth2.googleapis.com/tokeninfo` 验证 token
3. 提取 `email/name/picture/sub` → 按 email 查 customers 表：存在则 UPDATE（google_id + avatar），不存在则 INSERT（verified=1）
4. 直接设 session + 生成 30 天 persistent_token cookie
5. 返回 `ok:True` → 前端跳转 `/generate`

**30 天免登录机制**：

| 组件 | 实现 |
|------|------|
| Cookie 名称 | `auto_login` |
| Cookie 属性 | `httponly=True, samesite='Lax', max_age=30天` |
| Token 生成 | `uuid.uuid4().hex + secrets.token_hex(16)` |
| Token 存储 | `customers.persistent_token` + `customers.token_expires` |
| 恢复逻辑 | `@app.before_request auto_login_from_token()`：每请求检查 cookie → 查 DB 验证有效期 → 自动恢复 `session.verified` 和 `session.customer_id` |
| 清除逻辑 | `/api/logout` → 清空 cookie + DB token + `verified_sessions` 集合 |

### 阶段 3：3D 模型生成（`/generate`）

1. 进入生成页，左侧上传区（虚线拖拽、文件选择器）+ 右侧 3D 预览区（sticky 定位）
2. 拖入或选择参考图片（支持 png/jpg/jpeg/webp/bmp/gif），可选填文字描述
3. 点击提交 → `POST /api/generate-3d`（`multipart/form-data`，含 `image` + `description`）
4. 后端校验 `generation_count < 1` → 图片 base64 编码 → 调 `_submit_3d_job()` 发给混元3D API → 返回 `job_id` → 入库 `generation_tasks`（status='pending'）
5. 前端进入轮询：每 5 秒 `GET /api/task-status/<job_id>`，状态栏显示 Submitting → Processing → Completed/Failed
6. 完成时触发 `model-ready` 自定义事件 → Three.js GLTFLoader 加载 GLB → 3D 预览渲染

### 阶段 4：结果预览与下载（`/result/<task_id>`）

- 独立结果页含 Three.js 3D 预览（OrbitControls 旋转/缩放、三灯布光、ACES 色调映射）
- GLB/OBJ 下载按钮 → `GET /api/download-model?task_id=<id>&format=glb`
- "Chat with Mia" 按钮 → 跳转 `/messages`
- 10 秒倒计时自动跳转聊天页

### 阶段 5：聊天沟通（`/messages`）

- 左侧：已完成模型缩略图卡片
- 右侧：聊天面板（customer 气泡紫色浅底靠左、admin 气泡紫色实底靠右、system 消息灰色居中斜体）
- 底部：6条快捷回复按钮 + 文本输入栏 + 图片上传（10MB 限制）
- 每 3 秒轮询 `/api/messages` 刷新消息 + `/api/notifications` 更新未读角标

## 2.3 管理员工作流

```
┌──────────┐    ┌──────────────────────────────────────────────────────┐
│ 密码登录  │───▶│  三栏管理后台（/admin）                                │
│(/admin)  │    │  左：客户列表 ｜ 中：聊天面板 ｜ 右：详情/流量          │
└──────────┘    └──────────────────────────────────────────────────────┘
```

1. 访问 `/admin` → 未登录则显示 `admin_login.html`（暗色风格密码登录页）
2. `POST /api/admin/login` → 密码匹配 `ADMIN_PASSWORD` → 设 `session.admin_logged_in=True`
3. 进入三栏管理后台（每 4 秒自动刷新）：
   - **左侧客户列表**：搜索过滤、未读角标（红色数字）、首字母头像、tag 颜色标签（warm=黄/hot=红/cold=蓝）
   - **中间聊天面板**：点击客户加载对话 → 管理员气泡样式（紫色实底靠右）+ 图片灯箱 + 回复栏（文本+图片上传 10MB）
   - **右侧详情面板**（双标签页）：
     - **Detail**：行内可编辑字段（tag/country/whatsapp/phone/company）+ 保存按钮；已完成模型列表（task_id + 下载链接 + 完成时间）
     - **Traffic**：Chart.js 可视化——7天 PV 折线图 + 页面分布环形图 + 统计卡片（总PV/今日PV/今日UV）+ 最近10条访问记录表格

## 2.4 首次模型完成的自动化触达

当客户首次 3D 模型生成完成时（`/api/task-status` 返回 `done`），后端自动在 `messages` 表中插入一条 `sender='system'` 的欢迎消息：

> "Hi! Your 3D model is ready. I'm Mia, your personal consultant. Feel free to ask any questions about your design!"

此后管理员即可在后台看到该客户并主动发起对话。



---


# 第 3 章：功能需求详述

## 3.1 认证系统

### 3.1.1 API 清单

| 端点 | 方法 | 功能 | 请求体/参数 | 返回 |
|------|------|------|------------|------|
| `/api/login` | POST | 邮箱登录/注册 | `{email, phone?, name?, company?}` | `{ok, is_new, message}` |
| `/api/auth/google` | POST | Google OAuth 登录 | `{credential}` (id_token) | `{ok, name, is_new}` |
| `/api/verify` | POST | 验证码校验 | `{code}` (6位数字) | `{ok, message}` |
| `/api/resend-code` | POST | 重发验证码 | 无（基于 session） | `{ok, message}` |
| `/api/logout` | GET/POST | 登出 | 无 | `{ok}` |
| `/api/me` | GET | 当前登录状态 | 无 | `{logged_in, name, email}` |

### 3.1.2 验证码生命周期

```
生成（/api/login）
  │  存入 verification_codes[session.sid] = {
  │    email, code, expires(5min), attempts(0), last_code_sent
  │  }
  │  调用 mailer.send_verification_code()
  │
  ├── 用户输入正确 → 5分钟内 → /api/verify → pop记录 → 标记verified
  │
  ├── 用户输入错误 → attempts < 5 → 提示剩余次数
  │   └── attempts >= 5 → 记录标记 expired → 提示重新登录
  │
  ├── 5分钟过期 → 记录标记 expired → 提示重新登录
  │
  └── 重发（/api/resend-code）
       └── 距离上次发送 ≥ 60秒 → 生成新code并重置expires + attempts
```

验证码为 6 位纯数字（`random.randint(100000, 999999)`），存储于 Python 内存字典（非数据库），服务重启后全部失效。最多错误次数 5 次，超过后该记录标记 `expired=True`。

### 3.1.3 Google OAuth 验证链

```
前端 Google Sign-In
  → 获取 id_token（credential）
  → POST /api/auth/google {credential}
  → 后端 GET https://oauth2.googleapis.com/tokeninfo?id_token={credential}
  → 验证 audience 匹配 GOOGLE_CLIENT_ID
  → 提取 {email, name, picture, sub}
  → 按 email 查 customers:
      EXISTS → UPDATE google_id + avatar
      NOT EXISTS → INSERT (verified=1, name, email, google_id, avatar)
  → 生成 persistent_token → 设 auto_login cookie
  → 返回 {ok, name, is_new}
```

### 3.1.4 30天免登录数据流

```
请求到达 → @app.before_request auto_login_from_token()
  ├── session 有效 → 跳过
  ├── session 无效 + auto_login cookie 存在
  │   → 查 DB: SELECT persistent_token, token_expires FROM customers
  │          WHERE persistent_token = ? AND token_expires > datetime('now')
  │   → 匹配成功 → 恢复 session.verified + session.customer_id
  │   → 匹配失败 → 清除 cookie
  └── 无 cookie → 跳过
```

## 3.2 3D 生成流水线

### 3.2.1 API 清单

| 端点 | 方法 | 功能 | 限制 |
|------|------|------|------|
| `/api/generate-3d` | POST | 提交生成任务 | 需登录，每用户仅1次，multipart/form-data |
| `/api/task-status/<task_id>` | GET | 轮询任务状态 | 需登录，豁免流量统计 |
| `/api/download-model` | GET | 下载模型文件 | `?task_id=&format=glb/obj/fbx` |
| `/api/proxy-3d` | GET | 代理下载上游模型文件 | `?url=<原始URL>`，豁免流量统计 |

### 3.2.2 提交任务（POST /api/generate-3d）

**请求格式**：`multipart/form-data`
- `image`（file）：参考图片，支持 png/jpg/jpeg/webp/bmp/gif
- `description`（text，可选）：文字描述

**后端处理流程**：

```
1. is_logged_in() 校验 → session.customer_id
2. SELECT generation_count FROM customers WHERE id=? → count ≥ 1 则拒绝（403）
3. 读取 image 文件 → base64 编码
4. 读取 description 文本
5. _submit_3d_job(image_base64, prompt):
   请求体: {"Model": "3.0", "ImageBase64": "<base64>"}
   或如果无图片: {"Model": "3.0", "Prompt": "<text>"}
   目标URL: {HUNYUAN_ENDPOINT}/v1/ai3d/submit
   Header: Authorization: <API_KEY>
   → 解析 Response.JobId
6. INSERT generation_tasks (customer_id, input_type, job_id, status='pending')
7. UPDATE customers SET generation_status='in_progress'
8. 返回 {ok, task_id, status: "queued"}
```

**混元3D API 交互格式**（OpenAI-compatible 风格）：

```
# 提交请求
POST https://api.ai3d.cloud.tencent.com/v1/ai3d/submit
Authorization: sk-xxx
Content-Type: application/json
{"Model": "3.0", "ImageBase64": "iVBORw0..."}

# 提交响应
{"Response": {"JobId": "job_abc123", "RequestId": "req-xxx"}}

# 查询请求
POST https://api.ai3d.cloud.tencent.com/v1/ai3d/query
Authorization: sk-xxx
Content-Type: application/json
{"JobId": "job_abc123"}
```

### 3.2.3 轮询任务状态（GET /api/task-status/<task_id>）

**状态机**：

```
pending → running → done      → completed (前端 + DB)
                  → running   → in_progress (返回 progress=50)
                  → fail/failed/error → failed (DB 更新 error_message)
```

**done 状态的完整处理**：

```
_query_3d_job(task_id) → data.Response.Status = "done"
  │
  ├── 提取 data.Response.ResultFile3Ds[]
  │   遍历每个文件 {Type: "glb"|"obj"|"fbx", Url: "https://..."}
  │   → 构造代理URL: /api/proxy-3d?url={Url}
  │   → 组装 model_urls: {glb: proxy_url, obj: proxy_url, fbx: proxy_url}
  │
  ├── 下载 GLB → 缓存到 uploads/models/{task_id}.glb
  │
  ├── UPDATE customers:
  │   generation_count = 1, generation_status = 'completed'
  │
  ├── UPDATE generation_tasks:
  │   status = 'completed', result_url, preview_image_url, completed_at
  │
  ├── 首次完成 → INSERT messages (sender='system', content=欢迎语)
  │
  └── 返回: {status: "completed", progress: 100, model_urls,
             preview_image_url, local_model_url: "/uploads/models/{task_id}.glb"}
```

**前端轮询逻辑**（`main.js pollTaskStatus`）：

```javascript
// 每 5 秒轮询
pollInterval = setInterval(async () => {
    const resp = await fetch('/api/task-status/' + taskId);
    const data = await resp.json();
    if (data.status === 'completed') {
        clearInterval(pollInterval);
        // 触发 three-preview.js 监听的自定义事件
        window.dispatchEvent(new CustomEvent('model-ready', {
            detail: { modelUrl: data.local_model_url || data.model_urls.glb }
        }));
    } else if (data.status === 'failed') {
        clearInterval(pollInterval);
        showError(data.error);
    }
}, 5000);
```

### 3.2.4 模型下载（GET /api/download-model）

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 必填，任务 ID |
| `format` | string | 可选，`glb`（默认）/ `obj` / `fbx` |

**下载优先级**：
1. 本地缓存命中：`uploads/models/{task_id}.glb` → 直接 `send_file`
2. 本地缓存未命中：查 DB `result_url` → `requests.get(原始URL)` → 流式返回

### 3.2.5 CORS 代理（GET /api/proxy-3d）

由于混元3D返回的模型文件 URL 可能存在跨域限制，前端 Three.js GLTFLoader 无法直接加载。解决方案：后端代理转发。

```
GET /api/proxy-3d?url=https://cos.ap-guangzhou.myqcloud.com/model.glb
  → requests.get(url)
  → 返回 content + Headers:
      Content-Type: model/gltf-binary
      Access-Control-Allow-Origin: *
      Cache-Control: public, max-age=86400
```

此端点被 `track_traffic` 中间件豁免统计。

### 3.2.6 双节点代理模式

当 `config.py` 中 `HUNYUAN_PROXY_URL` 非空时，`app.py` 自动切换路由：

```
直连模式（默认）:
  POST https://api.ai3d.cloud.tencent.com/v1/ai3d/submit
  Header: Authorization: <API_KEY>

代理模式（HUNYUAN_PROXY_URL 设置后）:
  POST {HUNYUAN_PROXY_URL}/proxy/submit
  Header: X-Proxy-Secret: <HUNYUAN_PROXY_SECRET>
```

请求经 CloudFlare Tunnel → 香港轻量服务器 `hk_proxy.py` → 添加 `Authorization` header → 转发混元3D API。利用香港到腾讯云的低延迟优势（< 10ms vs 美西 > 150ms）。

## 3.3 聊天/消息系统

### 3.3.1 消息数据模型

```
messages 表:
  sender ∈ {'customer', 'admin', 'system'}
  message_type: 'text' | 'image'
  image_path: 图片路径（uploads/chat/xxx.jpg）
  is_read: 0 | 1（仅 customer 方向标记，admin 回复默认已读）
```

### 3.3.2 客户端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/messages` | GET | 获取当前客户全部消息（按 `created_at` 升序） |
| `/api/messages` | POST | 发送消息，支持 JSON `{content, image_path?}` 或 FormData |
| `/api/upload-chat-image` | POST | 上传聊天图片（≤ 32MB），返回 `{ok, image_path}` |
| `/api/quick-replies` | GET | 返回 6 条预设快捷回复模板 |
| `/api/notifications` | GET | 返回 `{unread_count, has_completed_model, latest_task_id}` |

**快捷回复模板（6条预设）**：
1. "Can I see more examples of your work?"
2. "Can you modify the design — change colors or add details?"
3. "What's the production timeline and shipping cost?"
4. "Do you ship internationally? What about customs?"
5. "How do I place an order? What payment methods do you accept?"
6. "What's your minimum order quantity and bulk pricing?"

### 3.3.3 管理端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/admin/login` | POST | `{password}` 匹配 `ADMIN_PASSWORD` |
| `/api/admin/logout` | POST | 清除 `session.admin_logged_in` |
| `/api/admin/customers` | GET | 客户列表，含子查询未读消息数 + 最后消息时间 |
| `/api/admin/messages/<customer_id>` | GET | 获取某客户消息列表，同时 `UPDATE SET is_read=1` |
| `/api/admin/reply` | POST | 管理员回复，支持文本+图片 |
| `/api/admin/customer/<customer_id>` | GET | 单个客户全部字段 |
| `/api/admin/customer/models` | GET | 某客户已完成模型任务列表 |
| `/api/admin/customer/update` | POST | 编辑可编辑字段（tag/whatsapp/company/country/phone） |
| `/api/admin/unread-count` | GET | 全局未读消息数（豁免流量统计） |

**客户列表排序逻辑**：

```sql
SELECT c.*,
  (SELECT COUNT(*) FROM messages m
   WHERE m.customer_id=c.id AND m.sender='customer' AND m.is_read=0
  ) AS unread_count,
  (SELECT MAX(created_at) FROM messages m
   WHERE m.customer_id=c.id
  ) AS last_msg_time
FROM customers c
ORDER BY last_msg_time DESC NULLS LAST
```

**客户可编辑字段**：`tag`（warm/hot/cold）、`whatsapp`、`company`、`country`、`phone`。`name`、`email`、`generation_count`、`generation_status` 为只读字段。

## 3.4 管理后台

### 3.4.1 三栏布局

| 面板 | 宽度 | 刷新频率 | 核心交互 |
|------|------|---------|---------|
| 左侧：客户列表 | 280px | 4秒轮询 | 搜索过滤、点击选中、未读角标、tag 颜色标签 |
| 中间：聊天面板 | flex:1 | 选中客户时加载 | 气泡样式、图片灯箱、快捷回复按钮、图片上传 |
| 右侧：详情面板 | flex:1 | 点击客户时加载 | Detail 标签（行内编辑）+ Traffic 标签（Chart.js 图表） |

### 3.4.2 Detail 标签功能

- **行内编辑**：点击字段值 → 变为 input → 修改 → 点击 Save 按钮 → `POST /api/admin/customer/update`
- **模型列表**：表格展示已完成任务（task_id + 下载链接 + 完成时间），`GET /api/admin/customer/models`

### 3.4.3 Traffic 标签功能

**API**：`GET /api/admin/traffic`

**返回数据结构**：

```json
{
  "total_pv": 1234,
  "today_pv": 56,
  "today_uv": 12,
  "daily_pv": [{"date": "2026-05-26", "count": 45}, ...],
  "page_distribution": [{"page": "/generate", "count": 320}, ...],
  "recent_10": [{"page": "/", "ip": "1.2.3.4", "created_at": "..."}, ...]
}
```

**可视化**（Chart.js）：
- **7天 PV 折线图**：`daily_pv` 数据，X 轴日期 / Y 轴 PV 数
- **页面分布环形图**（Doughnut）：`page_distribution` TOP 10
- **统计卡片**：总 PV、今日 PV、今日 UV（COUNT DISTINCT ip）
- **最近访问表格**：`recent_10` 最近 10 条记录

## 3.5 流量统计中间件

### 3.5.1 实现机制

```python
@app.before_request
def track_traffic():
    # 豁免路径
    EXEMPT_PREFIXES = ("/static", "/uploads", "/api/task-status",
                        "/api/proxy-3d", "/api/admin/unread-count")

    if not request.path.startswith(EXEMPT_PREFIXES):
        INSERT INTO traffic (page, ip, user_agent, date, referrer, customer_id)
```

### 3.5.2 去重策略

**每日 UV 去重**：查询时使用 `COUNT(DISTINCT ip)` + `WHERE date = 'YYYY-MM-DD'`。

没有在写入时做实时去重（即同一 IP 同一天访问同一页面可能产生多条记录），去重逻辑仅在 `/api/admin/traffic` 查询时使用 `DISTINCT` 完成，避免复杂的写入时去重逻辑。

### 3.5.3 豁免路径

以下频繁轮询 / 大流量端点不计入 traffic：

| 豁免路径 | 原因 |
|----------|------|
| `/static/*` | 静态资源 |
| `/uploads/*` | 上传文件 |
| `/api/task-status/*` | 前端每5秒轮询，量大且无分析价值 |
| `/api/proxy-3d` | 代理下载模型文件 |
| `/api/admin/unread-count` | 管理后台每4秒轮询 |



---


# 第 4 章：技术架构与实现决策

## 4.1 系统分层架构

```
┌─────────────────────────────────────────────────────┐
│                     客户端层                          │
│  浏览器: Vanilla JS + Three.js + Chart.js + GIS     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS (CloudFlare CDN)
┌──────────────────────▼──────────────────────────────┐
│                   Web 应用层                          │
│  Flask 3.x (app.py: ~1276行)                         │
│  ├── @before_request: auto_login + track_traffic     │
│  ├── Blueprint-less 路由（全部集中 app.py 内）        │
│  ├── 内存字典 verification_codes（验证码）            │
│  ├── 集合 verified_sessions（已登录 session 追踪）     │
│  └── mailer.py: SMTP SSL → 阿里云企业邮箱            │
└──────────┬─────────────────────────┬────────────────┘
           │ SQLite (WAL)            │ requests HTTP
┌──────────▼──────────┐  ┌──────────▼─────────────────┐
│     数据存储层       │  │     外部 API 层              │
│  data.db (WAL模式)   │  │  api.ai3d.cloud.tencent.com │
│  ├── customers       │  │  (腾讯混元3D API)            │
│  ├── messages        │  │  oauth2.googleapis.com      │
│  ├── generation_tasks│  │  (Google TokenInfo)         │
│  └── traffic         │  │  [可选] hk_proxy.py         │
│  flask_session/  (FS)│  │   (香港轻量代理节点)         │
└──────────────────────┘  └────────────────────────────┘
```

## 4.2 数据库设计

### 4.2.1 核心表 ER 关系

```
customers (1) ──┬── (N) messages          (sender/receiver)
                ├── (N) generation_tasks   (owner)
                └── (N) traffic            (可选关联)
```

### 4.2.2 customers 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | TEXT | PRIMARY KEY | `urlsafe_encode(email)`，确保唯一且可逆 |
| `email` | TEXT | NOT NULL UNIQUE | 登录邮箱 |
| `name` | TEXT | — | 用户名称（Google OAuth 从 token 中提取） |
| `phone` | TEXT | — | 手机号（手动填写，管理后台可编辑） |
| `company` | TEXT | — | 公司名 |
| `country` | TEXT | — | 国家 |
| `whatsapp` | TEXT | — | WhatsApp 号码 |
| `tag` | TEXT | — | 客户标签：`warm` / `hot` / `cold` |
| `avatar` | TEXT | — | Google OAuth 头像 URL |
| `google_id` | TEXT | — | Google 账户 sub |
| `generation_count` | INTEGER | DEFAULT 0 | 已生成次数（硬限制 ≤1） |
| `generation_status` | TEXT | DEFAULT 'idle' | `idle` / `in_progress` / `completed` |
| `persistent_token` | TEXT | — | 30天免登录 token |
| `token_expires` | TEXT | — | token 过期时间（ISO 格式） |
| `created_at` | TEXT | — | 注册时间 |
| `updated_at` | TEXT | — | 最后更新时间 |

**ID 策略**：使用 `email` 的 URL-safe base64 编码作为主键，而非自增 INTEGER。此设计的意图是：邮箱本身具有唯一性，`urlsafe_encode` 确保 ID 不含特殊字符，且可逆向解码为原始 email。

### 4.2.3 messages 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 消息 ID |
| `customer_id` | TEXT | FK → customers.id | 所属客户 |
| `sender` | TEXT | NOT NULL | `customer` / `admin` / `system` |
| `content` | TEXT | — | 消息文本 |
| `message_type` | TEXT | DEFAULT 'text' | `text` / `image` |
| `image_path` | TEXT | — | 图片存储路径 |
| `is_read` | INTEGER | DEFAULT 0 | 客户消息是否已被管理员阅读 |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | 发送时间 |

### 4.2.4 generation_tasks 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 任务 ID |
| `customer_id` | TEXT | FK → customers.id | 所属客户 |
| `input_type` | TEXT | NOT NULL | `image` / `text` |
| `job_id` | TEXT | UNIQUE | 混元3D API 返回的 JobId |
| `status` | TEXT | DEFAULT 'pending' | `pending` / `running` / `completed` / `failed` |
| `input_image_path` | TEXT | — | 上传图片本地路径 |
| `input_prompt` | TEXT | — | 文字描述 |
| `result_url` | TEXT | — | 模型文件原始 URL（JSON string） |
| `preview_image_url` | TEXT | — | 预览图 URL |
| `error_message` | TEXT | — | 失败原因 |
| `completed_at` | TEXT | — | 完成时间 |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | 最后更新时间 |

### 4.2.5 traffic 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 记录 ID |
| `page` | TEXT | NOT NULL | 访问路径 |
| `ip` | TEXT | — | 客户端 IP（CloudFlare → `CF-Connecting-IP`） |
| `user_agent` | TEXT | — | User-Agent 字符串 |
| `date` | TEXT | — | 访问日期（`YYYY-MM-DD`） |
| `referrer` | TEXT | — | Referer |
| `customer_id` | TEXT | — | 关联客户 ID（登录状态下记录） |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | 访问时间 |

### 4.2.6 渐进式 Schema 迁移

系统未使用 Alembic 等正式迁移工具，而是采用"append-only"的渐进式迁移策略：

```python
def init_db():
    conn.executescript(CREATE_TABLES_SQL)  # 首次初始化

# 后续按需追加
try:
    conn.execute("ALTER TABLE customers ADD COLUMN tag TEXT")
except sqlite3.OperationalError:
    pass  # 字段已存在则跳过

try:
    conn.execute("ALTER TABLE messages ADD COLUMN image_path TEXT")
except sqlite3.OperationalError:
    pass
```

迁移在 `app.py` 启动时自动执行，保证向前兼容。每次部署前手动检查是否有新增的 `ALTER TABLE` 语句需要同步到生产数据库。

## 4.3 Session 管理

### 4.3.1 配置

```python
SESSION_TYPE = "filesystem"          # 文件系统存储
SESSION_PERMANENT = True             # 持久化（非浏览器关闭即失效）
PERMANENT_SESSION_LIFETIME = 30天    # 与免登录 token 有效期一致
```

Session 文件存储于 `flask_session/` 目录，文件名格式为 `session_{sid}`，内容为 pickle 序列化的 session 字典。

### 4.3.2 多身份隔离

客户和管理员通过独立字段实现身份隔离：

| 维度 | 客户 | 管理员 |
|------|------|--------|
| Session 字段 | `verified`、`customer_id` | `admin_logged_in` |
| 免登录 | ✅ 支持（auto_login cookie + DB token） | ❌ 不支持 |
| 路由守卫 | `is_logged_in()` 检查 | `/api/admin/*` 检查 `admin_logged_in` |
| 登出 | 清理 cookie + DB token | 清除 `admin_logged_in` |

### 4.3.3 `verified_sessions` 全局集合

```python
verified_sessions = set()  # 存储已登录 session.sid
```

登录时 `verified_sessions.add(session.sid)`，登出时 `verified_sessions.discard(session.sid)`。`before_request` 中间件用于 `is_logged_in()` 的快速查找。

## 4.4 邮件发送逻辑（mailer.py）

### 4.4.1 SMTP 配置

```python
smtplib.SMTP_SSL(
    host="smtp.mxhichina.com",  # 阿里云企业邮箱
    port=465,
    context=ssl.create_default_context()
)
```

发送账号：`dulizhan@showlovein.com`（阿里云企业邮箱）。

### 4.4.2 邮件模板

HTML 邮件格式（内联 CSS）：

```html
┌─────────────────────────────────────────┐
│  [紫色渐变头部图片/背景]                  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  白色卡片                           │  │
│  │  "Your verification code is:"      │  │
│  │  [   大号居中蓝色数字 6 位验证码   ]  │  │
│  │  "This code expires in 5 minutes." │  │
│  │  "If you didn't request..."        │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [页脚：InflatableModel.CN copyright]    │
└─────────────────────────────────────────┘
```

### 4.4.3 错误处理

```python
try:
    server.sendmail(sender, to, msg.as_string())
    return True
except Exception as e:
    print(f"[MAIL ERROR] Failed to send: {e}")
    return False
```

失败时静默降级（不阻断登录流程），验证码在终端以 `[DEV MODE]` 前缀打印，开发环境中可直接从控制台获取验证码。

## 4.5 架构决策与权衡

### 4.5.1 SQLite 而非 MySQL/PostgreSQL

| 维度 | SQLite | MySQL/PostgreSQL |
|------|--------|------------------|
| 运维成本 | 零（单文件） | 需独立进程、安装、配置、备份策略 |
| 并发能力 | WAL 模式下中等读写并发 | 强 |
| 备份 | `cp data.db` | 需 dump 或快照 |
| 适用规模 | 日 PV < 10K | 任意规模 |

**决策**：当前业务规模下（个人建站、小批量定制业务），SQLite 的零运维优势远超并发劣势。WAL 模式保证了读写不互斥。若未来日 PV 超过 10K 或有水平扩展需求时，迁移至 PostgreSQL 的成本可控（SQLAlchemy 或直接改 `get_db()` 连接串）。

### 4.5.2 每用户仅 1 次 3D 生成

**约束代码**：

```python
if row["generation_count"] >= 1:
    return 403, "Only one generation is allowed."
```

**决策依据**：
1. **成本控制**：混元3D API 调用有费用，无限制可能导致滥用
2. **业务逻辑**：充气模型定制业务中，客户通常需要 1 个核心设计确认后沟通修改，而非多次重新生成
3. **转化引导**：生成完成后自动推送系统消息和聊天引导，将用户导入人工服务环节

### 4.5.3 同步 requests 而非异步（httpx/aiohttp）

| 维度 | requests (sync) | httpx (async) |
|------|----------------|---------------|
| 依赖数 | 1（标准库级） | 额外 asyncio 生态 |
| 代码复杂度 | 简单线性 | 需 async/await 重构全链路 |
| Gunicorn 兼容 | 原生支持 sync worker | 需 uvicorn + asgi middleware |

**决策**：混元3D API 的 submit 和 query 调用均在用户请求的响应周期内完成，使用 Gunicorn 的多 worker 能覆盖中等并发。异步带来的收益（连接复用、非阻塞 I/O）在当前并发水平下不显著。**若未来需要同时处理 100+ 并发 API 调用时，可平滑迁移到 `httpx.AsyncClient`。**

### 4.5.4 双节点代理模式 vs 直连混元 API

| 方案 | 美西→混元延迟 | 复杂度 | 成本增量 |
|------|-------------|--------|---------|
| 直连（默认） | ~200ms（跨国） | 零 | $0 |
| 代理（香港节点） | < 10ms（香港→腾讯云） | hk_proxy.py + Tunnel | ¥25/月 |

**决策**：默认直连即可（200ms 延迟对 submit 请求可接受）。代理模式为可选增强，当用户反馈生成响应过慢时启用，通过 `HUNYUAN_PROXY_URL` 环境变量零代码切换。

### 4.5.5 文件型 Session 而非 Redis

| 维度 | filesystem | Redis |
|------|-----------|-------|
| 运维 | 零依赖 | 需 Redis 进程 |
| 性能 | 磁盘 I/O，毫秒级 | 内存，微秒级 |
| 跨节点共享 | 否（单机） | 是 |
| 双节点适用 | 需共享存储（NFS） | 原生支持 |

**决策**：当前主站单节点运行，filesystem 足够。**双节点部署时，需将 `flask_session/` 目录放在主站节点的本地磁盘上（API 代理节点不运行 Flask 应用，无需 session）。** 若未来扩展到多主站节点，替换 Session 后端为 Redis 仅需改一行 `SESSION_TYPE` 配置。

## 4.6 安全设计要点

| 维度 | 实现 |
|------|------|
| **CSRF 防护** | Flask-WTF 未引入；所有状态变更 API 需登录验证（session 校验），Google OAuth 使用 id_token 服务端验证 |
| **XSS 防护** | Jinja2 默认 HTML 转义（`{{ }}`），用户输入不直接插 HTML |
| **SQL 注入** | 全部使用参数化查询（`conn.execute("SELECT ... WHERE id=?", (param,))`），无字符串拼接 SQL |
| **上传安全** | 仅允许白名单图片后缀；`MAX_CONTENT_LENGTH=32MB`；图片文件名通过 `secure_filename()` 处理 |
| **密码暴露** | API Key、SMTP 密码、Admin 密码默认硬编码于 `config.py`，部署前需迁移至 `.env` 文件（通过 `python-dotenv` 或直接 `export`） |
| **HTTPS** | CloudFlare 终止 TLS → `X-Forwarded-Proto` 回源 HTTP（Nginx 配置 `CF-Connecting-IP` 透传） |



---


# 第 5 章：部署与运维方案

## 5.1 双节点混合部署架构

```
                        ┌──────────────────────┐
                        │     用户（全球）       │
                        └──────────┬───────────┘
                                   │ DNS
                        ┌──────────▼───────────┐
                        │   CloudFlare CDN      │
                        │   • DNS 托管           │
                        │   • 静态资源缓存       │
                        │   • TLS 终止           │
                        │   • DDoS 防护          │
                        │   • CF-Connecting-IP   │
                        └─────┬──────────┬──────┘
                              │          │
                    HTTP/2    │          │ CF Tunnel
              ┌───────────────▼──┐  ┌───▼──────────────────┐
              │  美西 VPS (Vultr) │  │  香港轻量 (阿里云)     │
              │  $6/月            │  │  ¥25/月               │
              │                   │  │                       │
              │  ┌─────────────┐  │  │  ┌─────────────────┐  │
              │  │ Nginx       │  │  │  │ cloudflared     │  │
              │  │ :80/:443    │  │  │  │ (Tunnel 守护)   │  │
              │  └─────┬───────┘  │  │  └────────┬────────┘  │
              │        │          │  │           │           │
              │  ┌─────▼───────┐  │  │  ┌────────▼────────┐  │
              │  │ Gunicorn    │  │  │  │ hk_proxy.py     │  │
              │  │ :8000       │  │  │  │ Flask :5001      │  │
              │  │ 2-4 workers │  │  │  │ → 混元3D API    │  │
              │  └─────┬───────┘  │  │  └─────────────────┘  │
              │        │          │  │                       │
              │  ┌─────▼───────┐  │  └───────────────────────┘
              │  │ SQLite      │  │
              │  │ data.db     │  │
              │  │ + Session/  │  │
              │  └─────────────┘  │
              └───────────────────┘
```

### 5.1.1 节点职责分工

| 节点 | 角色 | 运行组件 | 关键职责 |
|------|------|---------|---------|
| **美西 VPS** | 主站节点 | Nginx + Gunicorn(Flask) + SQLite + Session | 全部 Web 服务、数据库读写、用户认证、轮询、聊天、管理后台 |
| **香港轻量** | API 代理节点 | cloudflared + hk_proxy.py(Flask) | 转发混元3D API 请求，利用香港到腾讯云的低延迟 |
| **CloudFlare** | CDN/网关 | DNS + CDN + Tunnel | 全球加速、TLS、DDoS 防护、静态资源缓存 |

### 5.1.2 请求路由

```
# 直连模式（默认，HUNYUAN_PROXY_URL 为空）
用户 → CF → 美西 VPS → requests.get("https://api.ai3d.cloud.tencent.com")

# 代理模式（HUNYUAN_PROXY_URL 设置后）
用户 → CF → 美西 VPS → CF Tunnel → 香港轻量 hk_proxy.py → 混元3D API
                                      ↑ 添加 Authorization header
```

### 5.1.3 月费汇总

| 服务 | 规格 | 月费 | 用途 |
|------|------|------|------|
| Vultr VPS (美西) | 1vCPU / 1GB / 25GB SSD | $6.00 | 主站 Web 服务器 |
| 阿里云轻量 (香港) | 2vCPU / 0.5GB / 20GB ESSD / 200M | ¥25.00 (~$3.55) | API 代理节点 |
| CloudFlare | Free Plan | $0 | DNS + CDN + Tunnel + DDoS |
| **合计** | — | **~$9.55/月** | — |

## 5.2 主站节点部署（美西 Vultr）

### 5.2.1 systemd 服务配置（`deploy/inflatable-us.service`）

```ini
[Unit]
Description=InflatableModel.CN Flask App (US)
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/inflatable-website
Environment="PATH=/opt/inflatable-website/venv/bin"
Environment="HUNYUAN_API_KEY=sk-xxx"
Environment="HUNYUAN_PROXY_URL="                    # 空 = 直连，填 URL = 代理模式
Environment="HUNYUAN_PROXY_SECRET="
Environment="MAIL_PASSWORD=xxx"
Environment="FLASK_SECRET_KEY=xxx"
Environment="GOOGLE_CLIENT_ID=xxx.googleusercontent.com"
Environment="ADMIN_PASSWORD=xxx"
ExecStart=/opt/inflatable-website/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/inflatable/gunicorn-access.log \
    --error-logfile /var/log/inflatable/gunicorn-error.log \
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Gunicorn 参数说明**：
- `--workers 4`：1vCPU 的 4 worker（I/O 密集型，可适当过量分配）
- `--timeout 120`：120 秒超时，覆盖混元 API 最长生成时间
- `--bind 127.0.0.1:8000`：仅监听本地，由 Nginx 反向代理

### 5.2.2 Nginx 配置（`deploy/nginx-us.conf`）

```nginx
server {
    listen 80;
    server_name inflatablemodel.cn www.inflatablemodel.cn;

    # CloudFlare Real IP
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 103.21.244.0/22;
    # ... 全部 CF IP 范围
    real_ip_header CF-Connecting-IP;

    client_max_body_size 32M;

    # 静态文件缓存
    location /static/ {
        alias /opt/inflatable-website/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    location /uploads/ {
        alias /opt/inflatable-website/uploads/;
        expires 7d;
    }

    # API 和动态请求
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

### 5.2.3 部署脚本（`deploy/deploy-us.sh`）

```bash
#!/bin/bash
# 1. 安装系统依赖
apt update && apt install -y python3 python3-venv nginx

# 2. 创建应用目录
mkdir -p /opt/inflatable-website /var/log/inflatable
chown -R www-data:www-data /opt/inflatable-website

# 3. 部署代码（rsync 或 git pull 到 /opt/inflatable-website）

# 4. 创建虚拟环境 + 安装依赖
python3 -m venv /opt/inflatable-website/venv
/opt/inflatable-website/venv/bin/pip install -r requirements.txt

# 5. 复制 systemd + nginx 配置
cp deploy/inflatable-us.service /etc/systemd/system/
cp deploy/nginx-us.conf /etc/nginx/sites-available/inflatable

# 6. 启用服务
ln -sf /etc/nginx/sites-available/inflatable /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
systemctl enable --now inflatable-us

# 7. CloudFlare DNS
# 手动在 CloudFlare Dashboard 添加 A 记录 → 美西 VPS IP
```

## 5.3 API 代理节点部署（香港阿里云轻量）

### 5.3.1 hk_proxy.py 架构

```python
# 路径：/opt/inflatable-proxy/hk_proxy.py
# Flask 应用，监听 127.0.0.1:5001

@app.route("/proxy/submit", methods=["POST"])
def proxy_submit():
    # 1. 验证 X-Proxy-Secret（防止未授权访问）
    # 2. 提取请求体 → 添加 Authorization header（API Key 从环境变量读取）
    # 3. POST https://api.ai3d.cloud.tencent.com/v1/ai3d/submit
    # 4. 返回原始响应（透传 status_code + headers + body）

@app.route("/proxy/query", methods=["POST"])
def proxy_query():
    # 同上 → POST /v1/ai3d/query
```

**代理节点不接触数据库、不处理 Session、不参与用户认证**，仅做 API 请求的加签转发。

### 5.3.2 CloudFlare Tunnel 配置

香港节点不暴露公网 IP，通过 CloudFlare Tunnel 接收来自美西主站的内部请求：

```bash
# 安装 cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared-linux-amd64.deb

# 登录授权
cloudflared tunnel login

# 创建隧道
cloudflared tunnel create inflatable-hk

# 配置 config.yml
cat > ~/.cloudflared/config.yml << EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: hk-proxy.inflatablemodel.cn
    service: http://localhost:5001
  - service: http_status:404
EOF

# 安装为 systemd 服务
cloudflared service install
systemctl enable --now cloudflared
```

**CF Tunnel 域名**：`hk-proxy.inflatablemodel.cn`（仅 CloudFlare 内部可解析，不对外暴露）。

### 5.3.3 部署脚本（`deploy/deploy-hk.sh`）

```bash
#!/bin/bash
# 1. 安装 Python3 + cloudflared
# 2. 创建 /opt/inflatable-proxy/
# 3. 部署 hk_proxy.py + requirements.txt（仅 flask + requests）
# 4. 配置 systemd service: inflatable-hk.service
# 5. 配置 CloudFlare Tunnel: hk-proxy.inflatablemodel.cn → localhost:5001
# 6. 启用自动启动
```

## 5.4 单节点回退方案

当不需要双节点部署时（节省成本、简化运维），主站直接调用混元 API：

```bash
# 美西 VPS 上：
export HUNYUAN_PROXY_URL=""        # 空值 = 直连模式
systemctl restart inflatable-us

# 香港节点可关机释放
```

**时效对比**：

| 模式 | Submit 延迟 | Query 延迟 | 额外成本 |
|------|------------|-----------|---------|
| 直连（美西→腾讯云） | ~200ms | ~200ms | $0 |
| 代理（美西→香港→腾讯云） | ~200ms + <10ms | ~200ms + <10ms | ¥25/月 |

Submit 和 Query 均为非流式请求，额外 200ms 延迟对用户体验影响极小，故直连模式为默认推荐。

## 5.5 运维注意事项

### 5.5.1 日志管理

| 日志 | 路径 | 轮转 |
|------|------|------|
| Gunicorn 访问日志 | `/var/log/inflatable/gunicorn-access.log` | `logrotate` 按天 + 保留 30 天 |
| Gunicorn 错误日志 | `/var/log/inflatable/gunicorn-error.log` | 同上 |
| Nginx 访问日志 | `/var/log/nginx/inflatable-access.log` | 同上 |

### 5.5.2 数据备份

```bash
# backup.py 提供自动备份
python backup.py  # → backups/data-v{timestamp}.db
```

建议 crontab 每日定时备份：
```cron
0 3 * * * cd /opt/inflatable-website && python backup.py
```

### 5.5.3 监控检查点

| 检查项 | 方法 | 正常阈值 |
|--------|------|---------|
| Flask 应用存活 | `systemctl status inflatable-us` | active (running) |
| Gunicorn worker 数 | `ps aux | grep gunicorn | wc -l` | ≥ 4（含 master） |
| SQLite WAL 膨胀 | `ls -lh data.db-wal` | < 10MB |
| /api/me 响应 | `curl localhost:8000/api/me` | HTTP 200 |
| 混元 API 连通 | `curl -H "Authorization: $KEY" https://api.ai3d.cloud.tencent.com/v1/ai3d/submit -d '{"Model":"3.0","Prompt":"test"}'` | HTTP 200（含 JobId） |

### 5.5.4 证书续期

CloudFlare 免费提供自动 TLS 证书，无需手动 renew。若使用自签证书 → 切换 CloudFlare 加密模式为 "Full (strict)"。

### 5.5.5 环境变量敏感信息管理

部署前将 `config.py` 中的硬编码凭据迁移为环境变量：

```bash
# 在 /etc/environment 或 systemd EnvironmentFile 中：
HUNYUAN_API_KEY=sk-xxx
MAIL_PASSWORD=xxx
FLASK_SECRET_KEY=xxx
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
ADMIN_PASSWORD=xxx
HUNYUAN_PROXY_URL=
HUNYUAN_PROXY_SECRET=xxx
```

禁止将包含凭据的 `.env` 或 `EnvironmentFile` 提交到 Git 仓库。`.env.example`（不含真实凭据）已随项目提供。

## 5.6 部署检查清单

| 步骤 | 命令/操作 | 验收标准 |
|------|----------|---------|
| 1. 系统依赖 | `apt install python3 python3-venv nginx` | 版本 ≥ 3.9 / ≥ 1.18 |
| 2. 代码部署 | `rsync -avz ./ user@host:/opt/inflatable-website/` | 文件完整无遗漏 |
| 3. 虚拟环境 | `pip install -r requirements.txt` | 4 个包安装成功 |
| 4. 配置文件 | 复制 `deploy/*.service` + `deploy/*.conf` + 设置环境变量 | `systemctl start` 不报错 |
| 5. Nginx | `nginx -t` + `systemctl reload nginx` | syntax ok |
| 6. 服务启动 | `systemctl start inflatable-us` | `curl localhost:8000/` 返回 HTML |
| 7. DNS | CloudFlare Dashboard 添加 A 记录 | `dig inflatablemodel.cn` 返回 CF IP |
| 8. SSL | CloudFlare "Full" 模式 | `curl -I https://inflatablemodel.cn` 返回 200 |
| 9. 邮箱 | `/api/login` → 邮箱收到验证码 | 验证码邮件接收 < 30s |
| 10. 3D 生成 | 提交测试图片 → 轮询 → 下载 | 全链路通畅 |
| 11. （可选）香港代理 | 设置 `HUNYUAN_PROXY_URL` → 重启 | proxy/health 返回 `ok` |
