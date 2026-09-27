"""v1.8.0 — exemplar-first LIL: auto-detect area/grade/term/week from the uploaded Lesson Exemplar."""
import sys, types, io, json
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

failures = []
def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)

# ------------------------------------------------- detection on the REAL exemplar
le_txt = Path(__file__).with_name("le_gm_q1.txt").read_text(encoding="utf-8")
check("le-text: extracted", len(le_txt) > 50000, f"{len(le_txt)} chars")
meta = app.detect_exemplar_meta(le_txt)
check("le: area detected", meta["area"].lower().replace("&", "and") == "general mathematics", meta["area"])
check("le: grade detected", meta["grade"] == "Grade 11", meta["grade"])
check("le: term detected (Semester FIRST)", meta["term"] == "Term 1", meta["term"])

# role-name trap: "Learning Area Specialist" must never become the area
trap = app.detect_exemplar_meta("Learning Area: Learning Area Specialist Grade Level: 9")
check("le: role-name filtered", trap["area"] != "Learning Area Specialist", trap["area"])
check("le: role trap falls back to next candidate or empty", "specialist" not in trap["area"].lower())

# header variant: 'Lesson Exemplar in ...' fallback
fb = app.detect_exemplar_meta("Lesson Exemplar in Statistics and Probability Quarter 3 contents here")
check("le: fallback title detection", bool(fb["area"]), fb["area"])

# case normalization: ALL-CAPS area title-cased
caps = app.detect_exemplar_meta("Learning Area: SCIENCE Grade Level: 8 Semester: Second")
check("le: caps title-cased", caps["area"] == "Science", caps["area"])
check("le: second semester -> Term 2", caps["term"] == "Term 2", caps["term"])

# quarter word mapping
q3 = app.detect_exemplar_meta("Learning Area: English Grade Level: 7 Quarter: Third")
check("le: quarter Third -> Term 3", q3["term"] == "Term 3", q3["term"])

# week detection
wk = app.detect_exemplar_meta("Learning Area: Science Grade Level: 9 Quarter: First Week 3: The lesson content")
check("le: week detected", wk["week"] == "Week 3", wk["week"])
empty = app.detect_exemplar_meta("just some random text without any header")
check("le: no header -> all empty", empty == {"area": "", "grade": "", "term": "", "week": ""}, empty)

# ------------------------------------------------- LIL tab wiring (exemplar-first)
src = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text(encoding="utf-8")
lil_start = src.index("with lil_tab:")
lil_src = src[lil_start: src.index("with test_tab:")]
# v2.6.0: the LIL tab mirrors the ILAW tab — the exemplar is an OPTIONAL guide,
# nothing is pre-filled or locked, and both tabs share one form builder.
check("order: exemplar uploader before the shared form",
      lil_src.find("lil_file") != -1 and lil_src.find("render_weekly_intentions") > lil_src.find("lil_file"))
check("order: detection (guide only) before the form",
      lil_src.find("detect_exemplar_meta") < lil_src.find("render_weekly_intentions"))
check("both tabs share the same form builder",
      'render_weekly_intentions(\n        "ilaw"' in src and 'render_weekly_intentions(\n        "lil"' in lil_src)
check("lock: only the Term box can lock, and only from the exemplar",
      "term_locked=bool(lil_meta" in lil_src and "disabled=lil_locked" not in lil_src)
check("exemplar is optional: no 'required' upload gate",
      "Lesson Exemplar upload (required)" not in lil_src and 'key="lil_file"' in lil_src)
check("detected meta is offered as a guide only", "Guide only" in lil_src)
check("no-exemplar path searches for the competency",
      "find_competency_online" in lil_src and "online_search" in lil_src)
check("reuse: cached exemplar text reused at submit",
      "lil_exemplar_raw" in lil_src.split("if lil_answers[")[1][:2500])

# ------------------------------------------------- version
check("version: 2.4.0", app._APP_VERSION == "2.6.0", app._APP_VERSION)

print()
if failures:
    print(f"FAILED {len(failures)}: " + ", ".join(failures))
else:
    print("ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
