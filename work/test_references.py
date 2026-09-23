"""v1.3.0: per-session references (Book/Site) + DO 3 s.2026 Annex A declaration."""
import sys, types, io
from pathlib import Path


class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Proxy:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return _CM()
    def __getattr__(self, name): return _Proxy()


fake = types.ModuleType("streamlit")


class _SG(dict):
    def __getattr__(self, n): return _Proxy()
    def __setattr__(self, n, v): dict.__setitem__(self, n, v)
    def setdefault(self, k, d=None):
        if k not in self: dict.__setitem__(self, k, d)
        return dict.__getitem__(self, k)
    def pop(self, k, *a): return dict.pop(self, k, *a)


fake.session_state = _SG()
fake.secrets = {}
fake.cache_data = lambda f=None, **k: (f if f else (lambda **kk: None))
fake.__getattr__ = lambda name: _Proxy()
for w in ("selectbox", "radio"):
    setattr(fake, w, lambda *a, **k: (a[1][0] if len(a) > 1 and isinstance(a[1], (list, tuple)) else _Proxy()))
fake.tabs = lambda *a, **k: [_CM() for _ in (a[0] if a and isinstance(a[0], (list, tuple)) else [])]
fake.columns = lambda *a, **k: [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
for w in ("text_input", "text_area"):
    setattr(fake, w, lambda *a, **k: "")
for w in ("button", "checkbox", "download_button", "form_submit_button"):
    setattr(fake, w, lambda *a, **k: False)
fake.file_uploader = lambda *a, **k: None
sys.modules["streamlit"] = fake
err = types.ModuleType("streamlit.errors")


class _E(Exception):
    pass


err.StreamlitSecretNotFoundError = _E
sys.modules["streamlit.errors"] = err
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("v1.6.0", app._APP_VERSION == "1.6.0")
check("book ref regex", bool(app._BOOK_REF_RE.match("Physics Essentials, J. Domingo, p. 45")))
m = app._SITE_REF_RE.match("Khan Academy, URL: https://www.khanacademy.org/science")
check("site ref regex", bool(m and m.group("url") == "https://www.khanacademy.org/science"))
rich = app.bold_references_rich("- Science for Grade 9, Santos & Reyes, Page 112\n- Khan Academy, URL: https://khan.org")
check("refs rich: 2 bold names", sum(1 for tb in rich if getattr(getattr(tb, "font", None), "b", False)) == 2)

d = {"area": "Science", "teacher": "Jose Dennis Plaza Chua", "ai_provider": "Groq", "grade": "G9", "term": "T1", "week": "1", "sessions": 1, "context": "", "bow": "B", "bow_filename": ""}
plan = {"lesson_title": "T", "overview": "O", "standards_and_competency": "S",
        "sessions": [{"session": "Session 1", "topic": ["t"], "learning_objectives": ["- o"], "pre_lesson": ["p"],
                      "flow": ["Activity: x. Analysis: y."], "learning_resources": ["- manipulatives\n- Science for Grade 9, Santos & Reyes, Page 112"],
                      "integration": ["N/A"], "formative_assessment": ["f"], "extended_learning": ["e"], "reflection": ["r"]}]}
data = app.excel_export(plan, d)
wb2 = load_workbook(io.BytesIO(data))
decl = str(wb2.active["B15"].value)
check("decl: teacher", "Jose Dennis Plaza Chua" in decl)
check("decl: ai name", "Groq" in decl)
check("decl: area", "Science Lesson Plan" in decl)
check("decl: DO 3 s.2026 wording", decl.startswith("Consistent with the policy guidelines on the use of AI") and "See DO 3 s.2026 Annex A." in decl and "no confidential learner information" in decl)
check("B16: session ref extracted", "Science for Grade 9" in str(wb2.active["B16"].value))
check("B24: bullet resources", "Science for Grade 9" in str(wb2.active["B24"].value))

sessions = [{"session": f"Session {i}", "topic": [f"t{i}"], "learning_objectives": ["- o"], "pre_lesson": ["p"],
             "flow": ["Activity: x."], "learning_resources": [f"- Ref {i}\n- Book {i}, Author {i}, Page {i}0"],
             "integration": ["N/A"], "formative_assessment": ["f"], "extended_learning": ["e"], "reflection": ["r"]} for i in range(1, 6)]
d5 = dict(d); d5["sessions"] = 5
plan5 = dict(plan); plan5["sessions"] = sessions
wb5 = load_workbook(io.BytesIO(app.excel_export(plan5, d5)))
refs5 = str(wb5.active["B16"].value)
check("5 sessions -> 5 references", sum(refs5.count(f"Book {i}") for i in range(1, 6)) == 5)

print("\nALL REFERENCES TESTS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
