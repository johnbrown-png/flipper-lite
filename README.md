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
- Optional webhook destination via environment variable:

```bash
FLIPPER_ANALYTICS_WEBHOOK_URL=https://your-endpoint.example/collect
```

If the webhook is set, each event is POSTed as JSON.
On Streamlit Community Cloud, you can also set the same key in app secrets.

### TikTok link format (recommended)

Use tagged URLs in TikTok so app-side attribution can be joined with ad-platform data:

```text
https://www.flipper.school/?utm_source=tiktok&utm_medium=paid_social&utm_campaign=summer_test
```

You can also include TikTok click id if available:

```text
https://www.flipper.school/?utm_source=tiktok&utm_medium=paid_social&utm_campaign=summer_test&ttclid=__CLICK_ID__
```

