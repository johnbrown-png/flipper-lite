"""Lightweight analytics helpers for Streamlit apps.

This module records basic product-analytics style events with optional webhook
forwarding. Events are also written to a local JSONL file for quick inspection.
"""

from __future__ import annotations

import json
import os
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_FILE = PROJECT_ROOT / "data" / "analytics" / "events.jsonl"
QUERY_KEYS = (
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "ttclid",
    "gclid",
    "fbclid",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_analytics_webhook_url() -> str:
    """Read webhook URL from env var or Streamlit secrets."""
    env_value = os.getenv("FLIPPER_ANALYTICS_WEBHOOK_URL", "").strip()
    if env_value:
        return env_value
    try:
        secret_value = str(st.secrets.get("FLIPPER_ANALYTICS_WEBHOOK_URL", "")).strip()
        return secret_value
    except Exception:
        return ""


def get_analytics_webhook_token() -> str:
    """Read optional webhook auth token from env var or Streamlit secrets."""
    env_value = os.getenv("FLIPPER_ANALYTICS_WEBHOOK_TOKEN", "").strip()
    if env_value:
        return env_value
    try:
        secret_value = str(st.secrets.get("FLIPPER_ANALYTICS_WEBHOOK_TOKEN", "")).strip()
        return secret_value
    except Exception:
        return ""


def _normalize_query_params() -> dict[str, str]:
    """Return a plain dict[str, str] from st.query_params."""
    normalized: dict[str, str] = {}
    try:
        for key in QUERY_KEYS:
            value = st.query_params.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                normalized[key] = str(value[0]) if value else ""
            else:
                normalized[key] = str(value)
    except Exception:
        return {}
    return normalized


def _extract_context_headers() -> dict[str, str]:
    """Best-effort extraction of request headers from Streamlit context."""
    headers: dict[str, str] = {}
    try:
        context = getattr(st, "context", None)
        raw_headers = getattr(context, "headers", None) if context else None
        if not raw_headers:
            return headers
        # Streamlit headers object behaves like a mapping.
        headers = {str(k).lower(): str(v) for k, v in dict(raw_headers).items()}
    except Exception:
        return {}
    return headers


def init_analytics(app_name: str) -> dict[str, Any]:
    """Initialize and return analytics session context in session_state."""
    if "analytics_session" not in st.session_state:
        st.session_state.analytics_session = {
            "session_id": str(uuid.uuid4()),
            "first_seen_utc": _utc_now_iso(),
            "app": app_name,
            "query": _normalize_query_params(),
            "once_keys": set(),
        }
    else:
        # Keep query params fresh so late arrivals with UTM are captured.
        st.session_state.analytics_session["query"] = _normalize_query_params()
        st.session_state.analytics_session["app"] = app_name
    return st.session_state.analytics_session


def _append_local_event(payload: dict[str, Any]) -> None:
    try:
        ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ANALYTICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        # Analytics should never break app behavior.
        pass


def _send_webhook_event(payload: dict[str, Any]) -> None:
    webhook_url = get_analytics_webhook_url()
    if not webhook_url:
        return
    webhook_token = get_analytics_webhook_token()
    headers = {"Content-Type": "application/json"}
    if webhook_token:
        headers["X-Analytics-Token"] = webhook_token
    try:
        req = request.Request(
            webhook_url,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=3):
            pass
    except (error.URLError, TimeoutError, ValueError):
        pass


def track_event(event_name: str, properties: dict[str, Any] | None = None, once_key: str | None = None) -> None:
    """Track an analytics event.

    Args:
        event_name: Event name, e.g. "page_view" or "search_submitted".
        properties: Event-specific payload.
        once_key: If provided, event emits at most once per session.
    """
    session = st.session_state.get("analytics_session")
    if not session:
        return

    once_keys = session.get("once_keys", set())
    if once_key and once_key in once_keys:
        return

    headers = _extract_context_headers()
    payload: dict[str, Any] = {
        "timestamp_utc": _utc_now_iso(),
        "app": session.get("app"),
        "session_id": session.get("session_id"),
        "first_seen_utc": session.get("first_seen_utc"),
        "event_name": event_name,
        "query": session.get("query", {}),
        "referrer": headers.get("referer", ""),
        "user_agent": headers.get("user-agent", ""),
        "properties": properties or {},
    }

    payload["event_id"] = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    if once_key:
        once_keys.add(once_key)
        session["once_keys"] = once_keys

    _append_local_event(payload)
    _send_webhook_event(payload)
