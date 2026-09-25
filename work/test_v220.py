# -*- coding: utf-8 -*-
"""v2.2.0 — no-week BOW topics carry their competencies to the AI.

Root cause of the "Curriculum alignment could not be verified" error on topics
like Grade 11 Trigonometric Identities: the SHS BOW has NO week rows, so topic
rows carried no competencies, the prompt's Week said "Week 1" (a week that does
not exist in that course), and match_bow_row found nothing. The model then hit
the strict-verification rule and refused.

Fixes tested here:
  1. extract_shs_topics attaches the numbered competencies that follow each unit
  2. summarize_bow marks competencies as 'Unit N learning competency:' when the row has no weeks
  3. match_bow_row matches by lesson title when the BOW has no week numbers
  4. the whole ILAW details path builds a BOW-grounded, week-honest prompt
"""
import io
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
    st.form = _mk; st.form_submit_button = lambda *a, **k: True
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

# Redirect the library BEFORE import (importing app runs the whole module).
tmp = Path(tempfile.mkdtemp(prefix="bowweek_"))
g11 = tmp / "Grade 11"
g11.mkdir(parents=True)

# Minimal SHS-shaped BOW: numbered units before numbered competencies, no weeks.
shs_text = ("ADVANCED MATHEMATICS\nGrade 11\nPrerequisite: Pre-Calculus\n"
            "CONTENT DOMAIN LEARNING COMPETENCIES\n"
            "1. Trigonometric Identities 1. illustrate the trigonometric identities 2. prove "
            "trigonometric identities using fundamental identities 3. solve situational problems "
            "involving trigonometric identities\n"
            "2. Derivatives and Tangents 6. define and illustrate the tangent line 7. explain the "
            "derivative of a function\n")
import app  # noqa: E402
from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject  # noqa: E402


def write_pdf(path, text):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    ops = ["BT"]
    y = 750
    for line in text.split("\n"):
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"/F1 10 Tf 1 0 0 1 40 {y} Tm ({safe}) Tj")
        y -= 14
    ops.append("ET")
    page = writer.pages[0]
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    content = DecodedStreamObject()
    content.set_data(" ".join(ops).encode("latin-1", "replace"))
    page[NameObject("/Contents")] = content
    with open(path, "wb") as fh:
        writer.write(fh)


write_pdf(g11 / "Advanced Mathematics.pdf", shs_text)
os.environ["DEPED_BOW_CACHE"] = str(tmp / "bow_library_cache.json")
app.BOW_LIBRARY_DIR = tmp
app.BOW_LIBRARY_CACHE = tmp / "bow_library_cache.json"
app.st.session_state.clear()

failures = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)


# --- 1. the extractor attaches competencies ---
raw = shs_text
rows = app.extract_shs_topics(raw)
trig = next((r for r in rows if "Trigonometric Identities" in r["lesson"]), None)
check("1a. trig unit found", trig is not None, [r["lesson"] for r in rows][:6])
check("1b. unit row carries competencies", bool(trig and trig["competencies"]),
      f"{len(trig['competencies']) if trig else 0} comps")
check("1c. competencies are the real ones",
      trig and any("illustrate the trigonometric identities" in c for c in trig["competencies"]),
      (trig or {}).get("competencies", [])[:2])
deriv = next((r for r in rows if "Derivatives" in r["lesson"]), None)
check("1d. second unit gets its OWN competencies",
      deriv and deriv["competencies"] and not deriv["competencies"] == trig["competencies"],
      f"{len(deriv['competencies']) if deriv else 0} comps")

# --- 2. summarize_bow marks no-week competencies honestly ---
terms = [{"term": "", "content_standards": [], "performance_standard": "", "weeks": rows, "suggested_activities": []}]
summary = app.summarize_bow(terms, "", "")
check("2a. unit competencies appear in the summary", "illustrate the trigonometric identities" in summary, "")
check("2b. 'Unit learning competency' label used", "Unit learning competency" in summary, summary[:400])
check("2c. no phantom 'Week rows' header for weekless rows",
      "Week rows" not in summary, "")

# --- 3. match_bow_row title-fallback ---
hint = app.match_bow_row(terms, "", "")
check("3a. generic units hint when no title set", "UNITS with no week numbers" in hint, hint[:120])
terms[0]["_selected_topic"] = "Trigonometric Identities"
hint = app.match_bow_row(terms, "", "")
check("3a2. title-matched hint names the unit", "the 'Trigonometric Identities' unit" in hint, hint[:160])
terms[0].pop("_selected_topic", None)
check("3b. hint tells the AI the course has no weeks", "no week numbers" in hint, hint[:200])
weeked = [{"term": "Term 1", "content_standards": [], "performance_standard": "", "weeks":
           [{"weeks": "1 to 3", "from": 1, "to": 3, "lesson": "Newton's Laws", "competencies": ["c1"]}], "suggested_activities": []}]
check("3c. weeked BOWs still match by week", "Weeks 1 to 3" in app.match_bow_row(weeked, "Term 1", "Week 2"), "")

# --- 4. the full details path (as the ILAW submit block builds it) ---
lib = app.load_bow_library()
entry = lib["Grade 11"]["Advanced Mathematics"]
struct = entry["terms"]
topic_hit_row = next(r for t in struct for r in t["weeks"] if "Trigonometric Identities" in r["lesson"])
week = f"Week {topic_hit_row['from']}" if topic_hit_row.get("from") else ""
bow_auto_term = next((str(t.get("term", "")).strip() for t in struct if str(t.get("term", "")).strip()), "")
term = bow_auto_term
if not term:
    week_num_match = app.re.search(r"\d{1,2}", str(week or ""))
    term = app.term_for_week(week_num_match.group(0)) if week_num_match else "Term 1"
check("4a. no phantom week label", week == "", week)
check("4b. term falls back to Term 1 (weekless course)", term == "Term 1", term)
bow_struct_text = app.summarize_bow(struct, term, week) + "\n\nRAW BOW TEXT:\n" + app.library_bow_text("Grade 11", "Advanced Mathematics")
details = {"area": "Mathematics", "grade": "Grade 11", "term": term, "week": week,
           "strategy": "7Es Model — Elicit, Engage, Explore, Explain, Elaborate, Evaluate, Extend",
           "title": "Trigonometric Identities", "sessions": 0, "duration": "60 minutes", "medium": "English",
           "teacher": "", "context": "", "note": "", "bow": bow_struct_text,
           "bow_filename": "Grade 11\\Advanced Mathematics",
           "bow_match": app.match_bow_row(struct, term, week)}
prompt = app.make_prompt(details)
check("4c. prompt carries the unit competencies", "illustrate the trigonometric identities" in prompt, "")
check("4d. prompt does NOT claim Week 1", "Week: Week 1" not in prompt, "")
check("4e. prompt has the BOW MATCH hint", "BOW MATCH" in prompt, "")
check("4f. raw BOW text included", "RAW BOW TEXT:" in prompt and len(details["bow"]) > 900, len(details["bow"]))

# --- 5. version ---
check("5. version is 2.2.0", app._APP_VERSION == "2.2.0", app._APP_VERSION)

print(f"\n{len(failures)} failures" if failures else "\nALL PASS")
sys.exit(1 if failures else 0)
