# 🔍 Flipper Lite - Curriculum Video Browser

A lightweight, fast web application that helps teachers discover high-quality educational videos aligned to the **White Rose Maths curriculum**.

## ✨ Features

- 🎯 **Curriculum-Aligned**: Browse videos by Year Group, Block, and Small Step
- ⚡ **Lightning Fast**: Pre-computed recommendations load instantly
- 📱 **Mobile-Friendly**: Works on phones, tablets, and desktops
- 🎓 **Quality-Scored**: All videos rated for educational value
- 🚀 **Zero Setup**: No API keys, no installation required

## 🌐 Try It Live

**Coming soon**: [flipper-curriculum.streamlit.app](https://flipper-curriculum.streamlit.app)

## 🏫 Perfect For

- Teachers planning lessons
- Parents supporting home learning
- Tutors finding topic-specific videos
- Schools building resource libraries

## 🛠️ Technology

Built with **Streamlit** for simplicity and speed. No heavy AI dependencies means instant loading and zero cost hosting.

## 💻 Run Locally

```bash
# Install dependencies (only 2 packages!)
pip install -r requirements_tier1.txt

# Launch the app
streamlit run flipper_lite.py
```

Visit `http://localhost:8501` in your browser.

## 📊 How It Works

1. **Pre-computation**: Videos are analyzed once using semantic search and LLM evaluation
2. **CSV Storage**: Best recommendations stored in a simple spreadsheet
3. **Fast Lookup**: App simply reads the CSV - no AI processing at runtime

## 📚 Data Source

Videos curated from educational YouTube channels, with each video scored for:
- Curriculum alignment accuracy
- Teaching quality
- Age-appropriateness
- Content clarity

## 🎯 Curriculum Coverage

- **White Rose Maths** curriculum structure
- Year groups from Reception to Year 6
- All blocks and small steps covered
- Regular updates as curriculum evolves

## 🤝 Contributing

This is a personal project to help teachers. Feedback welcome!

## 📝 License

Educational use. Videos remain property of their respective creators.

## 👨‍💻 About

Created to make finding quality maths teaching videos effortless. Built as **Tier 1** of a two-tier architecture - simple, fast, and free forever.

## 📈 Analytics and Traffic Attribution

TikTok click counts and Streamlit app metrics often differ. Common causes:
- Link preview bots and quick bounces count as clicks in ad platforms
- User leaves before Streamlit fully initializes
- Multiple clicks from one person in TikTok count differently from app sessions

This project now includes lightweight event tracking in both `flipper.py` and `flipper_lite.py`.

### What is tracked

- `page_view` (once per session)
- `search_submitted` and `search_results_rendered` (Flipper)
- `step_selection_applied` and step navigation events (Flipper Lite)
- `video_opened` / `video_link_clicked`
- Basic attribution params from URL (`utm_*`, `ttclid`, `gclid`, `fbclid`)

### Where events go

- Local JSONL log: `data/analytics/events.jsonl`
- Optional webhook destination via environment variable or secrets:

```bash
FLIPPER_ANALYTICS_WEBHOOK_URL=https://your-endpoint.example/collect
FLIPPER_ANALYTICS_WEBHOOK_TOKEN=replace_with_shared_token
```

If the webhook is set, each event is POSTed as JSON.

**Important:** when `flipper_lite.py` is deployed on Streamlit Community Cloud, that
app runs on Streamlit's own servers with its own ephemeral, non-persistent
filesystem — it is a *different machine* from the one you develop on. This means:

- The local `.streamlit/secrets.toml` file on your PC (gitignored, never pushed to
  git) has **no effect on the deployed app**. To configure the deployed app you must
  set secrets in the Streamlit Community Cloud dashboard for that specific app:
  **share.streamlit.io → your app → Settings → Secrets**.
- `data/analytics/events.jsonl` written by the deployed app lives only inside that
  app's container and resets whenever the app redeploys or wakes from sleep. Your
  local `analytics_dashboard.py` can never read it directly from disk.
- To see real traffic from the deployed app, `FLIPPER_ANALYTICS_WEBHOOK_URL` must
  point at a webhook receiver on a host that is (a) publicly reachable over the
  internet and (b) not your own PC/localhost (Streamlit Cloud cannot reach a
  private/home network address).

### Durable historical storage (implemented)

Use the webhook receiver to store events in SQLite:

```bash
python analytics_webhook_server.py --host 0.0.0.0 --port 8787 --token your_shared_token
```

Webhook receiver endpoints:
- `POST /collect` (stores event)
- `GET /events` (returns stored events as JSON; requires `X-Analytics-Token` header
  or `?token=` query param when `--token` is set) — used by `analytics_dashboard.py`
  to read real traffic remotely
- `GET /health` (health check)

SQLite output:
- `data/analytics/events.db` (override with `ANALYTICS_DB_PATH` env var)

Then point the **deployed app's** Streamlit Cloud secrets (not your local
`secrets.toml`) at your receiver:

```bash
FLIPPER_ANALYTICS_WEBHOOK_URL=https://your-receiver.example/collect
FLIPPER_ANALYTICS_WEBHOOK_TOKEN=your_shared_token
```

#### Deploying the receiver (Fly.io free tier, persistent volume)

`analytics_webhook_server.py` has no external dependencies, so any host that can run
Python works. Fly.io is recommended because its free tier includes a small
**persistent volume**, so the SQLite file survives restarts (unlike most free
web-service tiers, which wipe local disk on every redeploy/sleep cycle).

```bash
fly launch --config fly.analytics.toml --dockerfile Dockerfile.analytics --no-deploy
fly volumes create analytics_data --size 1
fly secrets set ANALYTICS_TOKEN=your_shared_token --config fly.analytics.toml
fly deploy --config fly.analytics.toml
```

Then set on the **deployed flipper_lite app** (share.streamlit.io → Settings → Secrets):

```toml
FLIPPER_ANALYTICS_WEBHOOK_URL = "https://<your-fly-app>.fly.dev/collect"
FLIPPER_ANALYTICS_WEBHOOK_TOKEN = "your_shared_token"
```

And locally (or in your local `.streamlit/secrets.toml`) so `analytics_dashboard.py`
can pull the same data over HTTPS:

```toml
ANALYTICS_REMOTE_URL = "https://<your-fly-app>.fly.dev"
ANALYTICS_REMOTE_TOKEN = "your_shared_token"
```

### Private analytics dashboard (implemented)


Run the dashboard:

```bash
streamlit run analytics_dashboard.py
```

or on Windows:

```bash
launch_analytics_dashboard.bat
```

Set dashboard access password:

```bash
ANALYTICS_DASHBOARD_PASSWORD=your_private_password
```

Dashboard behavior:
- Requires password before showing any data
- If `ANALYTICS_REMOTE_URL` is set, fetches events from that webhook receiver's
  `GET /events` endpoint first (this is the only way to see traffic from a
  Streamlit Cloud-deployed app) — shows an on-screen error if the fetch fails
- Otherwise reads `data/analytics/events.db` when available (preferred)
- Falls back to `data/analytics/events.jsonl` if DB is missing
- Includes KPI cards, daily trend, event funnel, source table, TikTok campaign table, top video table, CSV export
- Shows a warning banner whenever it falls back to local files, since local files
  never contain traffic from a separately deployed app

### Troubleshooting: dashboard shows no real traffic

If you visited the deployed app yourself and the dashboard still shows nothing:

1. Confirm secrets are set on the **deployed app itself**
   (share.streamlit.io → your app → Settings → Secrets), not just your local
   `.streamlit/secrets.toml` — the two are unrelated.
2. Confirm `FLIPPER_ANALYTICS_WEBHOOK_URL` points at a **publicly reachable**
   receiver (not `localhost`/a home IP) that is actually running right now.
3. Check the deployed app's logs (share.streamlit.io → Manage app → logs) for
   `[analytics] webhook delivery failed ...` lines — these now print the exact
   delivery error instead of failing silently.
4. Set `ANALYTICS_REMOTE_URL` / `ANALYTICS_REMOTE_TOKEN` for
   `analytics_dashboard.py` so it reads the receiver directly over HTTPS instead
   of local files.
5. Test the receiver directly: `curl https://<receiver>/health` should return
   `{"status":"ok"}`, and `curl -H "X-Analytics-Token: <token>" https://<receiver>/events`
   should return the JSON events array.

### TikTok link format (recommended)

Use tagged URLs in TikTok so app-side attribution can be joined with ad-platform data:

```text
https://www.flipper.school/?utm_source=tiktok&utm_medium=paid_social&utm_campaign=summer_test
```

You can also include TikTok click id if available:

```text
https://www.flipper.school/?utm_source=tiktok&utm_medium=paid_social&utm_campaign=summer_test&ttclid=__CLICK_ID__
```

