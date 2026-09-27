# -*- coding: utf-8 -*-
"""v2.5.0 — BOW/Lesson Exemplar are GUIDES, the two tabs share one form, and the
LIL tab works with or without a Lesson Exemplar.

What the teacher asked for:
  * stop pre-filling the ILAW boxes from the BOW — pick a BOW as a guide, or
    upload your own BOW, or type everything yourself
  * make the ILAW-LIL tab work the same way: a Lesson Exemplar is the guide, and
    when there is none, the AI searches instead
  * both tabs must look and behave the same

Tested here:
  1. nothing is pre-filled into the shared form
  2. one builder renders BOTH tabs (ILAW and LIL call it)
  3. the picked BOW row is still the silent guide/fallback, and its text is sent
  4. the LIL exemplar is optional; without it the AI searches public DepEd sources
  5. the LIL prompt switches between exemplar rules and research rules
  6. the LIL draft can never be refused and carries a verification label
  7. every provider is still offered on both tabs
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
_tmp = Path(tempfile.mkdtemp(prefix="v250_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("version is 2.5.0", app._APP_VERSION == "2.5.0", app._APP_VERSION)
src = Path(app.__file__).read_text(encoding="utf-8")

# --- 1. nothing is pre-filled any more ---------------------------------------
for needle in ("value=topic_lesson", "value=lib_area", "value=topic_comps", "value=bow_sel_grade",
               "value=week_default", "Pre-filled from the BOW", "value=\"\\n\".join(topic_comps)"):
    check(f"no pre-fill left: {needle[:34]}", needle not in src)
_builder_src = src[src.index("def render_weekly_intentions("):src.index('st.title("📚 DepEd Teacher Tools Generator")')]
check("the shared form pre-fills nothing", "value=" not in _builder_src,
      [line.strip()[:60] for line in _builder_src.splitlines() if "value=" in line][:3])

# --- 2. ONE builder for both tabs --------------------------------------------
check("builder defined once", src.count("def render_weekly_intentions(") == 1)
check("ILAW tab renders it", 'render_weekly_intentions(\n        "ilaw"' in src)
check("LIL tab renders the same one", 'render_weekly_intentions(\n        "lil"' in src)
check("the old per-tab LIL form is gone", 'st.form("lil_form")' not in src and 'st.form("ilaw_form")' not in src)
check("both tabs then use the same returned keys",
      all(f'{prefix}[\"{key}\"]' in src for prefix in ("answers", "lil_answers")
          for key in ("area", "grade", "note", "strategy", "competency", "context", "resources")))
check("both tabs pass the same design patterns and media lists",
      "ILAW_DESIGN_PATTERNS" in src and "ILAW_MEDIA" in src and "ILAW_LEARNER_CONTEXTS" in src)

# --- 3. the BOW pick is a guide, not the source of the form ------------------
check("BOW pick is labelled a guide", "1 · BOW guide (optional" in src)
check("guide panel shows the row's term/week and competencies",
      "📎 BOW guide" in src and "copy what you need into Step 2" in src)
check("uploading your own BOW is still offered", "Upload BOW — PDF, Word, or Excel" in src)
check("no BOW at all falls back to online research",
      "the AI will search well-known public DepEd curriculum content" in src)
check("a picked BOW row is the silent competency fallback",
      'competency_text = "\\n".join(topic_comps)' in src)
check("the picked BOW's text still grounds the draft",
      "summarize_bow(bow_struct, term, week)" in src and "library_bow_text(" in src)

# --- 4./5. the LIL tab: exemplar optional, otherwise AI search --------------
check("LIL exemplar uploader is optional", 'st.file_uploader("Upload Lesson Exemplar (PDF, Word, or Excel)"' in src)
check("LIL submit has no 'exemplar required' gate", "Lesson Exemplar upload (required)" not in src)
check("LIL no-exemplar path researches", 'if lil_details["online_search"]:' in src
      and "find_competency_online(lil_details)" in src)
check("LIL tells the teacher when it will search",
      "the AI will search well-known public DepEd curriculum content" in src)

exemplar_details = {"area": "Science", "grade": "Grade 9", "term": "Term 1", "week": "Week 3",
                    "termweek": "Term 1 · Week 3", "strategy": app.TEACHING_STRATEGIES[4], "sessions": 3,
                    "exemplar": "LESSON EXEMPLAR: Photosynthesis Day 1...", "teacher": "JDC", "note": ""}
exemplar_prompt = app.make_lil_prompt(exemplar_details)
for phrase in ("READ THE ENTIRE LESSON EXEMPLAR THOROUGHLY",
               "PRIMARY SOURCE RULE: Use the Lesson Exemplar as the primary source",
               "preserve the original activity names, sequence, and content",
               "LESSON EXEMPLAR TEXT:", "Preparation, Presentation, Practice, Production, Performance",
               "exactly 3 session object(s)", "Term 1 · Week 3", "WEEKLY OVERARCHING CONTEXT:",
               "ILAW QUALITY RUBRIC", "CRITICAL CONTEXTUALIZATION", "NEVER refuse"):
    check(f"LIL prompt (with exemplar): {phrase[:42]}", phrase in exemplar_prompt)
check("LIL prompt (with exemplar) does not ask for research",
      "NO Lesson Exemplar was uploaded" not in exemplar_prompt)

research_details = dict(exemplar_details, exemplar="", online_search=True)
research_prompt = app.make_lil_prompt(research_details)
for phrase in ("NO Lesson Exemplar was uploaded", "Research well-known public DepEd curriculum content",
               "never invent a competency code", "TEACHER NOTES AND RESEARCH TASK:",
               '"curriculum_verification":', "NEVER refuse"):
    check(f"LIL prompt (research): {phrase[:42]}", phrase in research_prompt)
check("research prompt drops the exemplar-only rules",
      "READ THE ENTIRE LESSON EXEMPLAR THOROUGHLY" not in research_prompt)

# --- 6. the LIL draft is never refused and is always labelled ---------------
check("LIL schema carries the verification fields",
      "curriculum_verification" in app.LIL_SCHEMA and "verification_note" in app.LIL_SCHEMA)
check("generate_lil recovers from a refusal",
      "plan = _ask_plan_completing(make_lil_prompt(details)" in src
      and src.count("_ask_plan_completing(") >= 3, src.count("_ask_plan_completing("))

LIL_GOOD = {"log_title": "T", "overview": "O", "component": "C", "learning_competency": "LC",
            "curriculum_verification": "UNVERIFIED", "verification_note": "check the exemplar",
            "sessions": [{"session": "Session 1", "topic": "a"}]}
LIL_REFUSAL = {"curriculum_verification": "FAILED", "message": "Curriculum alignment could not be verified."}
seen = []


def refuse_once(prompt, options=None, tools=False):
    seen.append(prompt)
    return dict(LIL_GOOD) if "OVERRIDE — the teacher needs the lesson plan now" in prompt else dict(LIL_REFUSAL)


orig_parse = app._ask_and_parse
app._ask_and_parse = refuse_once
try:
    lil = app.generate_lil("k", dict(exemplar_details, sessions=1))
    check("generate_lil still delivers a log after a refusal",
          isinstance(lil, dict) and len(lil.get("sessions") or []) == 1)
    check("generate_lil labels that log", lil.get("curriculum_verification") == "UNVERIFIED")
    check("the refusal triggered the recovery override", "OVERRIDE" in seen[1])
finally:
    app._ask_and_parse = orig_parse

app._ask_and_parse = lambda prompt, options=None, tools=False: dict(LIL_GOOD, curriculum_verification="VERIFIED",
                                                                   verification_note="")
try:
    lil = app.generate_lil("k", dict(exemplar_details, sessions=1))
    check("a VERIFIED MODEL answer stays VERIFIED", lil.get("curriculum_verification") == "VERIFIED")
    check("VERIFIED clears the note", lil.get("verification_note") == "")
finally:
    app._ask_and_parse = orig_parse

app._ask_and_parse = lambda prompt, options=None, tools=False: dict(
    LIL_GOOD, curriculum_verification="VERIFIED", verification_note="")
try:
    lil = app.generate_lil("k", dict(research_details, sessions=1))
    check("an online-search log can never be VERIFIED", lil.get("curriculum_verification") == "UNVERIFIED")
    check("that log explains why", len(str(lil.get("verification_note"))) > 20, str(lil.get("verification_note"))[:48])
finally:
    app._ask_and_parse = orig_parse

check("the LIL output shows the verification banner",
      "Alignment VERIFIED against the uploaded Lesson Exemplar" in src
      and "NOT verified against a Lesson Exemplar" in src)
check("the ILAW output still shows its own banner",
      "Curriculum alignment VERIFIED against the supplied BOW/source" in src)

# --- 7. providers untouched --------------------------------------------------
for provider in ("Google Gemini", "OpenRouter", "Groq", "Mistral"):
    check(f"provider still available: {provider}", provider in app.PROVIDERS)

print()
if fails:
    print(f"FAILURES ({len(fails)}):", fails)
    sys.exit(1)
print("ALL v2.5.0 GUIDE-STYLE TABS TESTS PASSED")
