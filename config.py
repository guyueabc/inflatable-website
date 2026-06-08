"""Application configuration — edit keys before deployment."""

import os
import secrets
from datetime import timedelta

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

# ═══════════════════════════════════════════════════════════════════════════
#  Hunyuan 3D API — OpenAI-compatible (api.ai3d.cloud.tencent.com)
# ═══════════════════════════════════════════════════════════════════════════
HUNYUAN_API_KEY = os.getenv("HUNYUAN_API_KEY", "")
HUNYUAN_ENDPOINT = os.getenv("HUNYUAN_ENDPOINT", "https://api.ai3d.cloud.tencent.com")
HUNYUAN_MODEL = os.getenv("HUNYUAN_MODEL", "3.0")

# HK proxy — when set, submit/query calls are routed through this URL
# Format: "https://hk-proxy.example.com" (CloudFlare Tunnel domain)
# Leave empty to call Hunyuan API directly (single-node mode)
HUNYUAN_PROXY_URL = os.getenv("HUNYUAN_PROXY_URL", "")
HUNYUAN_PROXY_SECRET = os.getenv("HUNYUAN_PROXY_SECRET", "")

# ── Google OAuth ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ── Upload limits ───────────────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}

# ── Session ─────────────────────────────────────────────────────────────────
SESSION_TYPE = "filesystem"
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

# ── SMTP (Email Verification) ───────────────────────────────────────────────
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.mxhichina.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "465"))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "false").lower() == "true"
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "dulizhan@showlovein.com")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv(
    "MAIL_DEFAULT_SENDER",
    "InflatableModel <dulizhan@showlovein.com>",
)

# ── Admin ───────────────────────────────────────────────────────────────────
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "InflatableModel2024!Secure")
