# -*- coding: utf-8 -*-
"""v2.4.0 — the ILAW tab rebuilt on the DepEd Tambayan ILAW planner's approach.

The reference planner (depedtambayanph.net's ILAW LP + PPT Generator Pro) collects
the week's own context — competency, content & performance standards, objectives,
learner context, lesson design pattern, materials on hand — and lets the AI unpack
it into the daily sessions. Our tab now asks for the same things (pre-filled from
the BOW library) and prompts the same way, while every AI provider stays available
and the BOW text remains the authority behind the draft.

Tested here:
  1. the reference-style input lists exist
  2. ilaw_session_count() maps the planner's session choices
  3. THE PROMPT mirrors the reference: WEEKLY OVERARCHING CONTEXT block, strict
     output language, critical Filipino contextualization, pure-JSON answer
  4. the teacher's own competency/standards/objectives/resources reach the prompt
  5. 'Default (AI selects)' makes the model choose AND name its framework
  6. named design patterns still pin their exact phases
  7. the tab wires every new box, and nothing is disabled any more
  8. Gemini + OpenRouter + Groq + Mistral are all still offered
"""
import json
import os
import sys
import tempfile
import types
from pathlib import Path


class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Proxy:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return _CM()
    def __getattr__(self, name): return _Proxy()


def _streamlit_stub():
    st = types.ModuleType("streamlit")
    errs = types.ModuleType("streamlit.errors")
    class StreamlitInvalidLayoutContextError(Exception): pass
    errs.StreamlitInvalidLayoutContextError = StreamlitInvalidLayoutContextError
    st.errors = errs
    st.__path__ = []
    def _mk(*a, **k): return _CM()
    st.form = _mk; st.form_submit_button = lambda *a, **k: False
    st.columns = lambda n, *a, **k: [_CM() for _ in (range(n) if isinstance(n, int) else n)]
    st.tabs = lambda labels: [_CM() for _ in labels]
    st.sidebar = _Proxy()
    st.session_state = {}
    st.subheader = _mk; st.info = _mk; st.warning = _mk; st.error = _mk
    st.success = _mk; st.caption = _mk; st.write = _mk; st.markdown = _mk
    st.title = _mk; st.header = _mk; st.download_button = _mk
    st.expander = _mk; st.spinner = _mk; st.divider = _mk; st.help = _mk
    st.set_page_config = _mk; st.image = _mk; st.progress = _mk; st.empty = _mk
    st.cache_data = lambda f=None, **k: (f if f else (lambda g: g))
    st.stop = _mk; st.rerun = _mk; st.select_slider = _mk
    st.radio = _mk; st.multiselect = lambda label, options=[], *a, **k: list(options)
    st.file_uploader = _mk
    st.text_input = lambda label, value="", *a, **k: ("" if value is None else value)
    st.text_area = lambda label, value="", *a, **k: ("" if value is None else value)
    st.number_input = lambda label, value=0, *a, **k: value
    st.selectbox = lambda label, options=[], *a, **k: (options[0] if options else None)
    st.slider = lambda label, *a, value=None, **k: (value if value is not None else 1)
    st.button = _mk; st.checkbox = lambda *a, **k: False
    st.metric = _mk; st.plotly_chart = _mk; st.dataframe = _mk; st.table = _mk
    st.secrets = {}
    st.link_button = _mk
    return st


sys.modules.setdefault("streamlit", _streamlit_stub())
if "streamlit.errors" not in sys.modules:
    _errs_mod = types.ModuleType("streamlit.errors")
    class StreamlitSecretNotFoundError(Exception): pass
    _errs_mod.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
    sys.modules["streamlit.errors"] = _errs_mod

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = Path(tempfile.mkdtemp(prefix="v240_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("version is 2.4.0", app._APP_VERSION == "2.4.0", app._APP_VERSION)

# --- 1. the reference-style input lists --------------------------------------
check("design patterns: 'Default (AI selects)' is offered first",
      app.ILAW_DESIGN_PATTERNS[0].lower().startswith("default"), app.ILAW_DESIGN_PATTERNS[0])
check("design patterns: the specific models are still there",
      len(app.ILAW_DESIGN_PATTERNS) == len(app.TEACHING_STRATEGIES) + 1)
check("learner contexts cover the reference presets",
      len(app.ILAW_LEARNER_CONTEXTS) >= 8 and app.ILAW_LEARNER_CONTEXTS[-1].lower().startswith("other"))
check("resource options cover the reference checkboxes",
      {"Laptop / Computer", "Projector / Smart TV", "Slide presentation", "Visual aids",
       "Manipulatives / models", "Printed worksheets", "Chalkboard / whiteboard",
       "Art / craft materials", "Audio / speakers", "Realia (real objects)"} <= set(app.ILAW_RESOURCE_OPTIONS))
check("media choices cover English + Filipino",
      app.ILAW_MEDIA[:2] == ["English", "Filipino"], app.ILAW_MEDIA[:2])

# --- 2. session-count choices -------------------------------------------------
check("auto choice lets the AI decide", app.ilaw_session_count(app.ILAW_SESSION_CHOICES[0]) == 0)
check("auto also for blank/None", app.ilaw_session_count("") == 0 and app.ilaw_session_count(None) == 0)
check("'5 Sessions (1 Week)' -> 5", app.ilaw_session_count("5 Sessions (1 Week)") == 5)
check("'3 Sessions (1 Week)' -> 3", app.ilaw_session_count("3 Sessions (1 Week)") == 3)
check("'1 Session' -> 1", app.ilaw_session_count("1 Session") == 1)
check("clamped to the template's 5 slots", app.ilaw_session_count("9 Sessions") == 5)
check("plan_session_count honours the fixed choice",
      app.plan_session_count({"sessions": app.ilaw_session_count("4 Sessions (1 Week)")}, {"session_count": 1}) == 4)
check("plan_session_count lets the AI decide on auto",
      app.plan_session_count({"sessions": app.ilaw_session_count("Auto — the AI decides from the topic and its competencies")},
                             {"session_count": 3}) == 3)

# --- 3. the prompt mirrors the reference -------------------------------------
BASE = {"area": "Advanced Mathematics", "grade": "Grade 11", "term": "Term 1", "week": "",
        "strategy": "5Es Model — Engage, Explore, Explain, Elaborate, Evaluate", "title": "Trigonometric Identities",
        "sessions": 4, "duration": "60 minutes", "medium": "English", "teacher": "JDC",
        "context": "Mixed readiness levels", "note": "", "bow": "BOW TEXT", "bow_match": "BOW MATCH"}
prompt = app.make_prompt(BASE)
check("prompt has the WEEKLY OVERARCHING CONTEXT block", "WEEKLY OVERARCHING CONTEXT:" in prompt)
for line in ("- Lesson Name:", "- Grade & Section:", "- Learning Area:", "- Learning Competency:",
             "- Content Standards:", "- Performance Standards:", "- General Learning Objectives:",
             "- General Learner Context:", "- Lesson Design Pattern:", "- Available Learning Resources:",
             "- Medium of Instruction:", "- Term / Week:", "- Duration per Session:",
             "- Additional Instructions / Prompts:"):
    check(f"context block line {line[:28]}", line in prompt)
check("prompt demands the strict output language",
      "Write EVERY row of the output STRICTLY in English." in prompt)
check("prompt carries the Filipino contextualization block",
      "CRITICAL CONTEXTUALIZATION" in prompt and "culturally responsive" in prompt
      and "Filipino learners" in prompt)
check("prompt asks for a pure JSON object", "Provide no text or explanation other than the pure JSON object" in prompt)
check("prompt tells the model to unpack the week", "Unpack the week's competency into the daily sessions" in prompt)
check("prompt keeps the BOW material attached", "BOW TEXT" in prompt and "BOW MATCH" in prompt)
check("prompt keeps the honest week wording",
      "not week-based (the source lists topics/units, not weeks)" in prompt)

# --- 4. the teacher's own inputs reach the prompt ----------------------------
own = dict(BASE, competency="18. apply sum and difference formulas to simplify expressions.",
           content_standards="The learner demonstrates understanding of trigonometric identities.",
           performance_standards="The learner applies identities to solve problems.",
           objectives="Knowledge: state the formulas. Skills: apply them.",
           resources="Chalkboard / whiteboard, Printed worksheets, metre tape",
           medium="Filipino")
own_prompt = app.make_prompt(own)
for needle in ("apply sum and difference formulas", "demonstrates understanding of trigonometric identities",
               "applies identities to solve problems", "Knowledge: state the formulas",
               "Chalkboard / whiteboard, Printed worksheets, metre tape",
               "Write EVERY row of the output STRICTLY in Filipino."):
    check(f"prompt carries teacher input: {needle[:40]}", needle in own_prompt)
blank = app.make_prompt(dict(BASE, competency="", content_standards="", performance_standards=""))
check("blank competency lines are marked, never faked",
      "- Learning Competency: [not provided" in blank
      and "- Content Standards: [not provided" in blank
      and "- Performance Standards: [not provided" in blank)

# --- 5. 'Default (AI selects)' + 6. named patterns ---------------------------
default_prompt = app.make_prompt(dict(BASE, strategy=app.ILAW_DESIGN_PATTERN_DEFAULT))
check("default pattern: the model must choose and name the framework",
      "Framework: <name>" in default_prompt and "the teacher left the framework to you" in default_prompt)
check("default pattern: a named framework is NOT forced",
      "Required design pattern:" not in default_prompt)
named_prompt = app.make_prompt(dict(BASE, strategy=app.TEACHING_STRATEGIES[2]))
check("named pattern: phases are pinned exactly",
      "Engage, Explore, Explain, Elaborate, Evaluate" in named_prompt
      and "Required design pattern:" in named_prompt)
check("empty strategy falls back to 'Default'",
      "the teacher left the framework to you" in app.make_prompt(dict(BASE, strategy="")))

# --- 7. the tab wires the new boxes ------------------------------------------
src = Path(app.__file__).read_text(encoding="utf-8")
for needle in ('st.form("ilaw_form")', '"2 · Weekly Lesson Details & Intentions"', "ilaw_comp__", "ilaw_cs__",
               "ilaw_ps__", "ilaw_objectives", "ilaw_ctx_pick", "ilaw_res__", "ilaw_res_other",
               "ilaw_sessions", "ilaw_week__", "ilaw_medium", "ilaw_strategy", "value=topic_lesson",
               "value=lib_area", "ilaw_session_count(sessions_pick)",
               'st.form_submit_button("Generate ILAW Lesson Plan (AI)"'):
    check(f"tab wiring: {needle[:44]}", needle in src)
check("no ILAW field is disabled by picking a BOW topic any more", "disabled=bool(topic_hit)" not in src)
check("the topic's competencies pre-fill the competency box", '"\\n".join(topic_comps)' in src)
check("learner context preset + notes are combined", 'str(context_pick)' in src and "learner_context" in src)
check("checked resources are joined for the prompt", '" ".join(picked_resources' not in src and "picked_resources" in src)

# --- 8. every provider still offered ----------------------------------------
for provider in ("Google Gemini", "OpenRouter", "Groq", "Mistral"):
    check(f"provider still available: {provider}", provider in app.PROVIDERS,
          ", ".join(app.PROVIDERS))
check("provider keys still labelled per provider",
      all(app.PROVIDERS[p].get("key_label") for p in ("Google Gemini", "OpenRouter", "Groq", "Mistral")))
check("SCHEMA still single-string per ILAW row",
      isinstance(app.SCHEMA["sessions"][0]["flow"], str) and "session_count" in app.SCHEMA)

print()
if fails:
    print(f"FAILURES ({len(fails)}):", fails)
    sys.exit(1)
print("ALL v2.4.0 REFERENCE-STYLE ILAW TESTS PASSED")
