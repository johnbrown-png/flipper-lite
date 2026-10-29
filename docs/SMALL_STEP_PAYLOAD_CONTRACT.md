# Small Step Selection Payload Contract

Version: 1.0

Purpose:
- Define one shared payload shape for step selection events from Selector cards and Match cards.
- Keep video lookup, breadcrumbs, and Previous/Next step navigation aligned.
- Keep selection orchestration centralized in shared/step_selection.py.

Action:
- action must be: small_step_search

Payload object name used in code:
- curriculum_context (session state)
- pending_insertion / pending_step_nav (session state handoff)

Required fields:
- action: str
  - Allowed value: small_step_search
- year: str
- term: str
- topic: str
- age: str
- small_step_id: str

Strongly recommended fields (required for reliable step navigation and UI consistency):
- small_step: str
- small_step_desc: str
- small_step_full_desc: str
- difficulty: str (empty string allowed)
- small_step_num: int
- small_step_num_in_topic: int
- display_text: str

Optional compatibility fields:
- selection_source: str (selector | match | nav | unknown)
- small_step_name: str
- ss_desc: str
- ss_wr_desc: str
- lexical_score: float
- semantic_score: float
- combined_score: float
- display_small_step_num_in_topic: int

Behavior notes:
- Video lookup uses: year, term, difficulty, topic, small_step, small_step_id.
- Previous/Next navigation expects: age, topic, difficulty, and either:
  - small_step_id (preferred), or
  - small_step_num_in_topic (fallback)
- If navigation fields are missing or inconsistent with filtered topic rows, nav buttons may be hidden.

Producer responsibilities:
- Selector cards flow should emit a complete payload with navigation fields.
- Match cards flow may emit a partial payload initially, but should be expanded to full contract before assigning curriculum_context.
- Nav flow (Previous/Next) should emit payloads with selection_source=nav and navigation fields.

Consumer responsibilities:
- Before writing curriculum_context, normalize payload keys where possible.
- Preserve action as small_step_search for all step-selection flows.
- Apply deferred selector widget-key sync on next rerun before selector widgets instantiate.

Current implementation locations:
- Selector cards producer: search_app/curriculum_assistant.py
- Match cards producer: flipper_search/streamlit_ui.py
- Central selection orchestration: shared/step_selection.py
- App integration + UI composition: flipper_lite.py
