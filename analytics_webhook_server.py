"""Minimal webhook receiver for Flipper analytics.

Run this process on an always-on host to store analytics events durably in SQLite.
No external dependencies required.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "analytics" / "events.db"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                received_utc TEXT NOT NULL,
                timestamp_utc TEXT,
                app TEXT,
                session_id TEXT,
                event_name TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                ttclid TEXT,
                referrer TEXT,
                user_agent TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp_utc)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name)
            """
        )
        conn.commit()


def insert_event(db_path: Path, payload: dict) -> bool:
    query = payload.get("query", {}) or {}
    event_id = str(payload.get("event_id", "")).strip()
    if not event_id:
        # Skip events without stable IDs; sender should provide this.
        return False

    row = (
        event_id,
        utc_now_iso(),
        str(payload.get("timestamp_utc", "")),
        str(payload.get("app", "")),
        str(payload.get("session_id", "")),
        str(payload.get("event_name", "")),
        str(query.get("utm_source", "")),
        str(query.get("utm_medium", "")),
        str(query.get("utm_campaign", "")),
        str(query.get("ttclid", "")),
        str(payload.get("referrer", "")),
        str(payload.get("user_agent", "")),
        json.dumps(payload, ensure_ascii=True),
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO events (
                event_id,
                received_utc,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        conn.commit()
        return conn.total_changes > 0


def build_handler(db_path: Path, token: str):
    class AnalyticsHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/") != "/collect":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            if token:
                req_token = self.headers.get("X-Analytics-Token", "")
                if req_token != token:
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b"Unauthorized")
                    return

            content_len = int(self.headers.get("Content-Length", "0"))
            if content_len <= 0:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing body")
                return

            raw = self.rfile.read(content_len)
            try:
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
            except Exception:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid JSON")
                return

            stored = insert_event(db_path, payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"ok": True, "stored": stored}
            self.wfile.write(json.dumps(response, ensure_ascii=True).encode("utf-8"))

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.rstrip("/") == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            # Keep output minimal for service logs.
            return

    return AnalyticsHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Flipper analytics webhook receiver.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite DB path")
    parser.add_argument("--token", default="", help="Shared token for X-Analytics-Token")
    args = parser.parse_args()

    db_path = Path(args.db)
    init_db(db_path)

    server = ThreadingHTTPServer((args.host, args.port), build_handler(db_path, args.token))
    print(f"Analytics webhook server listening on http://{args.host}:{args.port}")
    print(f"SQLite storage: {db_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
