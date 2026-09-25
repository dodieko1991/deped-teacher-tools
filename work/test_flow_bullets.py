"""v1.2.2: Flow renders as bullet-per-phase for ALL strategy models (7Es included)."""
import sys, types
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


check("version 1.9.0", app._APP_VERSION == "2.2.0")

# The EXACT text pattern from the user's screenshot: pre-lineated, mid-line phase starts, no Elicit label
seven_es = """Elicit: The teacher asks students to write two numbers whose product is 12 and sum is 7, prompting recall of
factoring basics. Learners discuss possible pairs in pairs for two minutes. Engage: A short game called
"Factor Bingo" is introduced where students match quadratic terms to their factored forms on a board.
Explore: In small groups, students manipulate algebra tiles to represent x² + 7x + 12 and physically combine
them into (x+3)(x+4). Explain: The teacher models the step-by-step factoring process on the board,
highlighting the use of the product-zero property. Elaborate: Groups solve three progressively harder
quadratics, explaining each step aloud while the teacher circulates. Evaluate: Students complete a
rapid-fire worksheet where they factor and solve five quadratics, turning it in for immediate feedback.
Extend: The class brainstorms how factoring could be used to find dimensions of a rectangular garden given
its area and perimeter."""
out = app.format_flow_text(seven_es)
lines = [l for l in out.split("\n") if l.strip()]
firsts = [l.split(":")[0].strip() for l in lines if ":" in l]
check("7Es: all 7 phases separate lines", len(lines) == 7, f"{len(lines)} lines")
check("7Es: Elicit included", firsts[:7] == ["Elicit", "Engage", "Explore", "Explain", "Elaborate", "Evaluate", "Extend"], str(firsts[:7]))

one_blob = "Elicit: recall drill. Engage: factor bingo. Explore: algebra tiles. Explain: modeling. Elaborate: harder sets. Evaluate: worksheet. Extend: garden problem."
out2 = app.format_flow_text(one_blob)
check("7Es: one blob also splits", len([l for l in out2.split("\n") if l.strip()]) == 7)

four_es = "Activity: do the experiment. Analysis: discuss results. Abstraction: summarize. Application: real-life task."
firsts4 = [l.split(":")[0] for l in app.format_flow_text(four_es).split("\n")]
check("4Es still works", firsts4 == ["Activity", "Analysis", "Abstraction", "Application"], str(firsts4))

five_es = "Engage: warm-up game. Explore: stations. Explain: discussion. Elaborate: project. Evaluate: quiz."
check("5Es works", len(app.format_flow_text(five_es).split("\n")) == 5)

weird = "**Elicit:** recall. *Engage:* game\n- Explore: tiles. Explain: board work."
firsts_w = [l.split(":")[0] for l in app.format_flow_text(weird).split("\n")]
check("mixed markdown + pre-lineated", firsts_w == ["Elicit", "Engage", "Explore", "Explain"], str(firsts_w))

lower = "elicit: one. ENGAGE: two. Explore: three."
firsts_l = [l.split(":")[0] for l in app.format_flow_text(lower).split("\n")]
check("case-insensitive + Title-case output", firsts_l == ["Elicit", "Engage", "Explore"], str(firsts_l))

html_out = app.flow_html(seven_es)
check("flow_html: bullets + bold labels", html_out.count("&bull;") == 7 and html_out.count("<b>") == 7)
check("flow_html: escapes content", "&lt;" in app.flow_html("Elicit: a < b test"))

# 5Ps Model (the user's screenshot): mid-paragraph phase labels split into bullets
five_ps = ("Preparation: Guro ay magpapakita ng mga larawan ng iba't ibang gulay at cooking oil, hinihikayat "
           "ang mga mag-aaral na magbahagi ng karanasan. Presentation: Guro ay magbibigay ng maikling lektyura "
           "tungkol sa nutrisyon ng gulay at katangian ng cooking oil, gamit ang visual aids. Practice: Sa maliliit "
           "na grupo, magbibigay ang guro ng mga sariwang gulay at oil. Production: Bawat grupo ay magsasagawa ng "
           "simpleng paghiwa at paghalo ng gulay. Performance: Ipinapakita ng bawat grupo ang kanilang inihanda.")
firsts5 = [l.split(":")[0] for l in app.format_flow_text(five_ps).split("\n")]
check("5Ps: all five phases split", firsts5 == ["Preparation", "Presentation", "Practice", "Production", "Performance"], str(firsts5))

iwe = "I Do: model the factoring on the board. We Do: solve two items together. You Do: students work alone."
firsts_iwe = [l.split(":")[0] for l in app.format_flow_text(iwe).split("\n")]
check("I Do-We Do-You Do splits", firsts_iwe == ["I Do", "We Do", "You Do"], str(firsts_iwe))

inquiry = "Question: pose the problem. Hypothesis: predict. Investigation: test it. Evidence: gather data. Conclusion: summarize."
check("Inquiry phases split", len(app.format_flow_text(inquiry).split("\n")) == 5)

lead_in = "Guide Question: How do forces act? Activity: groups test friction. Analysis: class compares results."
firsts_lead = [l.split(":")[0] for l in app.format_flow_text(lead_in).split("\n")]
check("lead-in text kept as own bullet", firsts_lead == ["Guide Question", "Activity", "Analysis"], str(firsts_lead))

phases = app._strategy_phases(app.TEACHING_STRATEGIES[4])
check("_strategy_phases 5Ps", phases == ["Preparation", "Presentation", "Practice", "Production", "Performance"], str(phases))
phases_iwe = app._strategy_phases(app.TEACHING_STRATEGIES[5])
check("_strategy_phases arrow-style", phases_iwe == ["teacher modeling", "guided practice", "independent practice"], str(phases_iwe))
prompt_5ps = app.make_prompt({"strategy": app.TEACHING_STRATEGIES[4], "sessions": 1, "duration": "1 hour", "medium": "English", "area": "Science", "grade": "G9", "term": "T1", "week": "1", "title": "", "teacher": "", "context": "", "bow": "BOW"})
check("prompt lists exact 5Ps phases", "Preparation, Presentation, Practice, Production, Performance" in prompt_5ps)

check("Excel bold rich text intact", callable(app.bold_flow_rich))
rich = app.bold_flow_rich(seven_es)
check("Excel rich: 7 bold labels", sum(1 for tb in rich if getattr(getattr(tb, "font", None), "b", False)) == 7)

# Excel-validity: the saved XML must have no empty <rPr/>, no newline-only run, and
# preserved spacing — those are what triggered Excel's 'Repaired Records' dialog.
import io as _io
import re as _re
import zipfile as _zipfile
from openpyxl import load_workbook as _lw
wb = _lw(app.TEMPLATE)
wb.active["B23"] = rich
buf = _io.BytesIO()
wb.save(buf)
with _zipfile.ZipFile(_io.BytesIO(buf.getvalue())) as z:
    cell_xml = _re.search(r'<c r="B23".{0,8000}?</c>', z.read("xl/worksheets/sheet1.xml").decode("utf-8"), _re.S).group(0)
check("Excel XML: no empty <rPr/>", "<rPr/>" not in cell_xml)
check("Excel XML: no newline-only run", not _re.search(r"<t>\s*</t>", cell_xml))
check("Excel XML: runs carry <rFont", cell_xml.count("<rFont") >= 14, str(cell_xml.count("<rFont")))
check("Excel XML: bold on labels", cell_xml.count('<b val="1"/>') == 7)
wb2 = _lw(_io.BytesIO(buf.getvalue()), rich_text=True)
from openpyxl.cell.rich_text import CellRichText as _CRT
v = wb2.active["B23"].value
check("Excel round-trip: still rich", isinstance(v, _CRT))
check("Excel round-trip: 7 bold survive", sum(1 for tb in v if getattr(getattr(tb, "font", None), "b", False)) == 7)
check("Excel round-trip: text intact", "Elicit" in str(v) and "perimeter." in str(v))

print("\nALL FLOW-BULLET TESTS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
