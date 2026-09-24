"""v1.4.0: ILAW-LIL tab — Lesson Implementation Log from an uploaded Lesson Exemplar."""
import io
import json
import re
import sys
import types
import zipfile
from pathlib import Path


class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Proxy:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return _CM()
    def __getattr__(self, name): return _Proxy()


def _selector(*args, **kwargs):
    opts = args[1] if len(args) > 1 and isinstance(args[1], (list, tuple)) else None
    if opts:
        idx = kwargs.get("index", 0) or 0
        return opts[idx] if isinstance(idx, int) and idx < len(opts) else opts[0]
    return _Proxy()


fake = types.ModuleType("streamlit")


class _SG(dict):
    def __getattr__(self, n): return _Proxy()
    def __setattr__(self, n, v): dict.__setitem__(self, n, v)
    def setdefault(self, k, d=None):
        if k not in self: dict.__setitem__(self, k, d)
        return dict.__getitem__(self, k)
    def pop(self, k, *a): return dict.pop(self, k, *a)


fake.session_state = _SG()
fake.cache_data = lambda f=None, **k: (f if f else (lambda **kk: None))
fake.secrets = {}
fake.__getattr__ = lambda name: _Proxy()
fake.selectbox = _selector
fake.radio = _selector
fake.tabs = lambda *a, **k: [_CM() for _ in (a[0] if a and isinstance(a[0], (list, tuple)) else [])]
fake.columns = lambda *a, **k: [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
fake.text_input = lambda *a, **k: ""
fake.text_area = lambda *a, **k: ""
fake.file_uploader = lambda *a, **k: None
fake.button = lambda *a, **k: False
fake.checkbox = lambda *a, **k: False
fake.download_button = lambda *a, **k: False
fake.form_submit_button = lambda *a, **k: False
fake.number_input = lambda *a, **k: 0
fake.slider = lambda *a, **k: 0
sys.modules["streamlit"] = fake
err = types.ModuleType("streamlit.errors")


class _E(Exception):
    pass


err.StreamlitSecretNotFoundError = _E
sys.modules["streamlit.errors"] = err
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("version 1.9.0", app._APP_VERSION == "2.0.0")

# --- tab order: ILAW | ILAW-LIL | Test Paper | PPT ---------------------------
src = Path(app.__file__).read_text(encoding="utf-8")
tab_line = [l for l in src.splitlines() if "st.tabs([" in l and "ILAW-LIL" in l]
check("tab order ILAW | LIL | Test | PPT",
      bool(tab_line) and tab_line[0].index("ILAW Lesson Plan") < tab_line[0].index("ILAW-LIL")
      < tab_line[0].index("Test Paper Generator") < tab_line[0].index("PowerPoint Generator"),
      tab_line[0].strip()[:110] if tab_line else "missing")

# --- schema covers every template row ----------------------------------------
check("LIL schema: learning_resources present", "learning_resources" in json.dumps(app.LIL_SCHEMA))
for key, _ in app.LIL_SESSION_FIELDS:
    check(f"LIL field wired: {key}", key in app.LIL_SCHEMA["sessions"][0])

# --- prompt: exact phases, exemplar basis, joined termweek --------------------
details = {"area": "Science", "teacher": "Juan Dela Cruz", "termweek": "Term 1 · Week 3",
           "strategy": app.TEACHING_STRATEGIES[4], "sessions": 3,
           "exemplar": "LESSON EXEMPLAR: Photosynthesis Day 1..."}
prompt = app.make_lil_prompt(details)
check("prompt: exact 5Ps phases", "Preparation, Presentation, Practice, Production, Performance" in prompt)
check("prompt: exemplar included", "LESSON EXEMPLAR: Photosynthesis" in prompt)
check("prompt: joined Term/Week", "Term 1 · Week 3" in prompt)
check("prompt: sessions count", "exactly 3 session object(s)" in prompt)
check("prompt: no invented names rule", "never invent" in prompt.lower() or "Never invent" in prompt)

# --- generate_lil: 3 options everywhere, padding, normalization ---------------
sample = {
    "log_title": "Implementation Log: Photosynthesis",
    "overview": "One logged session on photosynthesis.",
    "component": "Curriculum content, pedagogy and assessment",
    "learning_competency": "Explain the process of photosynthesis (S9LT-lg-j-26)",
    "sessions": [{
        "session": "Session 1", "topic": ["t1", "t2", "t3"],
        "learning_objectives": ["- a", "- b", "- c"],
        "learning_resources": ["- Exemplar pages 1-3", "- Science book, Santos, Page 12"],
        "flow": ["Preparation: greet and review. Presentation: short lecture.",
                 "Preparation: variant two. Presentation: lecture two.",
                 "Preparation: variant three. Presentation: lecture three."],
        "learning_experience": ["- Lesson Exemplar pp. 1-3", "- Exemplar v2", "- Exemplar v3"],
        "assessing_learning": ["- Exit ticket", "- Exit ticket v2", "- Exit ticket v3"],
        "ways_forward": ["- Proceed as planned", "- Reteach", "- Remediation"],
        "worked_well": ["w1", "w2", "w3"],
        "remediation": ["r1", "r2", "r3"],
        "enrichment": ["e1", "e2", "e3"],
        "adjustments": ["a1", "a2", "a3"],
    }],
}
app.ask_ai = lambda *a, **k: json.dumps(sample)
app.st.session_state["provider"] = "Mistral"
plan = app.generate_lil("key", dict(details, termweek="Term 1 · Week 3"))
sess = plan["sessions"][0]
check("generate_lil: single text per field", all(isinstance(sess[f], str) for f, _ in app.LIL_SESSION_FIELDS))
check("generate_lil: top fields normalized",
      plan["log_title"].startswith("Implementation Log") and "S9LT" in plan["learning_competency"])
check("generate_lil: ways_forward passthrough", sess["ways_forward"].startswith("- Proceed"))
sparse = {"log_title": "T", "overview": "O", "component": "C", "learning_competency": "LC",
          "sessions": [{"session": "Session 1", "flow": "one blob: a. b. c."}]}
app.ask_ai = lambda *a, **k: json.dumps(sparse)
plan2 = app.generate_lil("key", dict(details, sessions=2, termweek="Term 2 · Week 1"))
check("generate_lil: pads missing sessions to requested count", len(plan2["sessions"]) == 2)
check("generate_lil: ways_forward fallback fills",
      plan2["sessions"][0]["ways_forward"].startswith("- Proceed as planned"))
check("generate_lil: single flow stays one string", isinstance(plan2["sessions"][0]["flow"], str))

# --- export: blank dates, joined termweek, Prepared by ------------------------
data = app.lil_export(plan, {"teacher": "JUAN DELA CRUZ", "area": "Science", "grade": "Grade 9 - Hydrogen",
                             "termweek": "Term 1 · Week 3"})
from openpyxl import load_workbook
wb = load_workbook(io.BytesIO(data))
ws = wb.active
check("export: Teacher -> E10", ws["E10"].value == "JUAN DELA CRUZ")
check("export: Learning Area -> G10", ws["G10"].value == "Science")
check("export: Grade -> B11", ws["B11"].value == "Grade 9 - Hydrogen")
check("export: Term/Week joined -> E11", ws["E11"].value == "Term 1 · Week 3")
check("export: Dates/Time blank -> G11", ws["G11"].value in (None, ""))
check("export: Component -> C14", "Curriculum content" in str(ws["C14"].value))
check("export: Competency -> C15", "photosynthesis" in str(ws["C15"].value).lower())
check("export: objectives -> C18", ws["C18"].value.startswith("- a"))
check("export: resources -> C19", "Exemplar pages" in str(ws["C19"].value))
check("export: assessing -> C22", "Exit ticket" in str(ws["C22"].value))
check("export: ways forward -> C23", "Proceed as planned" in str(ws["C23"].value))
check("export: reflection rows", "w1" in str(ws["C25"].value) and "a1" in str(ws["C28"].value))
check("export: Prepared by -> A31", ws["A31"].value == "JUAN DELA CRUZ")
check("export: logo preserved", any("media/image" in n for n in zipfile.ZipFile(io.BytesIO(data)).namelist()))
check("export: template guide text untouched",
      "WEEKLY IMPLEMENTATION LOG" in str(ws["A20"].value) and "CERTIFICATION" in str(ws["A29"].value))

# legacy picks: (index, field) keys; still honored for old 3-option session state
legacy_plan = app._parse_json_lenient(json.dumps(sample))  # fresh copy, 3-option list shape
data_pick = app.lil_export(legacy_plan, {"teacher": "T", "area": "A", "grade": "G", "termweek": "T · W"},
                           {(0, "flow"): 1})
wb2 = load_workbook(io.BytesIO(data_pick), rich_text=True)
check("export: honored pick flows to C21", "variant two" in str(wb2.active["C21"].value))
check("export: unpicked cells default to option 1", ws["C18"].value == wb2.active["C18"].value)

# --- rich flow in C21: bold labels, Bookman font, Excel-valid XML -------------
rich = wb2.active["C21"].value
from openpyxl.cell.rich_text import CellRichText
check("export: C21 rich text", isinstance(rich, CellRichText))
check("export: bold phase labels in C21", sum(1 for tb in rich if getattr(getattr(tb, "font", None), "b", False)) >= 2)
buf = io.BytesIO()
wb2.save(buf)
with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as z:
    cell_xml = re.search(r'<c r="C21".{0,9000}?</c>', z.read("xl/worksheets/sheet1.xml").decode("utf-8"), re.S).group(0)
check("XML: no empty <rPr/>", "<rPr/>" not in cell_xml)
check("XML: no newline-only run", not re.search(r"<t>\s*</t>", cell_xml))
check("XML: Bookman font inherited", 'val="Bookman Old Style"' in cell_xml)

print("\nALL LIL TESTS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
