"""Transactional email helper for the "email me these videos" feature.

Uses the Resend HTTP API (https://resend.com) so sending works from hosts that
block outbound SMTP (e.g. Streamlit Community Cloud). No email address is
persisted by this module or by the caller — only a one-way hash should be
passed to analytics for measurement.
"""

from __future__ import annotations

import html
import json
import os
from typing import Any
from urllib import error, request

import streamlit as st

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM_ADDRESS = "Flipper School <recommendations@flipper.school>"
DEFAULT_REPLY_TO = "John.Brown@flipper.school"


def _get_secret(env_name: str, default: str = "") -> str:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    try:
        return str(st.secrets.get(env_name, "")).strip()
    except Exception:
        return default


def get_resend_api_key() -> str:
    return _get_secret("FLIPPER_RESEND_API_KEY")


def get_email_from_address() -> str:
    return _get_secret("FLIPPER_EMAIL_FROM", DEFAULT_FROM_ADDRESS)


def get_email_reply_to() -> str:
    return _get_secret("FLIPPER_EMAIL_REPLY_TO", DEFAULT_REPLY_TO)


def _build_email_html(step_label: str, small_step_desc: str, videos: list[dict[str, Any]]) -> str:
    rows = []
    for v in videos:
        video_id = str(v.get("video_id", "")).strip()
        title = html.escape(str(v.get("title", "")).strip())
        url = f"https://www.youtube.com/watch?v={video_id}"
        rows.append(
            f'<li style="margin-bottom:0.75rem;"><a href="{url}">{title}</a><br>'
            f'<span style="color:#6c757d; font-size:0.85rem;">{url}</span></li>'
        )
    rows_html = "".join(rows) if rows else "<li>No videos available.</li>"
    step_label_safe = html.escape(step_label)
    desc_safe = html.escape(small_step_desc) if small_step_desc else ""
    desc_html = f'<p style="color:#444;">{desc_safe}</p>' if desc_safe else ""
    return f"""
    <div style="font-family: Arial, sans-serif; color:#1e3a5f; max-width:560px;">
        <h2 style="color:#1e3a5f;">Your Flipper School video suggestions</h2>
        <p><strong>{step_label_safe}</strong></p>
        {desc_html}
        <ol style="padding-left:1.2rem;">{rows_html}</ol>
        <p style="color:#6c757d; font-size:0.8rem; margin-top:1.5rem;">
            Sent from Flipper School because you asked to email yourself these
            recommendations. Reply to this email with any questions.
        </p>
    </div>
    """


def send_video_recommendations_email(
    to_email: str,
    step_label: str,
    small_step_desc: str,
    videos: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Send the top video recommendations to the given address via Resend.

    Returns (success, error_message). Never logs or stores to_email itself.
    """
    api_key = get_resend_api_key()
    if not api_key:
        return False, "Email sending is not configured (missing API key)."

    payload = {
        "from": get_email_from_address(),
        "to": [to_email],
        "reply_to": get_email_reply_to(),
        "subject": f"Your Flipper School videos: {step_label}",
        "html": _build_email_html(step_label, small_step_desc, videos),
    }

    try:
        req = request.Request(
            RESEND_API_URL,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as resp:
            resp.read()
        return True, ""
    except error.HTTPError as exc:
        # HTTPError bodies from Resend describe the failure but do not echo the
        # recipient address, so this is safe to surface in the UI.
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        return False, f"Email API error ({exc.code}): {detail[:200]}"
    except Exception as exc:
        return False, f"Email send failed: {exc}"
