# Flipper Lite — UX Subproject: Project Brief

**Date:** May 2026  
**Owner:** Flipper Education Ltd  
**Status:** Pre-implementation — specification phase

---

## Background

Flipper Lite (`flipper_lite.py`) is a lightweight Streamlit web app that allows educators to browse
AI-curated YouTube videos aligned to the White Rose Mathematics curriculum. Videos are precomputed
and stored in a flat CSV; no runtime LLM or FAISS calls are made at browse time.

The current UX is a single-mode dropdown navigator: Year → Term → [Difficulty] → Topic → Small Step.
This works well for experienced users who know the curriculum, but does not serve learners or less
experienced educators who want to navigate the curriculum progressively and linearly.

---

## Goals

1. **Introduce two distinct navigation modes** that serve different user types without breaking the existing experience.
2. **Surface watched-video state** visually so users can track what they have already seen.
3. **Lay the architectural groundwork** for per-small-step exercises with optional progression gating.

---

## User Personas

### Persona A — The Expert Educator
- Knows the White Rose curriculum well
- Uses professional terminology (e.g. "mixed numbers", "column subtraction", "place value")
- Wants to jump directly to a specific small step as quickly as possible
- Values a clean, fast, uncluttered interface
- **Mode:** Laissez-Faire / Expert (Mode A) — essentially the current dropdown UX, possibly polished

### Persona B — The Sequential Learner (or Supporting Teacher)
- May be a student, a parent, or a less-experienced educator
- Wants to start at a known point and work forward through the curriculum one small step at a time
- Needs clear "next" / "back" controls rather than understanding the full hierarchy
- Will benefit from seeing which videos they have watched and knowing when they have completed a small step
- **Mode:** Linear / Sequential (Mode B) — new navigation mode

---

## Scope

### In scope
- Mode selection UI (toggle or tab between Expert and Sequential)
- Sequential mode navigation controls (Next/Prev video within step, Next/Prev small step)
- Watched video tracking with visual badge/indicator on cards
- Curriculum position persistence within session (and across sessions via localStorage)
- Exercise architecture design (data model + placeholder UI; no content authored yet)
- Exercise gating design (optional: require correct answer before "Next Small Step" is enabled)

### Out of scope
- Changes to `flipper.py` (the full semantic search version)
- Changes to the precompute pipeline or data schema
- Exercise content authoring
- User accounts / server-side persistence
- Accessibility audit (deferred)
- Internationalisation

---

## Non-goals

- Do not add runtime FAISS or LLM calls to `flipper_lite.py`
- Do not break Mode A (expert dropdown) while implementing Mode B
- Do not restructure the existing `shared/`, `search_app/`, or `data/` modules

---

## Success Criteria

1. Expert users can find and play a video in ≤4 dropdown interactions (unchanged from today).
2. Sequential users can start at a small step and advance to the next with a single button click.
3. Videos previously watched are visually distinguished on the card (badge, opacity, or tick).
4. A new session can resume from the last visited small step (via localStorage).
5. The exercise placeholder is present in the UI (even if no content is loaded) without breaking other views.

---

## File Layout

```
ux/
  PROJECT_BRIEF.md          ← this file
  UX_SPEC.md                ← detailed interaction specification
  ARCHITECTURE_NOTES.md     ← Streamlit implementation guidance
  exercises/                ← exercise data (JSON per small step, future)
  assets/                   ← any icons, illustrations specific to UX subproject
```

The agent definition lives at: `.github/agents/ux.agent.md`
