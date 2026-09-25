# -*- coding: utf-8 -*-
"""v2.0.0 — BOW library loader, library-first ILAW tab, AI-determined session count."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Build the synthetic library BEFORE importing app — BOW_LIBRARY_DIR is read at import time.
def write_pdf(path, text):
    """Create a one-page PDF containing `text` using pypdf's low-level writer."""
    from pypdf import PdfWriter
    from pypdf.generic import (DictionaryObject, NameObject, ArrayObject, TextStringObject, NumberObject)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # Build a very simple content stream that draws text lines.
    lines = text.split("\n")
    ops = ["BT"]
    y = 750
    for line in lines:
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"/F1 10 Tf 1 0 0 1 40 {y} Tm ({safe}) Tj")
        y -= 14
    ops.append("ET")
    stream = " ".join(ops).encode("latin-1", "replace")
    page = writer.pages[0]
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    page[NameObject("/Resources")] = resources
    from pypdf.generic import DecodedStreamObject
    content = DecodedStreamObject()
    content.set_data(stream)
    page[NameObject("/Contents")] = content
    with open(path, "wb") as fh:
        writer.write(fh)


tmp = Path(tempfile.mkdtemp(prefix="bowlib_"))
g9 = tmp / "Grade 9"; g11 = tmp / "Grade 11"; k = tmp / "Kindergarten"
for d in (g9, g11, k):
    d.mkdir(parents=True)
write_pdf(g9 / "[G9] Science.pdf", "SCIENCE\nGrade 9\nFirst Term\nContent Standard\n1 to 3 Newton's Laws, Force, and Energy\nbullet one competency here")
write_pdf(g11 / "Basic Calculus.pdf", "BASIC CALCULUS\nPrerequisite: Pre-Calculus\nCONTENT DOMAIN LEARNING COMPETENCIES\n1. Limits and Continuity 1. illustrate the limit of a function 2. apply limit laws\n2. Derivatives and Tangents 6. define and illustrate the tangent line 7. explain the derivative")
write_pdf(k / "Kindergarten BOW.pdf", "KINDERGARTEN Three-Term Budget Of Work\nFirst Term\nTheme Knowing Who We Are\nSubtheme Learning Competencies\n1. We are unique.\n2. We have feelings.")

# Both paths MUST be redirected before import: importing app runs the whole module
# (UI included), which calls load_bow_library() at import time.
os.environ["DEPED_BOW_LIBRARY"] = str(tmp)
os.environ["DEPED_BOW_CACHE"] = str(tmp / "bow_library_cache.json")
import app  # noqa: E402

failures = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)

# --- tests ---
lib = app.load_bow_library()
check("1. library loads", bool(lib), f"grades={sorted(lib)}")
check("2. grade folders mapped", "Grade 9" in lib and "Grade 11" in lib and "Kindergarten" in lib, sorted(lib))
check("3. subject names cleaned (no [G9] tag)", "[G9] Science" not in lib.get("Grade 9", {}), sorted(lib.get("Grade 9", {})))
check("4. G9 Science parsed with week rows", any(r["lesson"] for t in lib["Grade 9"]["Science"]["terms"] for r in t["weeks"]), "")
g9_terms = lib["Grade 9"]["Science"]["terms"]
check("5. G9 area/grade detected", lib["Grade 9"]["Science"]["grade"] == "Grade 9", lib["Grade 9"]["Science"]["grade"])
g11_terms = lib["Grade 11"]["Basic Calculus"]["terms"]
check("6. G11 file has terms (no-week topics)", len(g11_terms) == 1, f"{len(g11_terms)}")
check("7. G11 has NO week rows (weeks without numbers)", not g11_terms[0]["weeks"][0].get("from"), "")
check("8. G11 topic extracted (Derivatives)", any("Derivatives" in r["lesson"] for r in g11_terms[0]["weeks"]), [r["lesson"] for r in g11_terms[0]["weeks"]][:5])
check("9. G11 synthesized term label empty (no term)", g11_terms[0]["term"] == "", repr(g11_terms[0]["term"]))
k_terms = lib["Kindergarten"]["Kindergarten BOW"]["terms"]
check("10. Kinder subtheme topics", any("We are unique" in r["lesson"] for r in k_terms[0]["weeks"]), [r["lesson"] for r in k_terms[0]["weeks"]])

# no-term week rows (G11/12 week-based BOWs): synthesized single term
no_term = app.parse_bow("Budget of Work Grade 12 Tech-Pro\nWeek Learning Competency\n1 to 2 Animation fundamentals\nbullet comp one here\n3 to 5 Digital drawing techniques")
check("11. week rows without term -> one term", len(no_term) == 1 and no_term[0]["term"] == "Term 1", len(no_term))
check("12. no-term week rows preserved", no_term[0]["weeks"][0]["weeks"] == "1 to 2", no_term[0]["weeks"])

# summarize + match_bow_row tolerate from=0
summary = app.summarize_bow(g11_terms, "Term 1", "Week 1")
check("13. summarize tolerates no-week rows", "Derivatives" in summary, "")
mm = app.match_bow_row(g11_terms, "Term 1", "Week 1")
check("14. match_bow_row safe on no-week BOW", True, "")

# plan_session_count: AI decides when sessions=0, clamps, keeps explicit choice
d = {"sessions": 0}
check("15. AI-decided default (no declared count)", app.plan_session_count(d, {}) == 2, app.plan_session_count(d, {}))
check("16. AI-decided uses declared session_count", app.plan_session_count(d, {"session_count": 4}) == 4, "")
check("17. clamped to 5", app.plan_session_count(d, {"session_count": 9}) == 5, "")
check("18. explicit sessions still respected", app.plan_session_count({"sessions": 3}, {"session_count": 1}) == 3, "")

# schema + prompt wiring
check("19. SCHEMA has session_count", "session_count" in json.dumps(app.SCHEMA), "")
prompt = app.make_prompt({"area": "Science", "grade": "Grade 9", "term": "Term 1", "week": "Week 1",
                          "strategy": "4Es", "title": "T", "teacher": "", "context": "", "sessions": 0,
                          "duration": "60 minutes", "medium": "English", "bow": "B", "bow_filename": "", "bow_match": ""})
check("20. prompt tells AI to decide session count", "decide yourself how many sessions" in prompt, "")
check("21. prompt has no hard session count for library flow", "exactly 0 learner-centered sessions" not in prompt, "")
details = {"sessions": 0, "bow": "B", "area": "Science", "grade": "9", "term": "Term 1", "week": "Week 1",
           "title": "T", "strategy": "4Es", "duration": "60", "medium": "English", "teacher": "", "context": ""}
captured = {}
def fake_ask(prompt_text, options=None, tools=False):
    captured["prompt"] = prompt_text
    return {"lesson_title": "T", "overview": "O", "standards_and_competency": "S", "session_count": 3,
            "sessions": [{"session": f"Session {i+1}", "topic": f"T{i+1}"} for i in range(4)]}
old_ask = app._ask_and_parse
app._ask_and_parse = fake_ask
try:
    plan = app.generate("k", details)
finally:
    app._ask_and_parse = old_ask
check("22. generate: AI count (declared 3) enforced to 3 sessions", len(plan["sessions"]) == 3, len(plan["sessions"]))

captured.clear()
def fake_ask_over(prompt_text, options=None, tools=False):
    captured["prompt"] = prompt_text
    return {"lesson_title": "T", "overview": "O", "standards_and_competency": "S", "session_count": 9,
            "sessions": [{"session": f"Session {i+1}", "topic": "T"} for i in range(9)]}
app._ask_and_parse = fake_ask_over
try:
    plan = app.generate("k", dict(details))
finally:
    app._ask_and_parse = old_ask
check("23. generate: over-count clamped to 5 (template slots)", len(plan["sessions"]) == 5, len(plan["sessions"]))

# library helpers
text = app.library_bow_text("Grade 11", "Basic Calculus")
check("24. library_bow_text returns PDF text", "BASIC CALCULUS" in text, text[:60])
check("25. missing subject -> empty text", app.library_bow_text("Grade 11", "Nope") == "", "")

# version
check("26. version is 2.0.0", app._APP_VERSION == "2.1.0", app._APP_VERSION)

print(f"\n{'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
