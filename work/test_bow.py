"""v1.6.0 — BOW-first flow: parser (real [G9] Science.pdf), locked fields, prompt wiring."""
import sys, types, json, io, re
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
import app  # noqa: E402

failures = []
def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)

# ------------------------------------------------- parser on the REAL G9 Science BOW
bow_txt = Path(__file__).with_name("bow_g9_science.txt").read_text(encoding="utf-8")
check("pdf-text: extracted", len(bow_txt) > 20000, f"{len(bow_txt)} chars")
struct = app.parse_bow(bow_txt)
check("pdf: 3 terms parsed", isinstance(struct, list) and len(struct) == 3, f"got {len(struct) if isinstance(struct, list) else type(struct)}")
t1, t2, t3 = (struct + [None, None, None])[:3]
if not t1:
    print("FATAL: parser returned nothing for the real BOW")
    sys.exit(1)
check("pdf: term labels", t1["term"] == "Term 1" and t2["term"] == "Term 2" and t3["term"] == "Term 3",
      f"{[t['term'] for t in struct]}")
check("pdf: T1 content standards", len(t1["content_standards"]) >= 1, str(len(t1["content_standards"])))
check("pdf: T1 std mentions Newton", any("newton" in s.lower() for s in t1["content_standards"]))
check("pdf: T2 std about DNA/traits", any(("dna" in s.lower() or "trait" in s.lower()) for s in t2["content_standards"]))
check("pdf: T3 std about investigations/bonding", bool(t3["content_standards"]))
check("pdf: T1 week rows", len(t1["weeks"]) >= 4, f"{len(t1['weeks'])} rows")
check("pdf: first T1 row is weeks 1 to 3", t1["weeks"][0]["from"] == 1 and t1["weeks"][0]["to"] == 3)
check("pdf: Newton row title", "newton" in t1["weeks"][0]["lesson"].lower())
check("pdf: competencies on the row", len(t1["weeks"][0]["competencies"]) >= 2, str(len(t1["weeks"][0]["competencies"])))
check("pdf: T2 has 3 rows", len(t2["weeks"]) == 3, str(len(t2["weeks"])))
check("pdf: T3 has rows", len(t3["weeks"]) >= 4, str(len(t3["weeks"])))
check("pdf: suggested activities captured", len(t1["suggested_activities"]) >= 10, str(len(t1["suggested_activities"])))
check("pdf: T2+T3 activities", len(t2["suggested_activities"]) >= 5 and len(t3["suggested_activities"]) >= 5)
check("pdf: activity text meaningful", len(min(t1["suggested_activities"], key=len)) > 25)

# row→activity coincidence: the first row's activity list references its lesson domain
all_acts = " | ".join(t1["suggested_activities"]).lower()
check("pdf: T1 activities reference term content", ("force" in all_acts or "inertia" in all_acts or "circuit" in all_acts))

# ------------------------------------------------- parser unit behavior (synthetic)
SYN = ("FIRST TERM\nContent Standards: Living things and their environment.\n"
       "Performance Standard: Perform experiments.\n"
       "1 to 3 Respiratory and Circulatory Systems Working Together\n"
       "● describes how the respiratory and circulatory systems transport nutrients and gases\n"
       "● explain the mechanism of gas exchange\n"
       "Suggested Activities\n● Heart Rate Lab - Learners measure pulse before and after exercise")
syn = app.parse_bow(SYN)
check("syn: 1 term", len(syn) == 1)
check("syn: week row 1-3", syn[0]["weeks"][0]["from"] == 1 and syn[0]["weeks"][0]["to"] == 3)
check("syn: lesson title", "Respiratory" in syn[0]["weeks"][0]["lesson"])
check("syn: competencies separated", len(syn[0]["weeks"][0]["competencies"]) == 2)
check("syn: performance standard", "experiment" in syn[0]["performance_standard"].lower())
check("syn: activity captured", "Heart Rate Lab" in " ".join(syn[0]["suggested_activities"]))
check("syn: junk input -> []", app.parse_bow("hello there nothing to see") == [])
check("syn: empty -> []", app.parse_bow("") == [])
check("syn: area+grade detected", app._bow_area_grade("Grade 9 | Science Budget of Work")[0] == "Science"
      and app._bow_area_grade("Grade 9 | Science Budget of Work")[1] == "Grade 9")

# ------------------------------------------------- match_bow_row resolution
m = app.match_bow_row(struct, "Term 1", "Week 4")
check("match: T1 W4 hits second row (3-5)", "Electric Current" in m, m[:80])
m1 = app.match_bow_row(struct, "Term 1", "Week 2")
check("match: T1 W2 hits first row (1-3)", "Newton" in m1, m1[:80])
m2 = app.match_bow_row(struct, "Term 1", "Week 8")
check("match: T1 W8 hits a T1 row", "Term 1" in m2 and "BOW MATCH" in m2)
m3 = app.match_bow_row(struct, "Term 2", "Week 5")
check("match: T2 W5 hits biodiversity row", "Biodiversity" in m3)
check("match: week beyond BOW -> ''", app.match_bow_row(struct, "Term 1", "Week 19") == "")
check("match: no struct -> ''", app.match_bow_row([], "Term 1", "Week 1") == "")

# ------------------------------------------------- summarize_bow block
s = app.summarize_bow(struct, "Term 1", "Week 1")
check("summary: contains term headers", "TERM 1" in s and "TERM 2" in s and "TERM 3" in s)
row_comps = struct[0]["weeks"][0]["competencies"]
check("summary: contains rows + comps", "Weeks 1 to 3" in s and row_comps[0][:40] in s)

# ------------------------------------------------- tab order + BOW-first layout
src = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text(encoding="utf-8")
check("order: BOW uploader before form", src.find("ilaw_bow") != -1 and src.find("ilaw_bow") < src.find('st.form("ilaw_form")'))
check("order: BOW summary rendered before form", src.find("ilaw_bow_render") < src.find('st.form("ilaw_form")'))
tab_decl = src.split("st.tabs(")[1][:200]
check("order: ILAW first, LIL second", tab_decl.find("ILAW Lesson Plan") < tab_decl.find("ILAW-LIL"), tab_decl[:100])

# ------------------------------------------------- lock behavior
check("lock: bow_locked defined", "bow_locked = bool(" in src)
check("lock: >=2 disabled fields", src.count("disabled=bow_locked") >= 2, str(src.count("disabled=bow_locked")))
check("lock: BOW lesson feeds title", "ilaw_lesson_locked" in src)
check("lock: title prefilled from BOW row", "bow_title" in src)

# ------------------------------------------------- prompt wiring
p = app.make_prompt({"grade": "9", "area": "Science", "term": "Term 1", "week": "Week 1",
                     "strategy": "4Es", "title": "Newton", "sessions": 3, "duration": "60",
                     "medium": "English", "teacher": "T", "note": "", "context": "", "bow": "", "bow_match": None})
check("prompt: builds without BOW", bool(p) and "ILAW" in p)
t = t1; row = t1["weeks"][0]
p2 = app.make_prompt({"grade": "9", "area": "Science", "term": "Term 1", "week": "Week 1",
                      "strategy": "4Es", "title": row["lesson"][:40], "sessions": 3, "duration": "60",
                      "medium": "English", "teacher": "T", "note": "", "context": "",
                      "bow": app.summarize_bow(struct, "Term 1", "Week 1"),
                      "bow_match": app.match_bow_row(struct, "Term 1", "Week 1")})
check("prompt: BOW summary injected", "PARSED BOW SUMMARY" in p2)
check("prompt: BOW match injected", "BOW MATCH" in p2 and "Newton" in p2)
check("prompt: competencies injected", "inertia" in p2.lower())
check("prompt: LIL keeps source-priority", "CURRICULUM SOURCE PRIORITY" in app.make_lil_prompt(
    {"grade": "9", "area": "Science", "termweek": "Term 1 · Week 1", "strategy": "4Es", "sessions": 3,
     "teacher": "T", "note": "", "exemplar": "EXEMPLAR BODY"}))

# ------------------------------------------------- version
check("version: 1.8.0", app._APP_VERSION == "1.8.0", app._APP_VERSION)

print()
if failures:
    print(f"FAILED {len(failures)}: " + ", ".join(failures))
else:
    print("ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
