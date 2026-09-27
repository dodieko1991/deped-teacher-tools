# -*- coding: utf-8 -*-
"""v2.3.0 — the ILAW tab NEVER refuses: it verifies, then always delivers.

The reference ILAW generators teachers use freely (depedtambayanph.net and the
like) never block a teacher behind a curriculum gate — they take the teacher's
own competency input and always return a draft. Our BOW grounding must be an
extra, never a dead end, so the strict rule now ends in a LABEL (VERIFIED /
UNVERIFIED + verification note) instead of a refusal JSON. Tested here:

  1. the rule text asks for a complete plan and forbids a refusal answer
  2. _verification_status() normalizes the model's label + supplies a note
  3. _ask_plan_completing() recovers from a refusal answer once, then delivers
  4. generate() returns the plan even when the model refuses first
  5. generate() still raises after a SECOND refusal (a real dead end)
  6. make_prompt() carries the quality rubric learned from the reference tool
  7. excel_export() prints the real session count and never a dangling 'Term 1 / '
  8. excel_export() records the verification status in References
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
    st.button = _mk; st.checkbox = _mk
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

# Point the library at an empty folder so the import never scans 289 PDFs; the
# bundled seed still answers load_bow_library().
_tmp = Path(tempfile.mkdtemp(prefix="v230_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("version is 2.3.0", app._APP_VERSION == "2.5.0", app._APP_VERSION)

# --- 1. the rule asks for a complete plan and forbids refusing ----------------
rule = app.STRICT_CURRICULUM_VERIFICATION
for phrase in ("STRICT CURRICULUM VERIFICATION RULE",
               "VERIFY FIRST — THEN ALWAYS DELIVER",
               "Grade Level + Learning Area + Term + Week",
               "NEVER refuse, NEVER reply with only a refusal object",
               "\"curriculum_verification\": \"UNVERIFIED\"",
               "\"verification_note\"",
               "Never fabricate URLs, references, textbook",
               "page numbers, or source titles",
               "Teacher-provided resource - verification required"):
    check(f"rule text: {phrase[:46]}", phrase in rule)
check("rule no longer tells the model to answer with a refusal JSON",
      "\"curriculum_verification\": \"FAILED\"" not in rule)
check("recovery override exists and demands the full plan",
      "Do NOT reply with a refusal" in app.VERIFICATION_RECOVERY
      and "FULL ILAW plan" in app.VERIFICATION_RECOVERY)
check("SCHEMA carries the verification fields",
      "curriculum_verification" in app.SCHEMA and "verification_note" in app.SCHEMA)

# --- 2. _verification_status normalizes the label ----------------------------
plan = app._verification_status({"curriculum_verification": "VERIFIED", "verification_note": "ignore me"})
check("VERIFIED stays VERIFIED with no note", plan["curriculum_verification"] == "VERIFIED" and plan["verification_note"] == "")
plan = app._verification_status({"curriculum_verification": "PASSED"})
check("legacy PASSED counts as VERIFIED", plan["curriculum_verification"] == "VERIFIED")
plan = app._verification_status({"curriculum_verification": "FAILED", "verification_note": "upload the BOW"})
check("FAILED becomes UNVERIFIED and keeps the note",
      plan["curriculum_verification"] == "UNVERIFIED" and plan["verification_note"] == "upload the BOW")
plan = app._verification_status({})
check("missing label becomes UNVERIFIED with a default note",
      plan["curriculum_verification"] == "UNVERIFIED" and len(plan["verification_note"]) > 20,
      plan["verification_note"][:48])

# --- 3. _ask_plan_completing recovers from ONE refusal -----------------------
GOOD = {"lesson_title": "T", "overview": "O", "standards_and_competency": "S",
        "curriculum_verification": "UNVERIFIED", "verification_note": "check the BOW",
        "session_count": 2,
        "sessions": [{"session": "Session 1", "topic": "a"}, {"session": "Session 2", "topic": "b"}]}
REFUSAL = {"curriculum_verification": "FAILED", "message": "Curriculum alignment could not be verified."}
seen = []


# _ask_and_parse returns PARSED objects, so this stand-in returns dicts too.
def refuse_once(prompt, options=None, tools=False):
    seen.append(prompt)
    return dict(GOOD) if "OVERRIDE — the teacher needs the lesson plan now" in prompt else dict(REFUSAL)


orig_ask_parse = app._ask_and_parse
app._ask_and_parse = refuse_once
try:
    got = app._ask_plan_completing("base prompt", {})
    check("a refusal answer still ends in a delivered plan",
          isinstance(got, dict) and len(got.get("sessions") or []) == 2, str(got)[:60])
    check("the refusal triggered exactly one recovery turn", len(seen) == 2 and "OVERRIDE" in seen[1])
finally:
    app._ask_and_parse = orig_ask_parse


# --- 4./5. generate() delivers, and only a SECOND refusal is a dead end ------
DETAILS = {"bow": "BOW TEXT", "sessions": 2, "area": "Advanced Mathematics", "grade": "Grade 11",
           "term": "Term 1", "week": "", "strategy": app.TEACHING_STRATEGIES[2],
           "duration": "60 minutes", "medium": "English", "title": "Trigonometric Identities",
           "teacher": "", "context": "", "note": ""}

app._ask_and_parse = refuse_once
try:
    produced = app.generate("k", dict(DETAILS))
    check("generate() delivers the plan instead of raising",
          len(produced.get("sessions") or []) == 2, str(produced.get("curriculum_verification")))
    check("generate() labels the delivered plan",
          produced.get("curriculum_verification") == "UNVERIFIED"
          and produced.get("verification_note") == "check the BOW")
except Exception as exc:  # noqa: BLE001
    check("generate() delivers the plan instead of raising", False, f"{type(exc).__name__}: {exc}")
finally:
    app._ask_and_parse = orig_ask_parse

app._ask_and_parse = lambda prompt, options=None, tools=False: dict(REFUSAL)
try:
    app.generate("k", dict(DETAILS))
    check("generate() raises only after the recovery also refuses", False, "no exception")
except ValueError as exc:
    check("generate() raises only after the recovery also refuses",
          "could not be verified" in str(exc), str(exc)[:52])
finally:
    app._ask_and_parse = orig_ask_parse

# --- 6. the quality rubric learned from the reference generator --------------
prompt = app.make_prompt(dict(DETAILS, bow="", bow_match=""))
for phrase in ("ILAW QUALITY RUBRIC",
               "another teacher can teach the session straight from it",
               "inclusive and contextualized for Filipino learners",
               "Assessment runs through the session"):
    check(f"prompt rubric: {phrase[:40]}", phrase in prompt)
check("objective domain labels are demanded", "'Knowledge:', 'Skills:', or" in prompt)
check("weekless prompt states the week honestly",
      "not week-based (the source lists topics/units, not weeks)" in prompt)
review = app.make_review_prompt(DETAILS, {"sessions": [{"session": "Session 1"}, {"session": "Session 2"}]})
check("review prompt carries the rubric too", "ILAW QUALITY RUBRIC" in review)
check("review prompt protects a VERIFIED label from being faked",
      "only upgrade the label to VERIFIED" in review)
check("prompt always names a term (never a blank 'Term: ')",
      "Term: None" not in prompt and "Term: ;" not in prompt, prompt.split("Learning area: ")[1][:60])

# --- 7./8. the Excel export ---------------------------------------------------
EXPORT_DETAILS = dict(DETAILS, teacher="JOSE DENNIS P. CHUA", ai_provider="Google Gemini",
                      reference_source="Budget of Work (BOW) PDF in the app's built-in library.",
                      bow_filename="Grade 11\\Advanced Mathematics", sessions=0,
                      context="Mixed readiness levels.")
EXPORT_PLAN = dict(GOOD, sessions=[dict(s, learning_objectives="- Knowledge: x", pre_lesson="p",
                                        flow="Engage: e", learning_resources="- Book, Author, Page: not stated",
                                        integration="N/A", formative_assessment="f", extended_learning="x",
                                        reflection="r") for s in GOOD["sessions"]])
try:
    from openpyxl import load_workbook
    from io import BytesIO
    book = load_workbook(BytesIO(app.excel_export(EXPORT_PLAN, EXPORT_DETAILS)))
    sheet = book["WEEKLY LESSON PLAN"]
    check("export prints the plan's real session count", sheet["B13"].value == 2, sheet["B13"].value)
    check("weekless export has no dangling ' / ' in Term/Week",
          "/" not in str(sheet["B12"].value) and "no weeks to show" in str(sheet["B12"].value),
          sheet["B12"].value)
    check("export records the UNVERIFIED status in References",
          "NOT verified against a BOW/source" in str(sheet["B16"].value))
    check("export names the built-in library instead of 'Uploaded BOW file'",
          "Built-in BOW library: Grade 11 · Advanced Mathematics" in str(sheet["B16"].value))
    verified = dict(EXPORT_PLAN, curriculum_verification="VERIFIED", verification_note="")
    book2 = load_workbook(BytesIO(app.excel_export(verified, EXPORT_DETAILS)))
    check("export records a VERIFIED status in References",
          "Curriculum alignment: VERIFIED" in str(book2["WEEKLY LESSON PLAN"]["B16"].value))
except Exception as exc:  # noqa: BLE001
    check("Excel export runs", False, f"{type(exc).__name__}: {exc}")

# --- 9. the Term box for unit-based SHS BOWs ---------------------------------
# Before v2.3.0 a BOW with no terms left the Term box disabled AND blank, so the
# plan and the Excel carried no term at all. The Term box now locks only when
# the source states the topic's term, and the teacher's choice outranks a
# default.
src = Path(app.__file__).read_text(encoding="utf-8")
for needle in ('term_locked = bool(topic_hit and str(topic_hit[1].get("term") or "").strip())',
               'term = (topic_hit[1].get("term") if topic_hit else "") or answers["term"]',
               'disabled=term_locked,',
               'if topic_options and not any(str(t.get("term", "")).strip()'):
    check(f"term handling: {needle[:44]}", needle in src)
check("the dead 'if topic_options and term_locked:' branch is gone",
      "if topic_options and term_locked:" not in src)

print()
if fails:
    print(f"FAILURES ({len(fails)}):", fails)
    sys.exit(1)
print("ALL v2.3.0 NEVER-REFUSE TESTS PASSED")
