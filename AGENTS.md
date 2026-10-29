# Agent guide: Flipper

Read `README.md` first, then the doc for the module you are working in. These docs
describe the **current** system:

- Module A, Video Acquisition: `docs/acquisition.md`
- Module B, Curriculum: `docs/curriculum.md`
- Module C, Matching and QA: `docs/quality_assurance.md`
- Module D, Delivery (public app and analytics): `docs/delivery.md`

`docs/_history/` and `_archive/` describe superseded designs and retired code. Use them
for background only. Never treat them as the current spec or copy patterns from them.

## Do not move or rename (the deployed app reads these at fixed paths)

- `flipper_lite.py`, `requirements.txt`, `runtime.txt`, `.streamlit/config.toml`
- `precomputed_recommendations_flat_qa.csv`, `precomputed_recommendations_flat.csv`
- `Curriculum/Maths/curriculum_08052026_small_steps.csv`
- `shared/`, `search_app/`, `thoughtprompt/` (including `pilot_output/thought_prompts_multiplechoice.csv`), `flipper_search/`, `static/landing/`

Also shared by several modules, so move them only with every caller updated:
`channels.csv`, `extraction_state.json`, `search_history.json`,
`video_inventory/video_inventory.csv`, `query_embedder.py`, `data_pipeline/`.

## Working rules

- Run scripts from the project root. Many data paths are relative to it.
- After any change, run `.venv\Scripts\python.exe tools\smoke_test.py`. It makes no API calls.
- Precompute, the summariser and FAISS rebuilds call the paid OpenAI API. Extraction,
  topic search and the availability check use the YouTube Data API daily quota. Do not
  run them without asking.
- `data/`, `captions_output/`, source PDFs, `images/`, logs and archive CSVs are local
  only and not in git. Do not assume they exist on the deployed app.
- Pushing `main` redeploys the public app on Streamlit Cloud.
- Audience: UK teachers, parents and home-schoolers. Prefer clarity and curriculum
  relevance.
- Stay with the current stack: Python, Streamlit, Tkinter GUIs, FAISS, OpenAI. Do not
  propose React, mobile apps or microservices unless asked.
- Solutions must scale with thousands of long transcripts. Avoid anything linear in
  total embedding count at query time.
- Python style: snake_case. Do not propose scraping that breaks a site's terms of
  service.
