"""
mailer.py — SMTP email sender for InflatableModel.CN
Supports QQ Mail / Gmail / custom SMTP. Falls back to dev mode if MAIL_PASSWORD is empty.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import config


def is_smtp_configured() -> bool:
    """Check if real SMTP credentials are available."""
    return bool(
        config.MAIL_SERVER
        and config.MAIL_USERNAME
        and config.MAIL_PASSWORD
    )


def send_verification_code(to_email: str, code: str) -> tuple[bool, Optional[str]]:
    """
    Send a verification code email.

    Returns:
        (success, error_message_or_None)
    """
    subject = "Your Verification Code — InflatableModel.CN"

    html_body = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;padding:40px 0;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;margin:0 auto;">
  <tr>
    <td style="background:linear-gradient(135deg,#6366f1,#7c3aed);padding:32px;border-radius:12px 12px 0 0;text-align:center;">
      <h1 style="color:#fff;font-size:22px;margin:0;">InflatableModel.CN</h1>
    </td>
  </tr>
  <tr>
    <td style="background:#fff;padding:32px;border-radius:0 0 12px 12px;box-shadow:0 4px 12px rgba(0,0,0,.08);">
      <p style="color:#475569;font-size:15px;margin:0 0 16px;">Hi,</p>
      <p style="color:#475569;font-size:15px;margin:0 0 24px;">Your verification code is:</p>
      <div style="text-align:center;margin:24px 0;">
        <span style="display:inline-block;background:#f1f5f9;padding:16px 40px;border-radius:8px;font-size:32px;font-weight:700;letter-spacing:6px;color:#6366f1;font-family:'Courier New',monospace;">{code}</span>
      </div>
      <p style="color:#94a3b8;font-size:13px;margin:0 0 8px;">This code expires in <strong>5 minutes</strong>.</p>
      <p style="color:#94a3b8;font-size:13px;margin:0;">If you did not request this code, please ignore this email.</p>
    </td>
  </tr>
</table>
</body>
</html>"""

    text_body = f"Your verification code is: {code}\n\nThis code expires in 5 minutes.\n\nIf you did not request this code, please ignore this email."

    if not is_smtp_configured():
        return False, "SMTP not configured — use dev mode"

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = config.MAIL_DEFAULT_SENDER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        if config.MAIL_USE_TLS:
            server = smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT, timeout=15)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(config.MAIL_SERVER, config.MAIL_PORT, timeout=15, context=context)

        server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        server.sendmail(config.MAIL_DEFAULT_SENDER, to_email, msg.as_string())
        server.quit()
        return True, None

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed — check MAIL_USERNAME and MAIL_PASSWORD"
    except smtplib.SMTPConnectError:
        return False, f"Cannot connect to {config.MAIL_SERVER}:{config.MAIL_PORT}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Unexpected error sending email: {e}"
