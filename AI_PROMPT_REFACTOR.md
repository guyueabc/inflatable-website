# AI 重构提示词 —— InflatableModel.CN 核心功能全面升级

> **用途**: 将此文档直接发送给 AI（如 ChatGPT、Cursor、Codex 等）即可开始执行。
> **项目路径**: `D:\2\inflatable-website`
> **技术栈**: Flask 3.0 + SQLite (WAL) + Flask-Session (filesystem) + Gunicorn + Vanilla JS + Three.js + SMTP（阿里云企业邮箱）+ CloudFlare Tunnel

---

## 项目现状总结

当前项目是一个充气模型在线定制平台。用户上传图片/文字后通过腾讯混元3D API 生成3D模型，并可与后台客服"Mia"聊天。系统含认证、3D生成、聊天消息、管理后台四大模块。

### 核心文件

| 文件 | 作用 |
|------|------|
| `app.py` | 主应用：认证、3D生成、用户聊天 API |
| `admin_chat.py` | Blueprint：后台管理员聊天管理 |
| `admin_traffic.py` | Blueprint：流量统计面板 |
| `config.py` | 集中配置：API Key、SMTP、OAuth 等 |
| `mailer.py` | SMTP 邮件发送（验证码） |
| `templates/login.html` | 登录页：邮箱验证码 + 预留 Google 按钮 |
| `templates/messages.html` | 用户聊天页：HTTP 轮询聊天 |
| `templates/generate.html` | 3D 生成页：上传图片 + 预览 |
| `templates/admin.html` | 管理后台：客户列表 + 聊天面板 |
| `requirements.txt` | `flask>=3.0, flask-session>=0.7, requests>=2.31, gunicorn>=21.2` |

### 关键 API 路由

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/login` | POST | 提交邮箱/手机→发送验证码 |
| `/api/verify` | POST | 验证6位数字验证码 |
| `/api/auth/google` | POST | Google 登录（预留但未完成） |
| `/api/messages` | GET | HTTP 轮询获取消息（每3秒） |
| `/api/messages` | POST | 发送消息 |
| `/api/generate-3d` | POST | 提交3D生成任务 |
| `/api/logout` | GET/POST | 登出并清除持久令牌 |

---

## 七大改造需求

---

## 需求一：用户聊天消息发送失败 → 彻底重构为实时通信

### 问题根因
当前聊天使用 `setInterval(loadMsgs, 3000)` HTTP短轮询，多次修复仍失败。架构层面问题：轮询与 Session 时序不保证、非实时、无连接状态管理。

### 解决方案：Flask-SocketIO 完全替换 HTTP 轮询

**新增依赖**:
```
flask-socketio>=5.3
eventlet>=0.36
```

---

### 1.1 后端改造 —— `app.py`

**步骤1**：在文件顶部增加 SocketIO 初始化
```python
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

# 在 app = Flask(__name__) 和 Session(app) 之后添加
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", manage_session=False)
```

**步骤2**：添加聊天 Socket 事件处理器（放在现有路由之后、`if __name__` 之前）
```python
# ═══════ Socket.IO Chat Events ═══════

@socketio.on("connect")
def on_connect():
    """用户连接时，如果有会话则加入专属房间"""
    cid = session.get("customer_id")
    if cid:
        join_room(f"customer_{cid}")
    if session.get("admin_logged_in"):
        join_room("admin_room")

@socketio.on("disconnect")
def on_disconnect():
    cid = session.get("customer_id")
    if cid:
        leave_room(f"customer_{cid}")
    if session.get("admin_logged_in"):
        leave_room("admin_room")

@socketio.on("send_message")
def on_send_message(data):
    """用户/管理员发送消息，广播给双方"""
    cid = session.get("customer_id")
    is_admin = session.get("admin_logged_in")
    
    if not cid and not is_admin:
        return
    
    content = (data.get("content") or "").strip()
    image_path = (data.get("image_path") or "").strip()
    
    if not content and not image_path:
        return
    
    if is_admin:
        cid = (data.get("customer_id") or "").strip()
        if not cid:
            return
        sender = "admin"
    else:
        sender = "customer"
    
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (customer_id, sender, content, image_path) VALUES (?, ?, ?, ?)",
            (cid, sender, content, image_path),
        )
    
    with get_db() as conn:
        row = conn.execute(
            "SELECT created_at FROM messages WHERE customer_id=? ORDER BY id DESC LIMIT 1",
            (cid,),
        ).fetchone()
    
    msg_data = {
        "sender": sender,
        "content": content,
        "image_path": image_path,
        "created_at": row["created_at"] if row else "",
    }
    
    emit("new_message", msg_data, room=f"customer_{cid}")
    emit("new_message", dict(msg_data, customer_id=cid), room="admin_room")
```

**步骤3**：修改文件末尾
```python
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5002))
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)
```


---

### 1.4 前端改造 —— `templates/messages.html`

**步骤1**：在 `<head>` 中引入 Socket.IO 客户端
```html
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
```

**步骤2**：替换聊天 JS 逻辑。找到现有 `loadMsgs()` 和 `setInterval(loadMsgs, 3000)`，全部替换为：

```javascript
// ── Socket.IO 实时聊天 ──
const socket = io({ transports: ["websocket", "polling"] });

socket.on("connect", () => {
    console.log("[Chat] Connected via Socket.IO");
    loadMsgs();  // 连接后仅加载一次历史消息
});

socket.on("disconnect", (reason) => {
    document.getElementById("chatStatus").textContent = "Reconnecting...";
    document.getElementById("chatStatus").style.color = "#f59e0b";
});

socket.on("new_message", (msg) => {
    appendMessage(msg);
    scrollToBottom();
});

// 替换原 sendMsg 函数
async function sendMsg() {
    const input = document.getElementById("msgInput");
    const content = input.value.trim();
    
    const imageInput = document.getElementById("imageInput");
    let imagePath = "";
    if (imageInput && imageInput.files.length > 0) {
        const formData = new FormData();
        formData.append("image", imageInput.files[0]);
        try {
            const uploadRes = await fetch("/api/upload-chat-image", {
                method: "POST", body: formData,
            });
            const uploadData = await uploadRes.json();
            if (uploadData.ok) imagePath = uploadData.image_path;
        } catch (e) { console.error("Image upload failed:", e); }
        imageInput.value = "";
    }
    
    if (!content && !imagePath) return;
    socket.emit("send_message", { content, image_path: imagePath });
    input.value = "";
    input.style.height = "auto";
}

// ❌ 删除或注释：setInterval(loadMsgs, 3000);
```

**步骤3**：在聊天头部添加连接状态
```html
<span id="chatStatus" style="color:#10b981;">● Connected</span>
```

---

### 1.5 管理后台前端 —— `templates/admin.html`

同样引入 Socket.IO，选择客户时实时接收消息：

```javascript
const socket = io({ transports: ["websocket", "polling"] });
let currentCustomerId = null;

socket.on("new_message", (msg) => {
    if (msg.customer_id === currentCustomerId) {
        appendAdminMessage(msg);
        scrollAdminChat();
    }
    refreshCustomerBadge(msg.customer_id);
});
```

---

### 1.6 生产部署配置

**Gunicorn 启动命令**:
```bash
gunicorn -k eventlet -w 1 --bind 0.0.0.0:8000 app:app
```

**Nginx 新增 WebSocket 代理**:
```nginx
location /socket.io/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 86400s;
}
```

> ⚠️ Socket.IO + eventlet 必须 `-w 1`（单 worker）。对当前规模完全足够。


---

## 需求二：验证码频繁失败 → 替换发送方案 + 增加 Magic Link

### 问题根因
自建SMTP（阿里云 `smtp.mxhichina.com`）发送验证码不稳定：邮件进垃圾箱、延迟高、到达率不可控。

### 解决方案：专业邮件API + Magic Link 双通道

---

### 2.1 方案A（推荐）：使用 Resend 替换 SMTP

**注册**: https://resend.com → 获取 API Key → 验证域名 inflatablemodel.cn

**新增依赖**:
```
resend>=1.0
```

**修改 `mailer.py`**—— 完全替换为 Resend API：
```python
"""mailer.py — Resend API email sender for InflatableModel.CN"""
import os
from typing import Optional

# 尝试导入 resend；如果未安装则回退到 dev 模式
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def is_smtp_configured() -> bool:
    return bool(RESEND_AVAILABLE and RESEND_API_KEY)


def send_verification_code(to_email: str, code: str, magic_link: str = "") -> tuple[bool, Optional[str]]:
    """发送验证码邮件（含 Magic Link）"""
    subject = "Your Verification Code — InflatableModel.CN"

    magic_html = f'<p><a href="{magic_link}" style="display:inline-block;background:#6366f1;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">One-Click Login</a></p>' if magic_link else ""

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f8fafc;padding:40px 0;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
  <tr>
    <td style="background:linear-gradient(135deg,#6366f1,#7c3aed);padding:32px;border-radius:12px 12px 0 0;text-align:center;">
      <h1 style="color:#fff;font-size:22px;margin:0;">InflatableModel.CN</h1>
    </td>
  </tr>
  <tr>
    <td style="background:#fff;padding:32px;border-radius:0 0 12px 12px;box-shadow:0 4px 12px rgba(0,0,0,.08);">
      <p style="color:#475569;font-size:15px;">Your verification code is:</p>
      <div style="text-align:center;margin:24px 0;">
        <span style="display:inline-block;background:#f1f5f9;padding:16px 40px;border-radius:8px;font-size:32px;font-weight:700;letter-spacing:6px;color:#6366f1;font-family:monospace;">{code}</span>
      </div>
      {magic_html}
      <p style="color:#94a3b8;font-size:13px;margin-top:16px;">This code expires in <strong>5 minutes</strong>. If you did not request this, please ignore.</p>
    </td>
  </tr>
</table>
</body>
</html>"""

    if not is_smtp_configured():
        print(f"[DEV MODE] Verification code for {to_email}: {code}  |  Magic: {magic_link}")
        return True, None

    try:
        resend.api_key = RESEND_API_KEY
        params = {
            "from": "InflatableModel.CN <noreply@inflatablemodel.cn>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }
        resend.Emails.send(params)
        return True, None
    except Exception as e:
        return False, str(e)
```

**备选方案（SendGrid）**：如果不想用 Resend，改用 SendGrid（`pip install sendgrid`，注册 https://sendgrid.com）。逻辑类似，只需替换 API 调用部分。

---

### 2.2 Magic Link 一键登录

在 `app.py` 中增加：

```python
# ── Magic Link 生成与验证 ──

def generate_magic_token(customer_id: str) -> str:
    """生成24小时有效的 magic link token"""
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute(
            "UPDATE customers SET magic_token=?, magic_token_expires=? WHERE id=?",
            (token, expires, customer_id),
        )
    return token


@app.route("/api/magic-login")
def magic_login():
    """Magic Link 一键登录"""
    token = request.args.get("token", "")
    email = request.args.get("email", "").lower()
    if not token or not email:
        return redirect("/login?error=invalid_magic_link")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name FROM customers WHERE email=? AND magic_token=? AND magic_token_expires > datetime('now','localtime')",
            (email, token),
        ).fetchone()

    if not row:
        return redirect("/login?error=expired_magic_link")

    # 清除 magic token
    conn.execute("UPDATE customers SET magic_token='', magic_token_expires='' WHERE id=?", (row["id"],))

    # 设置会话
    session["customer_id"] = row["id"]
    session["contact_email"] = email
    session["contact_name"] = row["name"] or email.split("@")[0]
    session["verified"] = True
    verified_sessions.add(session.sid)

    # 设置30天自动登录 cookie
    persistent_token = uuid.uuid4().hex + secrets.token_hex(16)
    expires_db = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    client_ip = request.headers.get("CF-Connecting-IP", request.remote_addr)
    conn.execute(
        "UPDATE customers SET persistent_token=?, token_expires=?, last_ip=? WHERE id=?",
        (persistent_token, expires_db, client_ip, row["id"]),
    )

    resp = make_response(redirect("/generate"))
    resp.set_cookie("auto_login", persistent_token, max_age=30*24*3600, httponly=True, samesite="Lax")
    return resp
```

**在 `api_login` 中调用 magic link**：
```python
# 生成验证码的同时生成 magic link
magic_token = generate_magic_token(existing_id_or_cid)
magic_link = url_for("magic_login", token=magic_token, email=email, _external=True)
mailer.send_verification_code(email, code, magic_link=magic_link)
```

**数据库新增字段**：
```sql
ALTER TABLE customers ADD COLUMN magic_token TEXT DEFAULT '';
ALTER TABLE customers ADD COLUMN magic_token_expires TEXT DEFAULT '';
```

---

### 2.3 防暴力破解加强

在 `api_verify` 中：
```python
MAX_ATTEMPTS = 3  # 最多3次错误尝试
if record["attempts"] > MAX_ATTEMPTS:
    record["expired"] = True
    return jsonify({"ok": False, "error": "Too many attempts. Please request a new code."}), 429
```

---

### 2.4 需要新增的环境变量

```
RESEND_API_KEY=re_xxxxxxxxxxxx
```


---

## 需求三：手机号强制要求填写

### 3.1 后端修改 —— `app.py` `api_login` 函数

在 `api_login` 顶部校验部分增加：

```python
phone = (data.get("phone") or "").strip()

# ── 新增：手机号必填 ──
if not phone:
    return jsonify({"ok": False, "error": "Phone number is required."}), 400

# 基本国际格式校验
import re
if not re.match(r"^\+?[\d\s\-\(\)]{7,20}$", phone):
    return jsonify({"ok": False, "error": "Please enter a valid phone number (e.g. +86 13800138000)."}), 400
```

### 3.2 前端修改 —— `templates/login.html`

找到 Phone Number 行，从 `<span class="optional">(optional)</span>` 改为：
```html
<label for="phone">Phone Number <span class="required">*</span></label>
<input type="tel" id="phone" placeholder="+86 138 0000 0000" required autocomplete="tel">
```

并在前端 JS 增加校验：
```javascript
const phone = document.getElementById("phone").value.trim();
if (!phone) {
    errEl.textContent = "Phone number is required.";
    errEl.style.display = "block";
    return;
}
```

---

## 需求四：用户IP记忆自动登录（30天内无需重新验证）

### 4.1 项目已有基础设施
`auto_login_from_token()` 函数已通过 `persistent_token` cookie 实现自动登录，但缺少 IP 绑定安全层。

### 4.2 需要增强的内容

**数据库新增字段**：
```sql
ALTER TABLE customers ADD COLUMN last_ip TEXT DEFAULT '';
```

**修改 `auto_login_from_token()`**（`app.py` `@app.before_request`）：

```python
@app.before_request
def auto_login_from_token():
    """Restore session from persistent auto-login cookie (30-day validity + IP memory)."""
    if session.get("verified") and session.get("customer_id"):
        return
    token = request.cookies.get("auto_login")
    if not token:
        return

    client_ip = request.headers.get("CF-Connecting-IP", request.remote_addr)
    # 取 IP 前3段作为宽松匹配（允许同一网络内登录）
    ip_prefix = ".".join(client_ip.split(".")[:3]) if client_ip else ""

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, name, last_ip FROM customers WHERE persistent_token=? AND token_expires > datetime('now','localtime')",
            (token,),
        ).fetchone()

    if not row:
        return

    stored_ip = row["last_ip"] or ""
    stored_prefix = ".".join(stored_ip.split(".")[:3]) if stored_ip else ""

    # IP 前缀匹配 或 完全相同 → 允许自动登录
    if ip_prefix == stored_prefix or client_ip == stored_ip:
        session["customer_id"] = row["id"]
        session["contact_email"] = row["email"]
        session["contact_name"] = row["name"]
        session["verified"] = True
        verified_sessions.add(session.sid)
```

**在 `api_verify` 验证成功后记录 IP**：
```python
# 在 api_verify 中，验证成功后的区块增加：
client_ip = request.headers.get("CF-Connecting-IP", request.remote_addr)
conn.execute("UPDATE customers SET last_ip=? WHERE id=?", (client_ip, cid))
```

---

## 需求五：增加谷歌一键登录

### 5.1 你需要准备的东西（发给AI前请先准备好）

| 项目 | 获取方式 |
|------|----------|
| 1. 谷歌账号 | 任何 Gmail 账号 |
| 2. Google Cloud 项目 | https://console.cloud.google.com → 新建项目 |
| 3. OAuth 2.0 凭据 | APIs & Services → Credentials → Create OAuth client ID |
| 4. GOOGLE_CLIENT_ID | 创建后获得的 `xxx.apps.googleusercontent.com` |
| 5. GOOGLE_CLIENT_SECRET | 创建后获得的 `GOCSPX-xxx` |

**OAuth 配置关键字段**：
- Application type: **Web application**
- Authorized JavaScript origins: `https://inflatablemodel.cn`, `http://localhost:5002`
- Authorized redirect URIs: `https://inflatablemodel.cn/api/auth/google/callback`, `http://localhost:5002/api/auth/google/callback`

### 5.2 新增依赖
```
authlib>=1.3
```

### 5.3 后端实现 —— `app.py`

**步骤1**：文件顶部新增导入和OAuth注册
```python
from authlib.integrations.flask_client import OAuth

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"},
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
)
```

**步骤2**：替换现有的 `/api/auth/google` 和新增 callback 路由
```python
@app.route("/api/auth/google")
def google_login():
    """触发 Google OAuth 登录流程"""
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/api/auth/google/callback")
def google_callback():
    """Google OAuth 回调"""
    try:
        token = google.authorize_access_token()
        user_info = google.get("userinfo").json()
    except Exception as e:
        return redirect("/login?error=google_auth_failed")

    email = (user_info.get("email") or "").lower()
    name = user_info.get("name") or ""
    google_id = user_info.get("id") or ""

    if not email:
        return redirect("/login?error=google_no_email")

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE customers SET google_id=?, name=?, last_active_at=datetime('now','localtime') WHERE id=?",
                (google_id, name, existing["id"]),
            )
            cid = existing["id"]
        else:
            cid = email.replace("@", "_at_").replace(".", "_")
            conn.execute(
                "INSERT INTO customers (id, name, email, google_id, verified) VALUES (?, ?, ?, ?, 1)",
                (cid, name, email, google_id),
            )

    # 设置会话
    session["customer_id"] = cid
    session["contact_email"] = email
    session["contact_name"] = name
    session["verified"] = True
    verified_sessions.add(session.sid)

    # 设置30天自动登录
    persistent_token = uuid.uuid4().hex + secrets.token_hex(16)
    expires = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    client_ip = request.headers.get("CF-Connecting-IP", request.remote_addr)
    conn.execute(
        "UPDATE customers SET persistent_token=?, token_expires=?, last_ip=? WHERE id=?",
        (persistent_token, expires, client_ip, cid),
    )

    resp = make_response(redirect("/generate"))
    resp.set_cookie("auto_login", persistent_token, max_age=30*24*3600, httponly=True, samesite="Lax")
    return resp
```

### 5.4 前端修改 —— `templates/login.html`

**方案A（推荐，Google Identity Services 新SDK）**：
```html
<script src="https://accounts.google.com/gsi/client" async defer></script>

<div id="g_id_onload"
     data-client_id="{{ google_client_id }}"
     data-callback="handleGoogleResponse"
     data-auto_prompt="false">
</div>
<div class="g_id_signin"
     data-type="standard"
     data-size="large"
     data-theme="filled_blue"
     data-text="sign_in_with"
     data-shape="rectangular"
     data-logo_alignment="left">
</div>

<script>
function handleGoogleResponse(response) {
    fetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential })
    }).then(r => r.json()).then(data => {
        if (data.ok) window.location.href = "/generate";
        else alert("Google login failed: " + (data.error || "Unknown"));
    });
}
</script>
```

> ⚠️ 如果用方案A，后端需要改为验证 Google ID Token（而不是 OAuth 重定向），需要安装 `google-auth` 库。

**方案B（更简单，直接跳转后端）**：
```html
<a href="/api/auth/google" class="btn-google" style="display:flex;align-items:center;justify-content:center;gap:10px;padding:14px;background:#fff;color:#333;border:1px solid #dadce0;border-radius:8px;text-decoration:none;font-weight:500;font-size:15px;">
    <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
    Sign in with Google
</a>
```

**传给模板的变量**（`app.py` 的 `/login` 路由）：
```python
@app.route("/login")
def login_page():
    return render_template("login.html",
        google_client_id=config.GOOGLE_CLIENT_ID,
        smtp_configured=mailer.is_smtp_configured())
```

### 5.5 谷歌登录的用户处理规则
- 谷歌登录用户直接标记 `verified=1`，无需邮箱验证
- 同一邮箱先用验证码注册后谷歌登录 → 自动合并账号
- 谷歌登录同样享受30天 IP 记忆自动登录


---

## 需求六：3D模型生成失败时，自动将用户图片发送到客服对话框

### 6.1 修改点 —— `app.py` `api_generate_3d` 相关轮询逻辑

在轮询混元3D任务状态发现 `failed` 时，自动发送系统消息。

找到任务状态轮询代码区域（通常在 `/api/task-status/<task_id>` 路由中），在返回 `failed` 状态前增加：

```python
@app.route("/api/task-status/<task_id>")
def api_task_status(task_id):
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Not logged in"}), 403
    cid = session.get("customer_id")

    with get_db() as conn:
        task = conn.execute(
            "SELECT * FROM generation_tasks WHERE job_id=? AND customer_id=?",
            (task_id, cid),
        ).fetchone()

    if not task:
        return jsonify({"ok": False, "error": "Task not found"}), 404

    # ... 现有轮询/查询混元 API 状态逻辑 ...

    # ── 新增：检测到失败时自动通知聊天系统 ──
    if status == "failed" and task["status"] != "failed":
        # 仅首次变更为 failed 时发送消息（避免重复）
        error_msg = result.get("error_message", "Unknown error") if isinstance(result, dict) else "Unknown error"
        input_image = task["input_image_path"] or ""

        # 1) 通知用户
        conn.execute(
            "INSERT INTO messages (customer_id, sender, content, image_path, message_type) VALUES (?, 'system', ?, ?, 'system')",
            (cid,
             f"Your 3D model generation for task #{task_id[:8]} has failed. Our support team has been notified with your reference image and will get back to you shortly!",
             input_image,
            )
        )

        # 2) 通知客服（附带用户图片和错误信息）
        customer_name = session.get("contact_name", "Unknown")
        customer_email = session.get("contact_email", "")
        conn.execute(
            "INSERT INTO messages (customer_id, sender, content, image_path, message_type) VALUES (?, 'system', ?, ?, 'system')",
            (cid,
             f"[AUTO] 3D generation FAILED\nCustomer: {customer_name} ({customer_email})\nTask ID: {task_id}\nInput: {task['input_text'] or 'image'}\nError: {error_msg}",
             input_image,
            )
        )

        # 更新数据库任务状态
        conn.execute(
            "UPDATE generation_tasks SET status='failed', error_message=?, completed_at=datetime('now','localtime') WHERE job_id=?",
            (error_msg, task_id),
        )

        # 3) 通过 Socket.IO 实时推送（如果安装了 flask-socketio）
        try:
            from flask_socketio import emit
            emit("new_message", {
                "sender": "system",
                "content": f"[AUTO] 3D generation FAILED for {customer_name}, image attached",
                "image_path": input_image,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "customer_id": cid,
            }, room="admin_room", namespace="/")
        except Exception:
            pass  # SocketIO 不可用时不报错

    # ... 继续返回状态 ...
    return jsonify({"ok": True, "status": status, ...})
```

### 6.2 前端联动 —— `templates/generate.html`

在轮询状态时检测到 `failed`：
```javascript
if (data.status === "failed") {
    alert("Generation failed. Your image has been sent to our support team. Redirecting to chat...");
    window.location.href = "/messages";
}
```

---

## 需求七：对话框内所有图片和模型支持下载

### 7.1 前端修改 —— `templates/messages.html`

**修改 `appendMessage` 函数**：在渲染消息气泡时，为所有图片增加下载按钮。

```javascript
function appendMessage(msg) {
    const container = document.getElementById("chatMessages");
    const row = document.createElement("div");
    row.className = "msg-row " + msg.sender;

    const avatar = document.createElement("div");
    avatar.className = "msg-avatar";
    avatar.textContent = msg.sender === "customer" ? "You" : (msg.sender === "admin" ? "M" : "S");

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    // 文本内容
    if (msg.content) {
        bubble.textContent = msg.content;
    }

    // 图片
    if (msg.image_path) {
        const img = document.createElement("img");
        img.src = msg.image_path;
        img.className = "msg-img";
        img.onclick = () => openLightbox(msg.image_path);
        bubble.appendChild(img);

        // ── 新增：下载按钮 ──
        const downloadBtn = document.createElement("a");
        downloadBtn.href = "/api/download" + msg.image_path;
        downloadBtn.download = msg.image_path.split("/").pop();
        downloadBtn.className = "msg-download-btn";
        downloadBtn.title = "Download";
        downloadBtn.innerHTML = "⤓";
        bubble.appendChild(downloadBtn);
    }

    // 时间
    const time = document.createElement("div");
    time.className = "msg-time";
    time.textContent = msg.created_at ? formatTime(msg.created_at) : "";
    bubble.appendChild(time);

    row.appendChild(avatar);
    row.appendChild(bubble);
    container.appendChild(row);
}
```

**新增 CSS**（在 `<style>` 中添加）：
```css
.msg-bubble {
    position: relative;
}
.msg-download-btn {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 28px;
    height: 28px;
    background: rgba(0,0,0,0.55);
    color: #fff;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    font-size: 14px;
    font-weight: 700;
    opacity: 0;
    transition: opacity 0.2s;
    z-index: 5;
}
.msg-bubble:hover .msg-download-btn {
    opacity: 1;
}
.msg-download-btn:hover {
    background: var(--primary, #6366f1);
}
```

### 7.2 后端新增强制下载接口 —— `app.py`

```python
@app.route("/api/download/uploads/<path:filename>")
def api_download(filename):
    """强制下载用户上传的文件"""
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

@app.route("/api/download/uploads/chat/<path:filename>")
def api_download_chat(filename):
    """强制下载聊天图片"""
    return send_from_directory(os.path.join(UPLOAD_DIR, "chat"), filename, as_attachment=True)

@app.route("/api/download/uploads/models/<path:filename>")
def api_download_model(filename):
    """强制下载3D模型文件（.glb）"""
    return send_from_directory(os.path.join(UPLOAD_DIR, "models"), filename, as_attachment=True)
```

### 7.3 管理后台 `admin.html` 同样处理
管理后台查看客户聊天时，消息中的图片也需要下载按钮，代码逻辑相同。


---

## 附录A：完整改造清单

| 序号 | 需求 | 改造方式 | 影响文件 | 新增依赖 |
|------|------|----------|----------|----------|
| 1 | 聊天消息发送失败 | HTTP轮询 → Flask-SocketIO 实时通信 | `app.py`, `admin_chat.py`, `messages.html`, `admin.html` | `flask-socketio`, `eventlet` |
| 2 | 验证码频繁失败 | SMTP → Resend/SendGrid API + Magic Link 双通道 | `mailer.py`, `app.py`, `config.py` | `resend` 或 `sendgrid` |
| 3 | 手机号强制 | 后端校验 + 前端标记必填 | `app.py` (api_login), `login.html` | 无 |
| 4 | IP记忆自动登录(30天) | 增强现有 token + IP前缀匹配 | `app.py` (auto_login_from_token, api_verify) | 无 |
| 5 | 谷歌登录 | OAuth 2.0 完整实现 | `app.py`, `login.html`, `config.py` | `authlib` |
| 6 | 3D失败自动通知 | 失败时写入消息 + 图片 | `app.py` (api_task_status) | 无 |
| 7 | 图片/模型下载 | 前端下载按钮 + 后端强制下载接口 | `messages.html`, `admin.html`, `app.py` | 无 |

---

## 附录B：完整的 `requirements.txt`（改造后）

```
flask>=3.0
flask-session>=0.7
requests>=2.31
gunicorn>=21.2
flask-socketio>=5.3
eventlet>=0.36
authlib>=1.3
resend>=1.0
```

---

## 附录C：数据库迁移 SQL（注意：先备份 data.db！）

```sql
-- 需求三 & 四：手机号强制 + IP记忆
ALTER TABLE customers ADD COLUMN last_ip TEXT DEFAULT '';

-- 需求二：Magic Link
ALTER TABLE customers ADD COLUMN magic_token TEXT DEFAULT '';
ALTER TABLE customers ADD COLUMN magic_token_expires TEXT DEFAULT '';

-- 需求五：谷歌登录（google_id 已存在则跳过）
-- ALTER TABLE customers ADD COLUMN google_id TEXT DEFAULT '';
```

**执行方式**：
```python
# 可以在 app.py init_db 或单独脚本中执行
def run_migrations():
    with get_db() as conn:
        try: conn.execute("ALTER TABLE customers ADD COLUMN last_ip TEXT DEFAULT ''")
        except: pass
        try: conn.execute("ALTER TABLE customers ADD COLUMN magic_token TEXT DEFAULT ''")
        except: pass
        try: conn.execute("ALTER TABLE customers ADD COLUMN magic_token_expires TEXT DEFAULT ''")
        except: pass
```

---

## 附录D：新增环境变量汇总

```bash
# 在 .env 文件或服务器环境变量中添加：

# Resend（替换SMTP）
RESEND_API_KEY=re_xxxxxxxxxxxx

# Google OAuth（需求五，需先到 Google Cloud Console 创建）
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxx

# 以下已存在，确认已配置
FLASK_SECRET_KEY=xxx
HUNYUAN_API_KEY=sk-xxx
ADMIN_PASSWORD=xxx
```

---

## 附录E：执行顺序建议

**按优先级执行：**

1. **先做需求一**（Socket.IO 重构聊天）— 这是最大痛点，解决后所有消息相关功能都有基础
2. **再做需求六**（3D失败通知）— 直接依赖聊天系统
3. **再做需求七**（图片下载）— 前端微调
4. **然后做需求二**（Resend + Magic Link）— 独立模块，不干扰其他功能
5. **然后做需求三**（手机号强制）— 两行代码改动
6. **然后做需求四**（IP记忆）— 已有基础，只需增强
7. **最后做需求五**（谷歌登录）— 需要外部配置，复杂度最高

---

## 附录F：关键生产环境注意事项

1. **备份数据库**：任何迁移前先 `cp data.db data.db.backup`
2. **Gunicorn Socket.IO**：必须 `-k eventlet -w 1`，通过 Nginx 反向代理
3. **Resend 域名验证**：注册后需在 DNS 添加 TXT/SPF/DKIM 记录
4. **Google OAuth 审核**：开发阶段添加测试用户；发布到所有人使用前需 Google 审核
5. **测试环境**：先在本地 `http://localhost:5002` 完整测试后再部署生产

---

> 📋 **将此文档直接复制发送给 AI（ChatGPT / Cursor / Codex / Claude），告诉它："请按照这份文档重构 inflatable-website 项目"，AI 即可按步骤逐项执行。**
