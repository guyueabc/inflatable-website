"""
InflatableModel.CN 鈥?Flask backend
Login / Register / Google Auth / 3D Generation (one-time) / Chat with images / Traffic stats / Admin panel
"""

import json
import os
import random
import secrets
import sqlite3
import string
import time
import uuid
from datetime import datetime, timedelta

from typing import Optional

import requests
from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    send_from_directory,
    url_for,
)
try:
    from flask_session import Session
    HAS_FLASK_SESSION = True
except ImportError:
    Session = None
    HAS_FLASK_SESSION = False

import config
import mailer

# 鈹€鈹€ Admin blueprint modules 鈹€鈹€
from admin_chat import chat_bp
from admin_traffic import traffic_bp

# 鈹€鈹€ App factory 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
app = Flask(__name__)
app.config.from_object(config)
if Session is not None:
    Session(app)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Register admin blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(traffic_bp)

UPLOAD_DIR = os.path.join(app.root_path, "uploads")
CHAT_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "chat")
MODELS_DIR = os.path.join(UPLOAD_DIR, "models")
TEMP_DIR = os.path.join(UPLOAD_DIR, "temp")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHAT_UPLOAD_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 鈹€鈹€ Database 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
DB_PATH = os.path.join(app.root_path, "data.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            
CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT DEFAULT '',
                whatsapp TEXT DEFAULT '',
                social TEXT DEFAULT '',
                company TEXT DEFAULT '',
                country TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                verified INTEGER DEFAULT 0,
                generation_count INTEGER DEFAULT 0,
                generation_status TEXT DEFAULT 'unused',
                google_id TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                tag TEXT DEFAULT 'warm',
                last_active_at TEXT DEFAULT (datetime('now','localtime')),
                last_followup_at TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                sender TEXT NOT NULL CHECK(sender IN ('customer','admin','system')),
                content TEXT NOT NULL,
                image_path TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                is_read INTEGER DEFAULT 0,
                message_type TEXT DEFAULT 'text',
                template_id TEXT DEFAULT '',
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE INDEX IF NOT EXISTS idx_msg_customer ON messages(customer_id);
            CREATE INDEX IF NOT EXISTS idx_msg_read ON messages(is_read);
            CREATE TABLE IF NOT EXISTS generation_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                input_type TEXT NOT NULL,
                input_image_path TEXT DEFAULT '',
                input_text TEXT DEFAULT '',
                job_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result_url TEXT DEFAULT '',
                preview_image_url TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                completed_at TEXT DEFAULT NULL,
                error_message TEXT DEFAULT '',
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE TABLE IF NOT EXISTS traffic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                country TEXT DEFAULT '',
                referrer TEXT DEFAULT '',
                customer_id TEXT DEFAULT NULL
            );
        """)

    # Schema migration for existing DBs
    with get_db() as conn:
        for col, col_def in [
            ("phone", "TEXT DEFAULT ''"),
            ("generation_count", "INTEGER DEFAULT 0"),
            ("generation_status", "TEXT DEFAULT 'unused'"),
            ("google_id", "TEXT DEFAULT ''"),
            ("avatar", "TEXT DEFAULT ''"),
            ("country", "TEXT DEFAULT ''"),
            ("tag", "TEXT DEFAULT 'warm'"),
            ("last_active_at", "TEXT DEFAULT (datetime('now','localtime'))"),
            ("last_followup_at", "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass
        for col, col_def in [
            ("image_path", "TEXT DEFAULT ''"),
            ("message_type", "TEXT DEFAULT 'text'"),
            ("template_id", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass
        for col, col_def in [
            ("country", "TEXT DEFAULT ''"),
            ("referrer", "TEXT DEFAULT ''"),
            ("customer_id", "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE traffic ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass
        # V5 migration: date field for daily dedup
        try:
            conn.execute("ALTER TABLE traffic ADD COLUMN date TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        # V6 migration: persistent login token + banned
        for col, col_def in [
            ("persistent_token", "TEXT DEFAULT ''"),
            ("token_expires", "TEXT DEFAULT ''"),
            ("banned", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE customers ADD COLUMN {col} {col_def}")
            except sqlite3.OperationalError:
                pass


init_db()

# 鈹€鈹€ In-memory stores 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
verification_codes: dict = {}
verified_sessions: set = set()


def _session_id() -> str:
    """Get session ID safely - works with or without flask-session."""
    sid = getattr(session, 'sid', None)
    if sid:
        return sid
    import hashlib
    data = str(session.get('customer_id', '')) + str(session.get('contact_email', ''))
    return hashlib.md5(data.encode()).hexdigest() if data else str(id(session))


# 鈹€鈹€ Helpers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in config.ALLOWED_IMAGE_EXTENSIONS


def generate_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def is_logged_in() -> bool:
    return bool(session.get("verified") and session.get("customer_id"))


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Traffic Statistics Middleware
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.before_request
def auto_login_from_token():
    """Restore session from persistent auto-login cookie (30-day validity)."""
    if session.get("verified") and session.get("customer_id"):
        return
    token = request.cookies.get("auto_login")
    if not token:
        return
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, name FROM customers WHERE persistent_token=? AND token_expires > datetime('now','localtime')",
            (token,),
        ).fetchone()
    if row:
        session["customer_id"] = row["id"]
        session["contact_email"] = row["email"]
        session["contact_name"] = row["name"]
        session["verified"] = True
        verified_sessions.add(_session_id())


@app.before_request
def track_traffic():
    path = request.path
    if path.startswith("/static") or path.startswith("/uploads"):
        return
    if path.startswith("/api/task-status") or path.startswith("/api/admin/unread-count"):
        return
    if path.startswith("/api/proxy-3d"):
        return
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) AS cnt FROM traffic WHERE ip=? AND page=? AND date=?",
                (request.remote_addr, path, today),
            ).fetchone()
            if existing["cnt"] == 0:
                conn.execute(
                    "INSERT INTO traffic (page, ip, user_agent, date) VALUES (?, ?, ?, ?)",
                    (path, request.remote_addr, request.headers.get("User-Agent", "")[:500], today),
                )
    except Exception:
        pass


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Pages
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/")
def index():
    if is_logged_in():
        return redirect("/generate")
    return render_template("index.html")


@app.route("/login")
def login_page():
    if is_logged_in():
        return redirect("/generate")
    smtp_configured = bool(config.MAIL_USERNAME and config.MAIL_PASSWORD)
    return render_template("login.html", google_client_id=config.GOOGLE_CLIENT_ID, smtp_configured=smtp_configured)


@app.route("/verify")
def verify():
    email = session.get("contact_email", "")
    return render_template("verify.html", email=email)


@app.route("/generate")
def generate():
    cid = session.get("customer_id")
    if not cid:
        return redirect("/login")
    with get_db() as conn:
        row = conn.execute("SELECT generation_count FROM customers WHERE id=?", (cid,)).fetchone()
    if row and row["generation_count"] >= 1:
        return redirect("/messages")
    return render_template("generate.html")


@app.route("/messages")
def messages_page():
    cid = session.get("customer_id")
    if not cid:
        return redirect("/login")
    return render_template("messages.html")


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Login / Register
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    name = (data.get("name") or "").strip()
    company = (data.get("company") or "").strip()

    if not email:
        return jsonify({"ok": False, "error": "Email is required."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400
    if not name:
        name = email.split("@")[0]

    customer_id = email.replace("@", "_at_").replace(".", "_")

    with get_db() as conn:
        existing = conn.execute("SELECT id, name FROM customers WHERE email=?", (email,)).fetchone()

    if existing:
        with get_db() as conn:
            conn.execute(
                "UPDATE customers SET phone=?, name=?, company=?, last_active_at=datetime('now','localtime') WHERE id=?",
                (phone, name, company, existing["id"]),
            )
        session["customer_id"] = existing["id"]
        session["contact_email"] = email
        session["contact_name"] = name
    else:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, email, phone, whatsapp, company) VALUES (?, ?, ?, ?, ?, ?)",
                (customer_id, name, email, phone, phone, company),
            )
        session["customer_id"] = customer_id
        session["contact_email"] = email
        session["contact_name"] = name

    # Generate & send verification code
    # Rate limit: 1 request per 60 seconds per email
    existing_record = verification_codes.get(_session_id())
    if existing_record and not existing_record.get("expired"):
        elapsed = (datetime.utcnow() - existing_record.get("last_code_sent", datetime.min)).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return jsonify({"ok": False, "error": f"Please wait {remaining} seconds before requesting a new code.", "retry_after": remaining}), 429

    code = generate_code(6)
    verification_codes[_session_id()] = {
        "email": email,
        "code": code,
        "expires": datetime.utcnow() + timedelta(minutes=5),
        "attempts": 0,
        "last_code_sent": datetime.utcnow(),
    }

    sent, smtp_error = mailer.send_verification_code(email, code)
    smtp_configured = bool(config.MAIL_USERNAME and config.MAIL_PASSWORD)
    dev_code = None if smtp_configured else code
    if not sent:
        print(f"[SMTP FAILED] Verification code for {email}: {code} | Error: {smtp_error}")
        if smtp_configured:
            # SMTP was configured but failed — return error to user
            return jsonify({
                "ok": False,
                "error": f"Failed to send verification email. Please try again later or contact support.",
                "smtp_error": smtp_error,
                "dev_code": code,  # Provide code as fallback so user can still verify
            }), 503
        else:
            # SMTP not configured — dev mode
            return jsonify({
                "ok": True,
                "verified": False,
                "message": f"DEV MODE: Your code is {code}",
                "dev_code": code,
                "is_new": existing is None,
            })

    return jsonify({
        "ok": True,
        "verified": False,
        "message": "Verification code sent to your email.",
        "dev_code": dev_code,
        "is_new": existing is None,
    })


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Google OAuth
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/auth/google", methods=["POST"])
def api_auth_google():
    data = request.get_json(force=True, silent=True) or {}
    id_token = (data.get("credential") or "").strip()

    if not id_token:
        return jsonify({"ok": False, "error": "Missing credential."}), 400

    try:
        google_verify_url = "https://oauth2.googleapis.com/tokeninfo"
        resp = requests.get(google_verify_url, params={"id_token": id_token}, timeout=10)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": "Invalid Google token."}), 400
        token_info = resp.json()
    except Exception:
        return jsonify({"ok": False, "error": "Failed to verify Google token."}), 500

    google_email = (token_info.get("email") or "").strip().lower()
    google_name = (token_info.get("name") or google_email.split("@")[0]).strip()
    google_picture = token_info.get("picture", "")
    google_sub = token_info.get("sub", "")

    if not google_email:
        return jsonify({"ok": False, "error": "Could not get email from Google."}), 400

    customer_id = google_email.replace("@", "_at_").replace(".", "_")

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM customers WHERE email=?", (google_email,)).fetchone()

    if existing:
        cid = existing["id"]
        with get_db() as conn:
            conn.execute(
                "UPDATE customers SET google_id=?, avatar=?, last_active_at=datetime('now','localtime') WHERE id=?",
                (google_sub, google_picture, cid),
            )
    else:
        cid = customer_id
        with get_db() as conn:
            conn.execute(
                "INSERT INTO customers (id, name, email, google_id, avatar, verified) VALUES (?, ?, ?, ?, ?, 1)",
                (cid, google_name, google_email, google_sub, google_picture),
            )

    session["customer_id"] = cid
    session["contact_email"] = google_email
    session["contact_name"] = google_name
    session["verified"] = True
    verified_sessions.add(_session_id())

    # Generate persistent auto-login token (30 days)
    persistent_token = uuid.uuid4().hex + secrets.token_hex(16)
    expires = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute(
            "UPDATE customers SET persistent_token=?, token_expires=? WHERE id=?",
            (persistent_token, expires, cid),
        )

    resp = make_response(jsonify({
        "ok": True,
        "name": google_name,
        "email": google_email,
    }))
    resp.set_cookie("auto_login", persistent_token, max_age=30 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Verification
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/verify", methods=["POST"])
def api_verify():
    data = request.get_json(force=True, silent=True) or {}
    user_code = (data.get("code") or "").strip()

    record = verification_codes.get(_session_id())
    if not record:
        return jsonify({"ok": False, "error": "No verification in progress."}), 400

    if datetime.utcnow() > record["expires"]:
        # Mark expired but keep record so resend still works
        record["expired"] = True
        return jsonify({"ok": False, "error": "Verification code expired. Click 'Resend code' to get a new one."}), 400

    record["attempts"] += 1
    if record["attempts"] > 5:
        record["expired"] = True
        return jsonify({"ok": False, "error": "Too many attempts. Click 'Resend code' to get a new one."}), 429

    if user_code != record["code"]:
        return jsonify({"ok": False, "error": "Invalid code."}), 400

    verification_codes.pop(_session_id(), None)
    session["verified"] = True
    verified_sessions.add(_session_id())

    cid = session.get("customer_id")
    email = session.get("contact_email", "")
    if cid:
        # Generate persistent auto-login token (30 days)
        persistent_token = uuid.uuid4().hex + secrets.token_hex(16)
        expires = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            conn.execute(
                "UPDATE customers SET verified=1, persistent_token=?, token_expires=? WHERE id=?",
                (persistent_token, expires, cid),
            )
        resp = make_response(jsonify({"ok": True, "message": "Email verified successfully."}))
        resp.set_cookie("auto_login", persistent_token, max_age=30 * 24 * 3600, httponly=True, samesite="Lax")
        return resp

    return jsonify({"ok": True, "message": "Email verified successfully."})


@app.route("/api/resend-code", methods=["POST"])
def api_resend():
    record = verification_codes.get(_session_id())
    if not record:
        return jsonify({"ok": False, "error": "No active verification session."}), 400

    # 60-second interval check
    last_sent = record.get("last_code_sent")
    if last_sent:
        elapsed = (datetime.utcnow() - last_sent).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return jsonify({"ok": False, "error": f"Please wait {remaining} seconds before requesting a new code."}), 429

    new_code = generate_code(6)
    record["code"] = new_code
    record["expires"] = datetime.utcnow() + timedelta(minutes=5)
    record["attempts"] = 0
    record["expired"] = False
    record["last_code_sent"] = datetime.utcnow()

    sent, smtp_error = mailer.send_verification_code(record["email"], new_code)
    smtp_configured = bool(config.MAIL_USERNAME and config.MAIL_PASSWORD)
    if sent:
        return jsonify({"ok": True, "message": "New code sent."})
    else:
        print(f"[SMTP FAILED] Resend code for {record['email']}: {new_code} | Error: {smtp_error}")
        if smtp_configured:
            return jsonify({
                "ok": False,
                "error": f"Failed to send verification email. Please try again later.",
                "dev_code": new_code,  # Fallback so user can still verify
            }), 503
        else:
            return jsonify({"ok": True, "message": "Dev mode: check terminal for code.", "dev_code": new_code})


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Logout
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/logout", methods=["GET", "POST"])
def api_logout():
    verified_sessions.discard(_session_id())
    # Clear persistent token from DB
    cid = session.get("customer_id")
    if cid:
        with get_db() as conn:
            conn.execute("UPDATE customers SET persistent_token='', token_expires='' WHERE id=?", (cid,))
    session.clear()
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("auto_login")
    return resp


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Hunyuan 3D (OpenAI-compatible) pipeline
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

# 鈹€鈹€ Proxy routing: when HUNYUAN_PROXY_URL is set, route through HK proxy 鈹€鈹€
if config.HUNYUAN_PROXY_URL:
    HUNYUAN_SUBMIT_URL = f"{config.HUNYUAN_PROXY_URL}/proxy/submit"
    HUNYUAN_QUERY_URL  = f"{config.HUNYUAN_PROXY_URL}/proxy/query"
    HUNYUAN_HEADERS = {"Content-Type": "application/json"}
    if config.HUNYUAN_PROXY_SECRET:
        HUNYUAN_HEADERS["X-Proxy-Secret"] = config.HUNYUAN_PROXY_SECRET
else:
    HUNYUAN_SUBMIT_URL = f"{config.HUNYUAN_ENDPOINT}/v1/ai3d/submit"
    HUNYUAN_QUERY_URL  = f"{config.HUNYUAN_ENDPOINT}/v1/ai3d/query"
    HUNYUAN_HEADERS = {
        "Authorization": config.HUNYUAN_API_KEY,
        "Content-Type": "application/json",
    }


def _extract_api_error(data: dict) -> str:
    """Extract human-readable error from Tencent Cloud / OpenAI-style response body."""
    # Tencent Cloud锛歊esponse.Error.Message
    resp = data.get("Response", {}) or {}
    err = resp.get("Error", {}) or {}
    if err.get("Message"):
        return err["Message"]
    # OpenAI-style
    openai_err = data.get("error", {}) or {}
    if openai_err.get("message"):
        return openai_err["message"]
    # Fallback formats
    for key in ("Msg", "msg", "message", "Message"):
        if key in data:
            return str(data[key])
    return str(data)[:300]


def _submit_3d_job(image_base64: Optional[str] = None, prompt: Optional[str] = None) -> Optional[dict]:
    body = {"Model": config.HUNYUAN_MODEL}
    if image_base64:
        body["ImageBase64"] = image_base64
    elif prompt:
        body["Prompt"] = prompt

    try:
        resp = requests.post(HUNYUAN_SUBMIT_URL, headers=HUNYUAN_HEADERS, json=body, timeout=30)
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"API returned non-JSON response (status {resp.status_code})")
        if resp.status_code != 200:
            raise RuntimeError(f"Submit failed ({resp.status_code}): {_extract_api_error(data)}")
        # Check for API-level error inside 200 response
        job_id = (data.get("Response", {}) or {}).get("JobId")
        if not job_id:
            err_msg = _extract_api_error(data)
            raise RuntimeError(f"API error: {err_msg}")
        return data
    except requests.RequestException as e:
        raise RuntimeError(f"Submit request failed: {e}")


def _query_3d_job(job_id: str) -> Optional[dict]:
    body = {"JobId": job_id}
    try:
        resp = requests.post(HUNYUAN_QUERY_URL, headers=HUNYUAN_HEADERS, json=body, timeout=30)
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"API returned non-JSON response (status {resp.status_code})")
        if resp.status_code != 200:
            raise RuntimeError(f"Query failed ({resp.status_code}): {_extract_api_error(data)}")
        return data
    except requests.RequestException as e:
        raise RuntimeError(f"Query request failed: {e}")


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  3D Generation (one-time per user)
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/generate-3d", methods=["POST"])
def api_generate_3d():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Please log in first.", "redirect": "/login"}), 403

    cid = session.get("customer_id")

    with get_db() as conn:
        row = conn.execute("SELECT generation_count FROM customers WHERE id=?", (cid,)).fetchone()
    if row and row["generation_count"] >= 1:
        return jsonify({
            "ok": False,
            "error": "You have already generated a 3D model. Chat with our consultant for more details.",
            "redirect": "/messages"
        }), 403

    # Check if Hunyuan API is configured
    if not config.HUNYUAN_API_KEY and not config.HUNYUAN_PROXY_URL:
        return jsonify({
            "ok": False,
            "error": "3D generation service is not yet configured. Redirecting to chat...",
            "redirect": "/messages"
        }), 503

    image_file = request.files.get("image")
    description = (request.form.get("description") or "").strip()

    if not image_file and not description:
        return jsonify({"ok": False, "error": "Please upload a reference image or provide a description."}), 400

    image_path = None
    image_base64 = None
    filename = None  # Initialize to prevent NameError on text-only submissions

    if image_file and image_file.filename:
        if not allowed_image(image_file.filename):
            return jsonify({"ok": False, "error": "Unsupported image format."}), 400

        ext = image_file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        image_file.save(image_path)

        import base64 as b64
        with open(image_path, "rb") as f:
            image_base64 = b64.b64encode(f.read()).decode("utf-8")

    if image_file and not image_base64:
        return jsonify({"ok": False, "error": "Failed to read uploaded image."}), 500

    import traceback, sys
    try:
        result = _submit_3d_job(
            image_base64=image_base64,
            prompt=description if description else None,
        )
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return jsonify({
            "ok": False,
            "error": f"3D generation failed: {exc}",
            "redirect": "/messages"
        }), 502

    if not result:
        return jsonify({"ok": False, "error": "Failed to submit 3D generation job.", "redirect": "/messages"}), 502

    job_id = (result.get("Response") or {}).get("JobId")
    if not job_id:
        return jsonify({"ok": False, "error": "No job ID returned from API.", "redirect": "/messages"}), 502

    preview_url = url_for("uploaded_file", filename=filename, _external=True) if (image_path and filename) else None

    # Record generation task
    with get_db() as conn:
        conn.execute(
            "INSERT INTO generation_tasks (customer_id, input_type, input_image_path, input_text, job_id, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (cid, "image" if image_base64 else "text", image_path or "", description, job_id),
        )
        conn.execute(
            "UPDATE customers SET generation_status='in_progress', last_active_at=datetime('now','localtime') WHERE id=?",
            (cid,),
        )

    return jsonify({
        "ok": True,
        "task_id": job_id,
        "status": "queued",
        "preview_url": preview_url,
    })


@app.route("/api/task-status/<task_id>")
def api_task_status(task_id):
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    data = _query_3d_job(task_id)
    if not data:
        return jsonify({"status": "queued", "progress": 0})

    resp = (data.get("Response") or {})
    status = (resp.get("Status") or "").lower()

    if status == "done":
        result = {"status": "completed", "progress": 100, "task_id": task_id}
        model_urls = {}
        preview_url = None
        glb_raw_url = None

        files = resp.get("ResultFile3Ds") or []
        if isinstance(files, list):
            for f in files:
                ft = (f.get("Type") or "").lower()
                fu = f.get("Url") or ""
                if ft == "glb" and fu:
                    glb_raw_url = fu
                    model_urls["glb"] = f"/api/proxy-3d?url={fu}"
                elif ft == "obj" and fu:
                    model_urls["obj"] = f"/api/proxy-3d?url={fu}"
                elif ft == "fbx" and fu:
                    model_urls["fbx"] = f"/api/proxy-3d?url={fu}"
                pv = f.get("PreviewImageUrl") or f.get("Preview")
                if pv and not preview_url:
                    preview_url = pv

        # Cache GLB model locally
        local_result_url = ""
        if glb_raw_url:
            models_dir = os.path.join(UPLOAD_DIR, "models")
            os.makedirs(models_dir, exist_ok=True)
            local_path = os.path.join(models_dir, f"{task_id}.glb")
            try:
                resp_dl = requests.get(glb_raw_url, timeout=60)
                if resp_dl.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(resp_dl.content)
                    local_result_url = f"/uploads/models/{task_id}.glb"
            except Exception as e:
                print(f"[CACHE] Failed to download GLB for {task_id}: {e}")

        result["model_urls"] = model_urls
        result["preview_image_url"] = preview_url
        result["local_model_url"] = local_result_url  # locally cached, always works

        cid = session.get("customer_id")
        if cid:
            db_result_url = local_result_url or model_urls.get("glb", "")
            with get_db() as conn:
                conn.execute(
                    "UPDATE customers SET generation_count=1, generation_status='completed', last_active_at=datetime('now','localtime') WHERE id=?",
                    (cid,),
                )
                conn.execute(
                    "UPDATE generation_tasks SET status='completed', result_url=?, preview_image_url=?, completed_at=datetime('now','localtime') WHERE job_id=?",
                    (db_result_url, preview_url or "", task_id),
                )

                # Auto welcome message: only on first completion
                existing_system_msg = conn.execute(
                    "SELECT COUNT(*) as cnt FROM messages WHERE customer_id=? AND sender='system'",
                    (cid,),
                ).fetchone()
                if existing_system_msg["cnt"] == 0:
                    welcome_msg = (
                        "Hi! Your 3D model is ready. I'm Mia, your personal consultant. "
                        "I've reviewed your model and have some suggestions to make it even better. "
                        "Shall we discuss your requirements?"
                    )
                    conn.execute(
                        "INSERT INTO messages (customer_id, sender, content, image_path) VALUES (?, 'system', ?, ?)",
                        (cid, welcome_msg, preview_url or ""),
                    )

    elif status == "run":
        result = {"status": "in_progress", "progress": 50}
    elif status in ("fail", "failed", "error"):
        result = {"status": "failed", "progress": 0,
                  "error": resp.get("ErrorMessage", "Generation failed"),
                  "redirect": "/messages"}
        cid = session.get("customer_id")
        if cid:
            with get_db() as conn:
                conn.execute(
                    "UPDATE generation_tasks SET status='failed', error_message=?, completed_at=datetime('now','localtime') WHERE job_id=?",
                    (resp.get("ErrorMessage", "Generation failed"), task_id),
                )
                # Reset generation_count so user can retry
                conn.execute(
                    "UPDATE customers SET generation_count=0, generation_status='failed' WHERE id=?",
                    (cid,),
                )
    else:
        result = {"status": status, "progress": 0}

    return jsonify(result)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Download 3D Model
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/download-model")
def api_download_model():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Please log in first."}), 403

    task_id = request.args.get("task_id", "").strip()
    fmt = request.args.get("format", "glb").strip().lower()

    if not task_id:
        return jsonify({"ok": False, "error": "Missing task_id parameter."}), 400

    with get_db() as conn:
        task = conn.execute(
            "SELECT result_url FROM generation_tasks WHERE job_id=? AND status='completed'",
            (task_id,),
        ).fetchone()

    if not task or not task["result_url"]:
        return jsonify({"ok": False, "error": "Model not found or not yet completed."}), 404

    result_url = task["result_url"]

    # If result_url is a local path, serve the file
    if result_url.startswith("/uploads/models/"):
        filepath = os.path.join(app.root_path, result_url.lstrip("/"))
        if os.path.exists(filepath):
            filename = f"model_{task_id}.{fmt}"
            return send_from_directory(
                os.path.dirname(filepath),
                os.path.basename(filepath),
                as_attachment=True,
                download_name=filename,
                mimetype="model/gltf-binary" if fmt == "glb" else "application/octet-stream",
            )

    # Otherwise proxy from upstream
    # Extract raw URL from proxy URL pattern: /api/proxy-3d?url=xxx
    if result_url.startswith("/api/proxy-3d?url="):
        raw_url = result_url[len("/api/proxy-3d?url="):]
        try:
            resp = requests.get(raw_url, timeout=60)
            if resp.status_code == 200:
                filename = f"model_{task_id}.{fmt}"
                content_type = "model/gltf-binary" if fmt == "glb" else "application/octet-stream"
                return resp.content, 200, {
                    "Content-Type": content_type,
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Access-Control-Allow-Origin": "*",
                }
        except Exception as e:
            return jsonify({"ok": False, "error": f"Download failed: {e}"}), 502

    return jsonify({"ok": False, "error": "Model source unavailable."}), 404


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Static uploads
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/uploads/chat/<path:filename>")
def uploaded_chat_file(filename):
    return send_from_directory(CHAT_UPLOAD_DIR, filename)


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Proxy for 3D models (CORS bypass)
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/proxy-3d")
def api_proxy_3d():
    url = request.args.get("url")
    if not url:
        return jsonify({"ok": False, "error": "Missing 'url' parameter."}), 400

    # Security: only proxy Tencent Cloud 3D model URLs
    from urllib.parse import urlparse
    parsed = urlparse(url)
    ALLOWED_HOSTS = {"api.ai3d.cloud.tencent.com", "ai3d.cloud.tencent.com"}
    if parsed.hostname not in ALLOWED_HOSTS:
        return jsonify({"ok": False, "error": "Invalid model URL domain."}), 403

    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"Upstream error {resp.status_code}"}), 502

        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        if "glb" in url.lower() or url.lower().endswith(".glb"):
            content_type = "model/gltf-binary"
        elif "obj" in url.lower() or url.lower().endswith(".obj") or url.lower().endswith(".zip"):
            content_type = "application/octet-stream"

        return resp.content, 200, {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        }
    except requests.RequestException as exc:
        app.logger.error("Proxy request failed: %s", exc)
        return jsonify({"ok": False, "error": "Proxy request failed."}), 502


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Chat image upload
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/upload-chat-image", methods=["POST"])
def api_upload_chat_image():
    cid = session.get("customer_id")
    if not cid:
        return jsonify({"ok": False, "error": "Please log in first."}), 403

    image_file = request.files.get("image")
    if not image_file or not image_file.filename:
        return jsonify({"ok": False, "error": "No image provided."}), 400

    if not allowed_image(image_file.filename):
        return jsonify({"ok": False, "error": "Unsupported image format."}), 400

    ext = image_file.filename.rsplit(".", 1)[1].lower()
    filename = f"chat_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(CHAT_UPLOAD_DIR, filename)
    image_file.save(filepath)

    return jsonify({
        "ok": True,
        "image_path": f"/uploads/chat/{filename}",
        "url": url_for("uploaded_chat_file", filename=filename, _external=True),
    })


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Customer Messaging
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@app.route("/api/messages", methods=["GET"])
def api_get_messages():
    cid = session.get("customer_id")
    if not cid:
        return jsonify({"ok": False, "error": "Not logged in."}), 401

    # Check if user is banned
    try:
        banned_row = get_db().execute("SELECT banned FROM customers WHERE id=?", (cid,)).fetchone()
        if banned_row and banned_row["banned"]:
            return jsonify({"ok": True, "messages": [{"sender": "system", "content": "Your account has been restricted. Please contact support.", "created_at": "", "image_path": ""}]})
    except:
        pass

    with get_db() as conn:
        # Mark admin/system messages as read when customer views them
        conn.execute(
            "UPDATE messages SET is_read=1 WHERE customer_id=? AND sender IN ('admin','system') AND is_read=0",
            (cid,),
        )
        rows = conn.execute(
            "SELECT id, sender, content, image_path, created_at, is_read FROM messages "
            "WHERE customer_id=? ORDER BY created_at ASC",
            (cid,),
        ).fetchall()

    return jsonify({
        "ok": True,
        "messages": [dict(r) for r in rows],
    })
    
        
@app.route("/api/messages", methods=["POST"])
def api_send_message():
    cid = session.get("customer_id")
    if not cid:
        return jsonify({"ok": False, "error": "Please log in first."}), 401

    # Support both JSON and multipart/form-data
    if request.is_json:
        data = request.get_json(force=True, silent=True) or {}
        content = (data.get("content") or "").strip()
        image_path = (data.get("image_path") or "").strip()
    else:
        content = (request.form.get("content") or "").strip()
        image_path = ""
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            if not allowed_image(image_file.filename):
                return jsonify({"ok": False, "error": "Unsupported image format."}), 400
            ext = image_file.filename.rsplit(".", 1)[1].lower()
            filename = f"chat_{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(CHAT_UPLOAD_DIR, filename)
            image_file.save(filepath)
            image_path = f"/uploads/chat/{filename}"

    if not content and not image_path:
        return jsonify({"ok": False, "error": "Message cannot be empty."}), 400

    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (customer_id, sender, content, image_path) VALUES (?, 'customer', ?, ?)",
            (cid, content, image_path),
        )
    return jsonify({"ok": True, "image_path": image_path or None})


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Admin panel
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?


@app.route("/api/quick-replies", methods=["GET", "POST"])
def api_quick_replies():
    """Get or add quick replies."""
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"ok": False, "error": "Content is required"})
        conn = get_db()
        # Check if table exists, create if not
        conn.execute("CREATE TABLE IF NOT EXISTS quick_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL)")
        conn.execute("INSERT INTO quick_replies (content) VALUES (?)", (content,))
        conn.commit()
        return jsonify({"ok": True})
    
    # GET - return all quick replies
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS quick_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL)")
    rows = conn.execute("SELECT content FROM quick_replies ORDER BY id").fetchall()
    replies = [row["content"] for row in rows]
    return jsonify({"ok": True, "replies": replies})

@app.route("/api/quick-replies/<int:index>", methods=["DELETE"])
def api_delete_quick_reply(index):
    """Delete a quick reply by index."""
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS quick_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL)")
    rows = conn.execute("SELECT id FROM quick_replies ORDER BY id").fetchall()
    if index < 0 or index >= len(rows):
        return jsonify({"ok": False, "error": "Invalid index"})
    target_id = rows[index]["id"]
    conn.execute("DELETE FROM quick_replies WHERE id=?", (target_id,))
    conn.commit()
    return jsonify({"ok": True})


@app.route("/admin")
def admin_page():
    if not session.get("admin_logged_in"):
        return render_template("admin_login.html")
    return render_template("admin.html")

@app.route("/admin/traffic")
def admin_traffic_page():
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')
    return render_template('admin.html')

@app.route('/test')
def test_page():
    return render_template('test.html')

@app.route("/api/notifications")
def api_notifications():
    if not is_logged_in():
        return jsonify({"ok": True, "unread": 0, "generation_done": False, "has_completed_model": False, "latest_task_id": None})

    cid = session.get("customer_id")
    with get_db() as conn:
        unread = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE customer_id=? AND sender IN ('admin','system') AND is_read=0",
            (cid,),
        ).fetchone()["cnt"]

        completed_task = conn.execute(
            "SELECT job_id AS task_id FROM generation_tasks WHERE customer_id=? AND status='completed' ORDER BY completed_at DESC LIMIT 1",
            (cid,),
        ).fetchone()

    return jsonify({
        "ok": True,
        "unread": unread,
        "has_completed_model": completed_task is not None,
        "latest_task_id": completed_task["task_id"] if completed_task else None,
    })

@app.route("/api/me")
def api_me():
    if is_logged_in():
        return jsonify({
            "ok": True,
            "logged_in": True,
            "name": session.get("contact_name", ""),
            "email": session.get("contact_email", ""),
        })
    return jsonify({"ok": True, "logged_in": False})


# 鈹€鈹€ Main 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

@app.route("/api/my-models")
def api_my_models():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "Not logged in"}), 401

    cid = session.get("customer_id")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT job_id AS task_id, status, input_text AS prompt, "
            "preview_image_url AS thumbnail_url, completed_at "
            "FROM generation_tasks WHERE customer_id=? "
            "ORDER BY created_at DESC",
            (cid,),
        ).fetchall()

    models = []
    for r in rows:
        d = dict(r)
        if d["prompt"] and len(d["prompt"]) > 30:
            d["prompt"] = d["prompt"][:30]
        models.append(d)

    return jsonify({"ok": True, "models": models})

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)

