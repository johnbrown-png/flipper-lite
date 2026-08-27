"""Private Streamlit dashboard for Flipper analytics."""

from __future__ import annotations

import os
import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from urllib import request, error

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
EVENTS_JSONL = PROJECT_ROOT / "data" / "analytics" / "events.jsonl"
EVENTS_DB = PROJECT_ROOT / "data" / "analytics" / "events.db"


st.set_page_config(page_title="Flipper Analytics", page_icon="📊", layout="wide")


def _get_password_from_config() -> str:
    env_value = os.getenv("ANALYTICS_DASHBOARD_PASSWORD", "").strip()
    if env_value:
        return env_value
    try:
        secret_value = str(st.secrets.get("ANALYTICS_DASHBOARD_PASSWORD", "")).strip()
        return secret_value
    except Exception:
        return ""


def _require_login() -> None:
    required_password = _get_password_from_config()
    if not required_password:
        st.error("Dashboard password is not configured. Set ANALYTICS_DASHBOARD_PASSWORD in environment or Streamlit secrets.")
        st.stop()

    if st.session_state.get("analytics_auth_ok"):
        return

    st.title("Private Analytics Login")
    entered = st.text_input("Password", type="password")
    if st.button("Enter"):
        if entered == required_password:
            st.session_state.analytics_auth_ok = True
            st.rerun()
        else:
            st.error("Invalid password")
    st.stop()


def _load_events_from_db(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()

    query = """
        SELECT
            timestamp_utc,
            app,
            session_id,
            event_name,
            utm_source,
            utm_medium,
            utm_campaign,
            ttclid,
            referrer,
            user_agent,
            payload_json
        FROM events
    """

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        return df

    df["query.utm_source"] = df["utm_source"].fillna("")
    df["query.utm_medium"] = df["utm_medium"].fillna("")
    df["query.utm_campaign"] = df["utm_campaign"].fillna("")
    df["query.ttclid"] = df["ttclid"].fillna("")

    def extract_video_id(payload_str: str) -> str:
        try:
            payload = json.loads(payload_str)
            props = payload.get("properties", {}) if isinstance(payload, dict) else {}
            return str(props.get("video_id", ""))
        except Exception:
            return ""

    def extract_send_status(payload_str: str) -> str:
        try:
            payload = json.loads(payload_str)
            props = payload.get("properties", {}) if isinstance(payload, dict) else {}
            return str(props.get("send_status", ""))
        except Exception:
            return ""

    df["video_id"] = df["payload_json"].apply(extract_video_id)
    df["send_status"] = df["payload_json"].apply(extract_send_status)
    return df


def _load_events_from_jsonl(jsonl_path: Path) -> pd.DataFrame:
    if not jsonl_path.exists():
        return pd.DataFrame()

    rows = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    if not rows:
        return pd.DataFrame()

    df = pd.json_normalize(rows)

    if "query.utm_source" not in df.columns:
        df["query.utm_source"] = ""
    if "query.utm_medium" not in df.columns:
        df["query.utm_medium"] = ""
    if "query.utm_campaign" not in df.columns:
        df["query.utm_campaign"] = ""
    if "query.ttclid" not in df.columns:
        df["query.ttclid"] = ""
    if "properties.video_id" in df.columns:
        df["video_id"] = df["properties.video_id"].fillna("")
    else:
        df["video_id"] = ""
    if "properties.send_status" in df.columns:
        df["send_status"] = df["properties.send_status"].fillna("")
    else:
        df["send_status"] = ""
    return df


def _get_remote_url() -> str:
    env_value = os.getenv("ANALYTICS_REMOTE_URL", "").strip()
    if env_value:
        return env_value
    try:
        return str(st.secrets.get("ANALYTICS_REMOTE_URL", "")).strip()
    except Exception:
        return ""


def _get_remote_token() -> str:
    env_value = os.getenv("ANALYTICS_REMOTE_TOKEN", "").strip()
    if env_value:
        return env_value
    try:
        return str(st.secrets.get("ANALYTICS_REMOTE_TOKEN", "")).strip()
    except Exception:
        return ""


def _load_events_from_remote(base_url: str, token: str) -> tuple[pd.DataFrame, str]:
    """Fetch events from a deployed analytics_webhook_server.py over HTTPS.

    This is what lets a locally run dashboard see traffic from the real,
    publicly deployed Streamlit Cloud app instead of only this machine's
    local data/analytics files.
    """
    url = base_url.rstrip("/") + "/events"
    headers = {}
    if token:
        headers["X-Analytics-Token"] = token
    try:
        req = request.Request(url, headers=headers, method="GET")
        with request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, TimeoutError, ValueError) as exc:
        return pd.DataFrame(), f"Remote fetch failed ({url}): {exc}"

    if not rows:
        return pd.DataFrame(), ""

    df = pd.json_normalize(rows)
    if "query.utm_source" not in df.columns:
        df["query.utm_source"] = ""
    if "query.utm_medium" not in df.columns:
        df["query.utm_medium"] = ""
    if "query.utm_campaign" not in df.columns:
        df["query.utm_campaign"] = ""
    if "query.ttclid" not in df.columns:
        df["query.ttclid"] = ""
    if "properties.video_id" in df.columns:
        df["video_id"] = df["properties.video_id"].fillna("")
    else:
        df["video_id"] = ""
    if "properties.send_status" in df.columns:
        df["send_status"] = df["properties.send_status"].fillna("")
    else:
        df["send_status"] = ""
    return df, ""


def _load_events() -> tuple[pd.DataFrame, str]:
    remote_url = _get_remote_url()
    if remote_url:
        df, fetch_error = _load_events_from_remote(remote_url, _get_remote_token())
        if fetch_error:
            st.error(
                f"ANALYTICS_REMOTE_URL is configured but could not be reached: {fetch_error}\n\n"
                "Falling back to local files, which will NOT contain traffic from the "
                "deployed app."
            )
        else:
            return df, "remote"
    if EVENTS_DB.exists():
        return _load_events_from_db(EVENTS_DB), "sqlite"
    return _load_events_from_jsonl(EVENTS_JSONL), "jsonl"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out["timestamp_utc"] = pd.to_datetime(out["timestamp_utc"], errors="coerce", utc=True)
    out = out.dropna(subset=["timestamp_utc"])
    out["date"] = out["timestamp_utc"].dt.date

    out["source"] = out["query.utm_source"].astype(str).str.strip()
    out.loc[out["source"] == "", "source"] = "direct_or_unknown"

    out["campaign"] = out["query.utm_campaign"].astype(str).str.strip()
    out.loc[out["campaign"] == "", "campaign"] = "none"

    return out


def _render_dashboard(df: pd.DataFrame, source_backend: str) -> None:
    st.title("Flipper Analytics Dashboard")
    st.caption(f"Data backend: {source_backend} | Rows: {len(df)}")
    if source_backend in ("sqlite", "jsonl"):
        st.warning(
            "Reading from local files on this machine. If flipper_lite.py is deployed "
            "on Streamlit Community Cloud, that app's events live on Streamlit's own "
            "servers, not here — set ANALYTICS_REMOTE_URL / ANALYTICS_REMOTE_TOKEN "
            "(pointing at your deployed analytics_webhook_server.py) to see real traffic."
        )

    if df.empty:
        st.warning("No analytics events found yet.")
        return

    min_date = df["date"].min()
    max_date = df["date"].max()
    today = pd.Timestamp.utcnow().date()
    calendar_min = min(min_date, today - timedelta(days=30))
    calendar_max = max(max_date, today)
    default_end = calendar_max
    default_start = max(calendar_min, default_end - timedelta(days=6))

    col_left, col_right = st.columns([2, 1])
    with col_left:
        date_range = st.date_input(
            "Date range",
            value=(default_start, default_end),
            min_value=calendar_min,
            max_value=calendar_max,
        )
    with col_right:
        source_filter = st.multiselect("Source", options=sorted(df["source"].unique()), default=sorted(df["source"].unique()))

    # Streamlit date_input can return scalar date, list/tuple, or nested tuple/list.
    raw_range = date_range
    if isinstance(raw_range, (list, tuple)) and len(raw_range) == 1 and isinstance(raw_range[0], (list, tuple)):
        raw_range = raw_range[0]

    if isinstance(raw_range, (list, tuple)):
        if len(raw_range) >= 2:
            start_date, end_date = raw_range[0], raw_range[1]
        elif len(raw_range) == 1:
            start_date = end_date = raw_range[0]
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date = end_date = raw_range

    def _coerce_date(value, fallback):
        if isinstance(value, (list, tuple)):
            value = value[0] if value else fallback
        coerced = pd.to_datetime(value, errors="coerce")
        if pd.isna(coerced):
            return fallback
        return coerced.date()

    start_date = _coerce_date(start_date, min_date)
    end_date = _coerce_date(end_date, max_date)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    filtered = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    if source_filter:
        filtered = filtered[filtered["source"].isin(source_filter)]

    if filtered.empty:
        st.info(
            f"No events in selected range. Data currently available from {min_date} to {max_date}."
        )

    total_events = int(len(filtered))
    unique_sessions = int(filtered["session_id"].nunique())
    page_views = int((filtered["event_name"] == "page_view").sum())
    searches = int((filtered["event_name"] == "search_submitted").sum())
    video_events = int(filtered[filtered["event_name"].isin(["video_opened", "video_link_clicked"])].shape[0])
    email_requests = int((filtered["event_name"] == "email_recommendations_requested").sum())

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Events", f"{total_events:,}")
    k2.metric("Sessions", f"{unique_sessions:,}")
    k3.metric("Page views", f"{page_views:,}")
    k4.metric("Searches", f"{searches:,}")
    k5.metric("Video actions", f"{video_events:,}")
    k6.metric("Email requests", f"{email_requests:,}")

    trend = filtered.groupby("date").agg(events=("event_name", "count"), sessions=("session_id", "nunique")).reset_index()
    st.subheader("Daily Trend")
    st.line_chart(trend.set_index("date")[["events", "sessions"]])

    st.subheader("Event Funnel")
    funnel_order = ["page_view", "search_submitted", "search_results_rendered", "video_opened", "video_link_clicked"]
    funnel = (
        filtered[filtered["event_name"].isin(funnel_order)]
        .groupby("event_name")
        .size()
        .reindex(funnel_order, fill_value=0)
        .reset_index(name="count")
    )
    st.bar_chart(funnel.set_index("event_name")["count"])

    st.subheader("Source Performance")
    source_perf = (
        filtered.groupby("source")
        .agg(
            sessions=("session_id", "nunique"),
            events=("event_name", "count"),
            video_actions=("event_name", lambda s: int(s.isin(["video_opened", "video_link_clicked"]).sum())),
        )
        .sort_values("sessions", ascending=False)
    )
    st.dataframe(source_perf, use_container_width=True)

    st.subheader("TikTok Campaigns")
    tiktok = filtered[(filtered["source"] == "tiktok") | (filtered["query.ttclid"].astype(str).str.strip() != "")]
    if tiktok.empty:
        st.info("No TikTok-attributed data in current filter.")
    else:
        campaign_perf = (
            tiktok.groupby("campaign")
            .agg(
                sessions=("session_id", "nunique"),
                events=("event_name", "count"),
                searches=("event_name", lambda s: int((s == "search_submitted").sum())),
                video_actions=("event_name", lambda s: int(s.isin(["video_opened", "video_link_clicked"]).sum())),
            )
            .sort_values("sessions", ascending=False)
        )
        st.dataframe(campaign_perf, use_container_width=True)

    st.subheader("Top Videos")
    top_videos = (
        filtered[filtered["video_id"].astype(str).str.strip() != ""]
        .groupby("video_id")
        .size()
        .reset_index(name="events")
        .sort_values("events", ascending=False)
        .head(20)
    )
    st.dataframe(top_videos, use_container_width=True)

    st.subheader("Email Recommendations")
    email_events = filtered[filtered["event_name"] == "email_recommendations_requested"]
    if email_events.empty:
        st.info("No 'email me these videos' requests in the current filter. No email addresses are ever stored — only a one-way hash is recorded per request.")
    else:
        sent = int((email_events["send_status"] == "sent").sum())
        failed = int((email_events["send_status"] == "failed").sum())
        unique_requesters = int(email_events["session_id"].nunique())
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("Requests", f"{len(email_events):,}")
        ec2.metric("Sent OK", f"{sent:,}")
        ec3.metric("Failed", f"{failed:,}")
        st.caption(f"From {unique_requesters:,} distinct sessions. Address is never stored — only a SHA-256 hash is logged per request.")
        email_trend = email_events.groupby("date").size().reset_index(name="requests")
        st.line_chart(email_trend.set_index("date")["requests"])

    export_df = filtered.copy()
    csv_data = export_df.to_csv(index=False)
    st.download_button("Download filtered CSV", data=csv_data, file_name="flipper_analytics_filtered.csv", mime="text/csv")


def main() -> None:
    _require_login()
    raw_df, backend = _load_events()
    df = _prepare(raw_df)
    _render_dashboard(df, backend)


if __name__ == "__main__":
    main()
