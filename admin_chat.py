"""
admin_chat.py — 管理后台聊天模块
独立聊天管理后端，处理客户列表、消息收发、客户信息编辑
"""
import json
import uuid
import secrets
import os
import sqlite3
import time
from datetime import datetime, timedelta

import requests
from flask import Blueprint, jsonify, request, session, send_from_directory

import config

chat_bp = Blueprint("admin_chat", __name__, url_prefix="/api/admin")

# ── Login rate limiting (in-memory, per IP) ──
_login_attempts = {}  # ip -> {"count": int, "last_attempt": float}
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCKOUT_SEC = 300  # 5 minutes

# ── Database helpers (reuse main DB) ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "data.db")
CHAT_UPLOAD_DIR = os.path.join(ROOT_DIR, "uploads", "chat")




def _ensure_admin_logs_table():
    """Create admin_logs table if not exists."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target_customer TEXT DEFAULT '',
            detail TEXT DEFAULT '',
            ip TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime("now","localtime"))
        )
    """)
    conn.commit()
    conn.close()

def log_admin_action(action, target_customer="", detail=""):
    """Record an admin action to the log."""
    try:
        from flask import request
        ip = request.remote_addr or ""
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            "INSERT INTO admin_logs (action, target_customer, detail, ip) VALUES (?, ?, ?, ?)",
            (action, target_customer, detail, ip)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_db_path():
    """Get the database file path."""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def admin_required(f):
    """Decorator: require admin login"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"ok": False, "error": "未授权，请先登录"}), 401
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════
#  客户管理
# ══════════════════════════════════════════════════

@chat_bp.route("/login", methods=["POST"])
def admin_login():
    """管理员登录（含失败次数限制）"""
    ip = request.remote_addr or "unknown"
    now = time.time()

    # Check rate limit
    attempt = _login_attempts.get(ip)
    if attempt and attempt["count"] >= _MAX_LOGIN_ATTEMPTS:
        if now - attempt["last_attempt"] < _LOGIN_LOCKOUT_SEC:
            remaining = int(_LOGIN_LOCKOUT_SEC - (now - attempt["last_attempt"]))
            return jsonify({"ok": False, "error": f"登录失败次数过多，请 {remaining} 秒后重试"}), 429
        else:
            _login_attempts.pop(ip, None)

    data = request.get_json(force=True, silent=True) or {}
    password = (data.get("password") or "").strip()
    if password == config.ADMIN_PASSWORD:
        _login_attempts.pop(ip, None)
        session["admin_logged_in"] = True
        return jsonify({"ok": True})

    # Record failed attempt
    if ip not in _login_attempts:
        _login_attempts[ip] = {"count": 0, "last_attempt": now}
    _login_attempts[ip]["count"] += 1
    _login_attempts[ip]["last_attempt"] = now

    return jsonify({"ok": False, "error": "密码错误"}), 401


@chat_bp.route("/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return jsonify({"ok": True})


@chat_bp.route("/customers")
@admin_required
def api_admin_customers():
    """获取客户列表（含未读消息数）"""
    with get_db() as conn:
        customers = conn.execute("""
            SELECT c.*,
                (SELECT COUNT(*) FROM messages WHERE customer_id=c.id AND sender='customer' AND is_read=0) AS unread,
                (SELECT MAX(created_at) FROM messages WHERE customer_id=c.id) AS last_msg_time
            FROM customers c
            ORDER BY last_msg_time DESC NULLS LAST, c.created_at DESC
        """).fetchall()
    return jsonify({
        "ok": True,
        "customers": [dict(r) for r in customers],
    })


@chat_bp.route("/customer/<customer_id>")
@admin_required
def api_admin_customer_info(customer_id):
    """获取单个客户详情"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, whatsapp, company, country, tag, generation_count, generation_status, verified, created_at, last_active_at, last_followup_at FROM customers WHERE id=?",
            (customer_id,),
        ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "客户不存在"}), 404
    return jsonify({"ok": True, "customer": dict(row)})


@chat_bp.route("/customer/models")
@admin_required
def api_admin_customer_models():
    """获取客户的模型列表"""
    customer_id = request.args.get("customer_id", "").strip()
    if not customer_id:
        return jsonify({"ok": False, "error": "缺少客户ID"}), 400
    with get_db() as conn:
        tasks = conn.execute(
            "SELECT job_id AS task_id, result_url, input_image_path, completed_at "
            "FROM generation_tasks WHERE customer_id=? AND status='completed' ORDER BY completed_at DESC",
            (customer_id,),
        ).fetchall()
    return jsonify({"ok": True, "models": [dict(t) for t in tasks]})


@chat_bp.route("/customer/update", methods=["POST"])
@admin_required
def api_admin_update_customer():
    """更新客户字段（tag/whatsapp/company/country/phone）"""
    data = request.get_json(force=True, silent=True) or {}
    customer_id = (data.get("customer_id") or "").strip()
    field = (data.get("field") or "").strip()
    value = (data.get("value") or "").strip()

    ALLOWED = {"tag", "whatsapp", "company", "country", "phone"}
    if field not in ALLOWED:
        return jsonify({"ok": False, "error": f"不允许修改字段 '{field}'"}), 400
    if not customer_id:
        return jsonify({"ok": False, "error": "缺少客户ID"}), 400

    COL_MAP = {"tag": "tag", "whatsapp": "whatsapp", "company": "company", "country": "country", "phone": "phone"}
    column = COL_MAP[field]

    with get_db() as conn:
        conn.execute(
            f"UPDATE customers SET {column}=?, last_followup_at=datetime('now','localtime') WHERE id=?",
            (value, customer_id),
        )
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════
#  消息管理
# ══════════════════════════════════════════════════

@chat_bp.route("/messages/<customer_id>")
@admin_required
def api_admin_messages(customer_id):
    """获取客户聊天消息列表（同时标记已读）"""
    with get_db() as conn:
        conn.execute(
            "UPDATE messages SET is_read=1 WHERE customer_id=? AND sender='customer' AND is_read=0",
            (customer_id,),
        )
        rows = conn.execute(
            "SELECT id, sender, content, image_path, created_at, is_read FROM messages "
            "WHERE customer_id=? ORDER BY created_at ASC",
            (customer_id,),
        ).fetchall()
    return jsonify({"ok": True, "messages": [dict(r) for r in rows]})


@chat_bp.route("/reply", methods=["POST"])
@admin_required
def api_admin_reply():
    """管理员回复消息"""
    # Support both JSON and multipart/form-data
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        customer_id = (data.get("customer_id") or "").strip()
        content = (data.get("content") or "").strip()
        image_path = (data.get("image_path") or "").strip()
    else:
        customer_id = (request.form.get("customer_id") or "").strip()
        content = (request.form.get("content") or "").strip()
        image_path = (request.form.get("image_path") or "").strip()

    if not customer_id or (not content and not image_path):
        return jsonify({"ok": False, "error": "客户ID和内容不能为空"}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (customer_id, sender, content, image_path) VALUES (?, 'admin', ?, ?)",
            (customer_id, content, image_path),
        )
        log_admin_action("reply", customer_id, content[:100])
    return jsonify({"ok": True})


@chat_bp.route("/unread-count")
@admin_required
def api_admin_unread_count():
    """获取所有客户的未读消息总数"""
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM messages WHERE sender='customer' AND is_read=0"
        ).fetchone()["cnt"]
    return jsonify({"ok": True, "unread": total})


@chat_bp.route("/upload-chat-image", methods=["POST"])
@admin_required
def api_admin_upload_chat_image():
    """上传聊天图片"""
    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "请选择图片"}), 400

    import uuid
    ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else "png"
    ALLOWED = {"png", "jpg", "jpeg", "webp", "gif"}
    if ext not in ALLOWED:
        return jsonify({"ok": False, "error": "不支持的图片格式"}), 400

    os.makedirs(CHAT_UPLOAD_DIR, exist_ok=True)
    filename = f"chat_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(CHAT_UPLOAD_DIR, filename)
    file.save(filepath)

    return jsonify({
        "ok": True,
        "image_path": f"/uploads/chat/{filename}",
        "url": f"/uploads/chat/{filename}",
    })


@chat_bp.route("/logs")
@admin_required
def api_admin_logs():
    """Get admin action logs."""
    _ensure_admin_logs_table()
    limit = request.args.get("limit", 100, type=int)
    import sqlite3
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM admin_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    logs = [dict(r) for r in rows]
    return jsonify({"ok": True, "logs": logs})

