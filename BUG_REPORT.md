# Bug Report — inflatablemodel.com.cn

> 测试时间: 2026-06-09
> 测试环境: Render.com (live), 本地代码审查
> 测试范围: 全功能遍历 — 买家端 + 管理后台 + API

---

## 🔴 P0 — 严重 (影响核心业务)

### BUG-01: 管理员密码硬编码为 `admin123`，无修改入口

**位置**: `config.py:49`
**描述**: `ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")` — 默认密码 `admin123` 写死在代码中，且无任何 UI 入口修改密码。任何人查看 GitHub 源码即可获得管理员密码，导致后台完全暴露。

**复现步骤**:
```bash
curl -s -X POST "https://inflatablemodel.com.cn/api/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"admin123"}'
# 返回 {"ok":true}
```

**影响范围**: 管理后台完全沦陷 — 可查看所有客户信息、聊天记录、发送伪造消息

**修复建议**:
1. 在 Render 环境变量中设置自定义 ADMIN_PASSWORD
2. 添加密码修改功能
3. 添加登录失败次数限制（防暴力破解）

---

### BUG-02: 快速回复 API 无鉴权，任何人可增删

**位置**: `app.py:1049-1082`
**描述**: `/api/quick-replies` 的 GET/POST/DELETE 均无任何权限检查，任何人无需登录即可添加或删除快速回复内容，可能导致 XSS 攻击或内容篡改。

**复现步骤**:
```bash
# 无需登录，直接插入
curl -s -X POST "https://inflatablemodel.com.cn/api/quick-replies" \
  -H "Content-Type: application/json" \
  -d '{"content":"<script>alert(1)</script>"}'
# 返回 {"ok":true}

# 无需登录，直接删除
curl -s -X DELETE "https://inflatablemodel.com.cn/api/quick-replies/0"
```

**影响范围**: 快速回复数据可被任意篡改，恶意内容可能通过聊天界面注入

**修复建议**: 添加 `@admin_required` 装饰器到 POST 和 DELETE 方法

---

### BUG-03: 买家聊天图片上传缺少文件大小限制

**位置**: `app.py:953-975`
**描述**: `/api/upload-chat-image` 没有检查上传图片文件大小。虽然有 `MAX_CONTENT_LENGTH = 32MB` 全局限制，但 32MB 对聊天图片来说过大，恶意用户可上传大文件耗尽 Render 免费磁盘。

**影响范围**: 磁盘空间耗尽导致服务崩溃

**修复建议**: 在上传处理中增加大小检查（如 5MB 上限）

---

## 🟡 P1 — 中等 (影响用户体验)

### BUG-04: admin.html 代码三重冗余，维护困难

**位置**: `templates/admin.html` 全文
**描述**: 由于历史合并问题，`admin.html` 中核心 JavaScript 代码（`loadCustomers`, `selectCustomer`, `loadMessages`, `sendAdminReply`, `handleAdminImage` 等）被定义了 **3 次**（行 429-636, 685-892, 1058-1265），分别位于 3 个 `<script>` 块中。浏览器执行时最后一个定义覆盖前面的，但：
1. 3 个 `<script>` 块中 `allCustomers` 变量初始化了 3 次
2. `loadCustomers()` 被 `setInterval` 和底部初始化调用了 3 次（每 4 秒发 3 个请求）
3. 修改代码时必须同步 3 处，容易遗漏

**影响范围**: 
- 管理后台每 4 秒发 3 倍轮询请求，浪费 API 配额
- 代码维护困难，任何修改需同步 3 处
- 网络流量 3 倍消耗

**修复建议**: 合并为单个 `<script>` 块，删除重复代码

---

### BUG-05: `/api/generate-3d` 图片上传路径变量未定义导致 500

**位置**: `app.py:711`
**描述**: 
```python
preview_url = url_for("uploaded_file", filename=filename, _external=True) if image_path else None
```
但 `filename` 变量名是在 `if image_file` 分支内部定义的（行 679）。当用户**仅上传图片**时 `filename` 存在，但当**仅提供文字描述**时，代码在行 711 引用了未定义的 `filename`，会导致 `NameError`。

实际流程：用户仅提供 description → `image_file` 为 None → `filename` 未定义 → 行 711 `NameError`

**注意**: 当 `image_file` 为 None 时，行 668 的 `if not image_file and not description` 不会触发（因为 description 有值），代码继续执行到行 711。

**影响范围**: 纯文字描述的 3D 生成请求会 500 崩溃

**复现步骤**:
```
POST /api/generate-3d (multipart/form-data)
description="A red balloon" (无图片)
```

**修复建议**: 行 711 改为 `if image_path else None` 中增加 `filename` 的安全检查

---

### BUG-06: 买家消息已读状态未同步给管理端

**位置**: `app.py:982-1006`
**描述**: 买家通过 `/api/messages` GET 获取消息时，没有将 admin/system 发的消息标记为已读。这意味着：
1. 管理员发送的消息对买家永远显示未读
2. 管理员无法知道买家是否已读自己的消息

**影响范围**: 管理员和买家的消息已读状态不互通

**修复建议**: 买家 GET messages 时，将 `sender IN ('admin','system')` 的消息标记为 `is_read=1`

---

### BUG-07: admin_chat.py 数据库连接未正确关闭

**位置**: `admin_chat.py:29-41`, `admin_chat.py:48-56`
**描述**: `_ensure_admin_logs_table()` 和 `log_admin_action()` 手动创建 `sqlite3.connect()` 连接，用完后调用 `conn.close()`。但 `log_admin_action()` 中的异常路径可能跳过 `conn.close()`。

更严重的是，`api_quick_replies`（`app.py:1057-1068`）直接调用 `get_db()` 返回的连接没有用 `with` 包裹，也没有显式关闭，导致连接泄漏。

**影响范围**: SQLite 连接泄漏，高并发时可能触发 "database is locked" 错误

**修复建议**: 所有数据库操作使用 `with get_db() as conn:` 上下文管理器

---

### BUG-08: traffic 表的 `date` 列可能为空

**位置**: `app.py:260-272`
**描述**: `track_traffic()` 在 `@app.before_request` 中写入 traffic 记录，但使用 `today = datetime.now().strftime("%Y-%m-%d")` 设置 `date` 列。而 `_ensure_date_column()` 中的 `ALTER TABLE` 设置了 `DEFAULT ''`。对于 `ALTER TABLE` 之前已存在的行，`date` 列为空字符串，不会匹配 `date>=?` 的查询条件。

**影响范围**: 早期流量数据在统计中被遗漏

**修复建议**: 使用 `COALESCE(date, DATE(created_at))` 作为查询字段，或在 `track_traffic` 中确保 `date` 始终有值

---

## 🟢 P2 — 低 (体验优化)

### BUG-09: `/verify` 页面无鉴权保护

**位置**: `app.py:295-298`
**描述**: `/verify` 页面不需要任何 session 状态即可访问。如果用户直接访问 `/verify` 且没有 `contact_email`，页面会显示空邮箱或异常状态。

**影响范围**: 低 — 不影响功能，但体验不佳

**修复建议**: 检查 session 中是否有验证流程进行中，否则重定向到 `/login`

---

### BUG-10: 买家 `api/me` 返回的 `generation_done` 字段缺失

**位置**: `app.py:1125-1134`
**描述**: `/api/me` 只返回 `logged_in`, `name`, `email`，缺少 `generation_done` 和 `generation_status` 字段。前端可能依赖这些信息来决定跳转目标。

**影响范围**: 低 — 前端有独立的通知轮询机制

**修复建议**: 在 `/api/me` 响应中增加 `generation_status` 字段

---

### BUG-11: messages.html 的图片 lightbox 存在 XSS 风险

**位置**: `templates/messages.html:484`
**描述**:
```javascript
'openLightbox(\'' + (m.image_path || '').replace(/"/g, '&quot;') + '\')'
```
`image_path` 的单引号未被转义。如果攻击者通过 API 发送 `image_path` 包含 `')` 的值，可以注入 JavaScript 代码。

**影响范围**: 低 — 需要绕过服务端验证，但理论上可行

**修复建议**: 对 `image_path` 使用 `escapeAttr()` 函数或改用 data 属性

---

### BUG-12: admin.html 的 `</script>` 重复关闭标签

**位置**: `templates/admin.html:1056-1057`
**描述**: 行 1056 有 `</script>`，行 1057 又有一个 `</script>`。这是之前 HTML 结构修复的遗留问题。

**影响范围**: 低 — 浏览器容错处理，但不符合 HTML 规范

**修复建议**: 删除多余的 `</script>` 标签

---

### BUG-13: 流量统计的环比/同比在无对比数据时显示 `+100%`

**位置**: `admin_traffic.py:87-89`
**描述**:
```python
def _calc_growth(current, previous):
    if previous == 0: return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)
```
当上一周期 PV=0 且本周有流量时，环比显示 `+100%`，这在统计上不准确。

**影响范围**: 低 — 统计准确性问题

**修复建议**: 当 previous=0 时返回 `N/A` 或 `--` 而非 `100%`

---

### BUG-14: 管理员双重退出按钮

**位置**: `templates/admin.html:345, 353`
**描述**: 顶部导航栏和客户列表面板各有一个退出按钮，功能完全相同。

**影响范围**: 低 — UI 冗余

**修复建议**: 删除客户列表面板中的退出按钮，保留顶部导航栏的

---

## 📊 Bug 汇总

| 级别 | 数量 | Bug 编号 |
|------|------|----------|
| 🔴 P0 | 3 | BUG-01, BUG-02, BUG-03 |
| 🟡 P1 | 5 | BUG-04, BUG-05, BUG-06, BUG-07, BUG-08 |
| 🟢 P2 | 6 | BUG-09~14 |
| **合计** | **14** | |

---

## ⚡ 建议优先修复顺序

1. **BUG-01** (管理员密码) → Render 环境变量中设置 ADMIN_PASSWORD
2. **BUG-02** (快速回复无鉴权) → 添加 admin_required
3. **BUG-05** (文字生成 NameError) → 修复 filename 变量引用
4. **BUG-04** (三重冗余代码) → 合并 script 块
5. **BUG-07** (数据库连接泄漏) → 统一使用 with 上下文
