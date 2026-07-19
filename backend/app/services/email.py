"""
Email service — multi-provider with graceful fallback.

Supported transports (auto-detected by env vars):
  - SMTP          (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM)
  - SendGrid      (SENDGRID_API_KEY, SENDGRID_FROM)
  - Console (dev) — no provider configured; emails are logged to stdout.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _render(template: str, **vars: Any) -> str:
    """Tiny placeholder renderer: replaces {{key}} occurrences."""
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


# ─── Public templates ────────────────────────────────────────────
VERIFY_EMAIL_TEMPLATE = """
<html><body style="font-family:sans-serif;line-height:1.6">
  <h2 style="color:#0ea5e9">Verify your email</h2>
  <p>Hi {{name}},</p>
  <p>Please confirm your email address by clicking the link below.</p>
  <p><a href="{{link}}" style="background:#0ea5e9;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">Verify Email</a></p>
  <p>If you didn't request this, you can ignore this email.</p>
  <p style="color:#9ca3af;font-size:12px">The link expires in 24 hours.</p>
</body></html>
""".strip()

PASSWORD_RESET_TEMPLATE = """
<html><body style="font-family:sans-serif;line-height:1.6">
  <h2 style="color:#ef4444">Reset your password</h2>
  <p>Hi {{name}},</p>
  <p>We received a request to reset your password. Click the link below to choose a new one.</p>
  <p><a href="{{link}}" style="background:#ef4444;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">Reset Password</a></p>
  <p>If you didn't request this, you can safely ignore this email.</p>
  <p style="color:#9ca3af;font-size:12px">The link expires in 1 hour.</p>
</body></html>
""".strip()


# ─── Transports ──────────────────────────────────────────────────
async def _send_smtp(to: str, subject: str, html: str) -> bool:
    host = settings.smtp_host
    port = settings.smtp_port
    user = settings.smtp_username
    password = settings.smtp_password
    sender = settings.smtp_from or (user or "noreply@example.com")
    if not host:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content("This email requires an HTML-compatible client.")
    msg.add_alternative(html, subtype="html")

    def _send():
        try:
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.starttls()
                if user and password:
                    smtp.login(user, password)
                smtp.send_message(msg)
            return True
        except Exception as exc:
            logger.error("smtp_send_failed", error=str(exc))
            return False

    return await asyncio.to_thread(_send)


async def _send_sendgrid(to: str, subject: str, html: str) -> bool:
    api_key = settings.sendgrid_api_key
    sender = settings.sendgrid_from
    if not api_key or not sender:
        return False
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send.json",
                json=payload,
                headers=headers,
            )
            return resp.status_code in (200, 202)
    except Exception as exc:
        logger.error("sendgrid_send_failed", error=str(exc))
        return False


async def _send_console(to: str, subject: str, html: str) -> None:
    """Dev-mode fallback. Emits the message to the structured logs."""
    logger.warning(
        "email_console_mode",
        to=to,
        subject=subject,
        preview=html[:160],
        hint="Configure SMTP_* or SENDGRID_API_KEY to send real email.",
    )


# ─── Public API ──────────────────────────────────────────────────
async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an HTML email using the best available transport."""
    if not to:
        return False
    if settings.sendgrid_api_key:
        ok = await _send_sendgrid(to, subject, html)
        if ok:
            return True
    if settings.smtp_host:
        ok = await _send_smtp(to, subject, html)
        if ok:
            return True
    await _send_console(to, subject, html)
    return True


async def send_verification_email(to: str, name: str, link: str) -> None:
    html = _render(VERIFY_EMAIL_TEMPLATE, name=name or "there", link=link)
    await send_email(to, "Verify your email", html)


async def send_password_reset_email(to: str, name: str, link: str) -> None:
    html = _render(PASSWORD_RESET_TEMPLATE, name=name or "there", link=link)
    await send_email(to, "Reset your password", html)