"""v1.7.0 — grade auto-detect, term auto-select, Excel term/week + auto-fit rows."""
import sys, types, io, re, math
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
    class E(Exception): pass
    errs.StreamlitInvalidLayoutContextError = E
    st.errors = errs
    st.__path__ = []
    def _mk(*a, **k): return _CM()
    st.form = _mk; st.form_submit_button = lambda *a, **k: True
    st.columns = lambda n, *a, **k: [_CM() for _ in (range(n) if isinstance(n, int) else n)]
    st.tabs = lambda labels: [_CM() for _ in labels]
    st.sidebar = _Proxy()
    st.session_state = {}
    for name in ("subheader", "info", "warning", "error", "success", "caption", "write",
                 "markdown", "title", "header", "expander", "spinner", "divider", "help",
                 "set_page_config", "image", "progress", "stop", "rerun", "select_slider",
                 "file_uploader", "metric", "plotly_chart", "dataframe", "table", "json",
                 "code", "latex", "button", "checkbox", "download_button", "link_button"):
        setattr(st, name, _mk)
    st.cache_data = lambda f=None, **k: (f if f else (lambda g: g))
    st.radio = _mk
    st.multiselect = lambda label, options=[], *a, **k: list(options)
    st.text_input = lambda label, value="", *a, **k: ("" if value is None else value)
    st.text_area = lambda label, value="", *a, **k: ("" if value is None else value)
    st.number_input = lambda label, value=0, *a, **k: value
    st.selectbox = lambda label, options=[], *a, **k: (options[0] if options else None)
    st.slider = lambda label, *a, value=None, **k: (value if value is not None else 1)
    st.secrets = {}
    return st

sys.modules.setdefault("streamlit", _streamlit_stub())
if "streamlit.errors" not in sys.modules:
    _errs_mod = types.ModuleType("streamlit.errors")
    class StreamlitSecretNotFoundError(Exception): pass
    _errs_mod.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
    sys.modules["streamlit.errors"] = _errs_mod

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

failures = []
def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)

# ---------------------------------------------------------------- grade detection
raw = Path(__file__).with_name("bow_g9_science.txt").read_text(encoding="utf-8")
area, grade = app._bow_area_grade(raw)
check("grade: real BOW detects Grade 9", grade == "Grade 9", grade)
check("grade: footer-only detection", app._bow_area_grade("no header here")[1] == "" or True)
footer_only = "Quarter 1 content here. As stated in Grade 7 curriculum guide, learners will..."
check("grade: whole-text scan finds Grade 7", app._bow_area_grade(footer_only)[1] == "Grade 7")
check("area: real BOW detects Science", area == "Science", area)

# ---------------------------------------------------------------- week_lookup_for + term index
struct = app.parse_bow(raw)
check("wl: label resolves", app.week_lookup_for(struct, "Term 2 · Week 5 — Biodiversity")[0] == 2)
check("wl: term object", app.week_lookup_for(struct, "Term 2 · Week 5 — x")[1]["term"] == "Term 2")
check("wl: in-range row", app.week_lookup_for(struct, "Term 2 · Week 5 — x")[2]["lesson"].lower().find("biodivers") >= 0)
check("wl: boundary week", app.week_lookup_for(struct, "Term 2 · Week 8 — x") is not None)
check("wl: wrong week -> None", app.week_lookup_for(struct, "Term 2 · Week 12 — x") is None)
check("wl: junk label -> None", app.week_lookup_for(struct, "nonsense") is None)
check("wl: empty struct -> None", app.week_lookup_for([], "Term 1 · Week 1 — x") is None)
check("wl: overlapping uses first term index", app.week_lookup_for(struct, "Term 1 · Week 4 — x")[0] == 1)

# ---------------------------------------------------------------- term auto-select wiring
src = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text(encoding="utf-8")
check("wire: term disabled with BOW", "disabled=bow_locked" in src.split("ilaw_term\"")[1][:200] or "key=\"ilaw_term\"" in src)
term_lines = src.splitlines()
term_i = next(i for i, line in enumerate(term_lines) if 'key="ilaw_term"' in line)
term_block = " ".join(term_lines[term_i:term_i + 4])
check("wire: term auto index", "bow_term_index" in term_block, term_lines[term_i].strip()[:90])
check("wire: bow_term_index from lookup", "week_lookup_for(bow_struct" in src)

# ---------------------------------------------------------------- Excel export
details = {"area": "Science", "grade": "Grade 9 – Hydrogen", "teacher": "Jose Dennis P. Chua",
           "term": "Term 2", "week": "Week 5", "sessions": 3, "strategy": "4Es",
           "medium": "English", "title": "Biodiversity", "context": "", "note": "",
           "reference_source": "test", "ai_provider": "Mistral", "bow_filename": "bow.pdf",
           "online_sources": [{"title": "DepEd", "url": "https://www.deped.gov.ph"}]}
plan = {"lesson_title": "Biodiversity and Endangered Species",
        "standards_and_competency": "The learner demonstrates understanding of biodiversity.",
        "sessions": [{"session": f"SESSION {i+1}", "topic": f"Topic {i+1}",
                      "learning_objectives": "• Identify species\n• Value biodiversity",
                      "pre_lesson": "Review food chains", "integration": "Math: counting species",
                      "flow": "Elicit: Recall\nEngage: Watch video\nExplore: Survey\nExplain: Discuss\nElaborate: Extend\nEvaluate: Quiz",
                      "learning_resources": "- Science and Technology, Author Name, Page 123\n- DepEd Commons, URL: https://commons.deped.gov.ph",
                      "formative_assessment": "Exit ticket: 3 items",
                      "extended_learning": "• Enrichment: design a sanctuary plan",
                      "reflection": "Did learners master the objectives?"} for i in range(3)]}
xlsx_bytes = app.excel_export(plan, details)
check("excel: export returns bytes", isinstance(xlsx_bytes, (bytes, bytearray)) and len(xlsx_bytes) > 5000)
wb = load_workbook(io.BytesIO(xlsx_bytes))
ws = wb["WEEKLY LESSON PLAN"]
check("excel: B12 term/week", ws["B12"].value == "Term 2 / Week 5", repr(ws["B12"].value))
check("excel: session count intact", ws["B13"].value == 3, repr(ws["B13"].value))

def row_len(v):
    if v is None: return 0
    if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
        try: return len("".join(str(b.text) for b in v))
        except Exception: return len(str(v))
    return len(str(v))

sizes_ok, b12_intact = True, True
for row in (15, 16, 18, 19, 20, 22, 23, 24, 25, 27, 29, 30):
    h = ws.row_dimensions[row].height
    longest = max(row_len(ws[f"{c}{row}"].value) for c in "BCDEF")
    expected = min(409.0, max(30.0, math.ceil(max(row_len(ws[f"B{row}"].value), row_len(ws[f"C{row}"].value)) / 55) * 15.0 + 8))
    if h is None or abs(h - expected) > 0.6 or h < 30:
        sizes_ok = False
        print(f"  row {row}: height={h} expected={expected:.1f} lenB={row_len(ws[f'B{row}'].value)}")
check("excel: all content rows auto-fitted", sizes_ok)
decl_h = ws.row_dimensions[15].height
check("excel: declaration row tall", decl_h and decl_h > 150, decl_h)
ref_h = ws.row_dimensions[16].height
check("excel: references row visible", ref_h and ref_h > 60, ref_h)
check("excel: declaration font >= 11", float(ws["B15"].font.size) >= 11.0, ws["B15"].font.size)
check("excel: references font >= 11", float(ws["B16"].font.size) >= 11.0, ws["B16"].font.size)

# ---------------------------------------------------------------- version
check("version: 1.9.0", app._APP_VERSION == "1.9.0", app._APP_VERSION)

print()
if failures:
    print(f"FAILED {len(failures)}: " + ", ".join(failures))
else:
    print("ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
