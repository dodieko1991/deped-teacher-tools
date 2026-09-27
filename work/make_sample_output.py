# -*- coding: utf-8 -*-
"""Make a REAL app output for Grade 11 · Advanced Mathematics · Trigonometric Identities.

Runs the same pipeline the ILAW tab runs — built-in BOW library (Grade → Subject
→ Topic) → details dict → make_prompt() → excel_export() — with the sample plan in
work/sample_plan_g11_trig.py standing in for the AI answer, so the exact output
format can be produced and compared offline (no provider key needed).

Outputs (work/sample_outputs/):
  * ILAW_SAMPLE_G11_AdvancedMathematics_TrigonometricIdentities.xlsx — the app's Excel export
  * ILAW_SAMPLE_preview.html — the same plan as an ILAW matrix, for on-screen comparison
  * prompt_g11_trig.txt — the exact prompt the AI receives (BOW grounding proof)
"""
import html
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work" / "sample_outputs"


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
    _errs = types.ModuleType("streamlit.errors")
    class StreamlitSecretNotFoundError(Exception): pass
    _errs.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
    sys.modules["streamlit.errors"] = _errs
sys.path.insert(0, str(ROOT))

# The real library + a COPY of the real cache: this script never rewrites the
# app's own bow_library_cache.json.
os.environ["DEPED_BOW_LIBRARY"] = str(ROOT / "BOW Library")
_tmp_cache = Path(tempfile.mkdtemp(prefix="sample_bow_")) / "cache.json"
shutil.copyfile(ROOT / "bow_library_cache.json", _tmp_cache)
os.environ["DEPED_BOW_CACHE"] = str(_tmp_cache)

import app  # noqa: E402
from sample_plan_g11_trig import PLAN  # noqa: E402  (work/ is on sys.path via this file's folder)

GRADE = "Grade 11"
SUBJECT = "Advanced Mathematics"
WANTED = "trigonometric identities"
LEARNER_CONTEXT = (
    "Mixed readiness levels in a 40-learner Grade 11 class: about a third solve special-angle values from memory, "
    "a third still need the unit-circle chart, and a small group struggles with negative signs and fraction "
    "arithmetic. Learners respond well to group tasks and mini-whiteboards, and most are motivated by "
    "calculator-free challenges and local contexts such as the barangay road and the school antenna."
)

lib = app.load_bow_library()
assert GRADE in lib and SUBJECT in lib[GRADE], f"library has no {GRADE} / {SUBJECT}"

# --- exactly what the ILAW tab does with the dropdowns -----------------------
topic_options, topic_lookup, term_locked, bow_auto_term = [], {}, False, ""
for t_index, term_dict in enumerate(lib[GRADE][SUBJECT]["terms"], start=1):
    if str(term_dict.get("term", "")).strip():
        term_locked = False
        bow_auto_term = bow_auto_term or term_dict["term"]
    for row in term_dict["weeks"]:
        label = app.topic_label(term_dict.get("term"), row)
        topic_options.append(label)
        topic_lookup[label] = (t_index, term_dict, row)
bow_sel_topic = next(lbl for lbl in topic_options if WANTED in lbl.lower())
topic_hit = topic_lookup[bow_sel_topic]
bow_struct = lib[GRADE][SUBJECT]["terms"]
bow_text = app.library_bow_text(GRADE, SUBJECT)
bow_title = topic_hit[2]["lesson"]
week = f"Week {topic_hit[2]['from']}" if topic_hit and topic_hit[2].get("from") else ""
# Same precedence the submit block uses: the source's own term, else the
# teacher's choice (the Term box defaults to Term 1 for unit-based SHS BOWs),
# else the BOW's first stated term.
term = (topic_hit[1].get("term") if topic_hit else "") or "Term 1" or bow_auto_term
for row in bow_struct:
    row["_selected_topic"] = bow_title

details = {
    "area": lib[GRADE][SUBJECT].get("area") or SUBJECT, "grade": GRADE, "term": term, "week": week,
    "strategy": "5Es Model — Engage, Explore, Explain, Elaborate, Evaluate",
    "title": bow_title, "sessions": 0, "duration": "60 minutes", "medium": "English",
    "teacher": "JOSE DENNIS P. CHUA", "context": LEARNER_CONTEXT, "note": "",
    # The reference-style boxes the reconstructed tab now pre-fills from the BOW.
    "competency": "\n".join(topic_hit[2].get("competencies") or []),
    "content_standards": "The learner demonstrates understanding of the key concepts of trigonometric identities.",
    "performance_standards": ("The learner is able to apply trigonometric identities accurately to simplify "
                              "expressions, prove identities, and solve problems."),
    "objectives": ("Knowledge: state the sum, difference, double-angle and half-angle formulas. "
                   "Skills: apply them to simplify expressions and prove identities. "
                   "Attitude: work accurately and check a partner's reasoning."),
    "resources": "Chalkboard / whiteboard, Printed worksheets, Visual aids, Calculators",
    "bow": app.summarize_bow(bow_struct, term, week) + "\n\nRAW BOW TEXT:\n" + bow_text,
    "bow_filename": f"{GRADE}\\{SUBJECT}",
    "bow_match": app.match_bow_row(bow_struct, term, week),
    "ai_provider": "Google Gemini",
    "reference_source": "Budget of Work (BOW) PDF in the app's built-in library.",
}

prompt = app.make_prompt(details)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "prompt_g11_trig.txt").write_text(prompt, encoding="utf-8")

# --- proof that the app no longer grounds the plan in a phantom week ---------
checks = [
    ("topic label found", bool(bow_sel_topic)),
    ("weekless topic sends NO week", week == ""),
    ("prompt has no phantom 'Week: Week 1'", "Week: Week 1" not in prompt),
    ("prompt states the week honestly",
     "not week-based (the source lists topics/units, not weeks)" in prompt),
    ("prompt carries the unit competencies", all(f"{n}." in prompt for n in (18, 19, 20, 21))),
    ("prompt carries the BOW MATCH hint", "BOW MATCH" in prompt.upper()),
    ("prompt carries the quality rubric", "ILAW QUALITY RUBRIC" in prompt),
    ("prompt tells the model never to refuse", "NEVER refuse" in prompt),
    ("raw BOW text attached", "RAW BOW TEXT" in prompt),
]
for name, ok in checks:
    print(("PASS" if ok else "FAIL"), "-", name)
print()
print("TOPIC LABEL :", bow_sel_topic)
print("TERM/WEEK   :", repr(term), "/", repr(week))
print("BOW MATCH   :", str(details["bow_match"])[:300].replace("\n", " | "))
print("PROMPT SIZE :", f"{len(prompt):,} chars")
print()

# --- the app's own Excel export, with the sample plan ------------------------
xlsx = app.excel_export(PLAN, details)
xlsx_path = OUT / "ILAW_SAMPLE_G11_AdvancedMathematics_TrigonometricIdentities.xlsx"
xlsx_path.write_bytes(xlsx)
print("WROTE", xlsx_path.relative_to(ROOT), f"({len(xlsx):,} bytes)")

# --- the same plan as an ILAW matrix, for side-by-side comparison ------------
E = html.escape


def cell(value):
    return E(str(value or "")).replace("\n", "<br>")


def row_html(label, key):
    cells = "".join(f"<td>{cell(item.get(key))}</td>" for item in PLAN["sessions"])
    return f'<tr><td class="row-label">{label}</td>{cells}</tr>'


session_heads = "".join(f"<th>Session {i}</th>" for i in range(1, len(PLAN["sessions"]) + 1))
span = len(PLAN["sessions"]) + 1
html_doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>ILAW Sample — Grade 11 Advanced Mathematics · Trigonometric Identities</title>
<style>
 body {{ font-family: Arial, Helvetica, sans-serif; font-size: 12px; margin: 18px; color: #111; }}
 h1 {{ font-size: 18px; margin: 0 0 4px; }}
 .meta {{ color: #444; margin-bottom: 12px; }}
 table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin-bottom: 16px; }}
 th, td {{ border: 1px solid #4b5563; padding: 6px; vertical-align: top; }}
 th {{ background: #e5e7eb; text-align: center; }}
 .row-label {{ background: #f3f4f6; font-weight: bold; width: 15%; }}
 .section-header {{ background: #d1d5db; font-weight: bold; font-size: 13px; }}
 .hdr-label {{ background: #f3f4f6; font-weight: bold; width: 22%; }}
 .notice {{ border: 1px solid #b45309; background: #fef3c7; padding: 8px; margin-bottom: 12px; }}
 .ok {{ border: 1px solid #15803d; background: #dcfce7; padding: 8px; margin-bottom: 12px; }}
</style></head><body>
<h1>ILAW Lesson Plan — SAMPLE OUTPUT</h1>
<div class="meta">Produced by the DepEd Teacher Tools Generator (app v{app._APP_VERSION}) for
<b>Grade 11 · Advanced Mathematics · Trigonometric Identities</b> — an offline sample built on the
real SHS Budget of Work competencies 18–21, for comparison with the reference generator.</div>
<div class="{'ok' if PLAN['curriculum_verification'] == 'VERIFIED' else 'notice'}">
<b>Curriculum alignment: {E(PLAN['curriculum_verification'])}.</b> {cell(PLAN['verification_note'])}
</div>
<table>
 <tr><td class="hdr-label">Lesson Title</td><td>{cell(PLAN['lesson_title'])}</td></tr>
 <tr><td class="hdr-label">Learning Area/s</td><td>{cell(details['area'])}</td></tr>
 <tr><td class="hdr-label">Name of Teacher/s</td><td>{cell(details['teacher'])}</td></tr>
 <tr><td class="hdr-label">Grade Level and Section</td><td>{cell(details['grade'])}</td></tr>
 <tr><td class="hdr-label">Term / Week</td><td>{E(term) if week else E(term) + ' — the SHS BOW lists units, not weeks; placement to be verified'}</td></tr>
 <tr><td class="hdr-label">No. of Sessions</td><td>{len(PLAN['sessions'])} Sessions ({cell(details['duration'])} each)</td></tr>
 <tr><td class="hdr-label">References</td><td>{cell(PLAN['sessions'][1]['learning_resources'])}</td></tr>
 <tr><td class="hdr-label">Declaration of AI use</td><td><i>Co-created with AI assistance to unpack the
 Budget of Work competencies into a four-session learning design; reviewed and validated by the teacher.
 See DO 3 s.2026 Annex A.</i></td></tr>
</table>
<table>
 <tr><td colspan="{span}" class="section-header">Intentions.</td></tr>
 <tr><td class="row-label">Learning Competency and Curriculum Standards:</td>
     <td colspan="{len(PLAN['sessions'])}">{cell(PLAN['standards_and_competency'])}</td></tr>
 <tr><td class="row-label"></td>{session_heads}</tr>
 {row_html('Learning Objectives:', 'learning_objectives')}
 <tr><td class="row-label">Learner Context:</td><td colspan="{len(PLAN['sessions'])}">{cell(LEARNER_CONTEXT)}</td></tr>
 <tr><td colspan="{span}" class="section-header">Learning Experience.</td></tr>
 {row_html('Pre-Lesson:', 'pre_lesson')}
 {row_html('Flow:', 'flow')}
 {row_html('Learning Resources:', 'learning_resources')}
 {row_html('Opportunities for integration:', 'integration')}
 <tr><td colspan="{span}" class="section-header">Assessment.</td></tr>
 {row_html('Formative Assessment:', 'formative_assessment')}
 <tr><td colspan="{span}" class="section-header">Ways Forward.</td></tr>
 {row_html('Extended learning opportunities:', 'extended_learning')}
 {row_html('Reflections:', 'reflection')}
</table>
<div class="meta">{cell(PLAN['overview'])}</div>
</body></html>
"""
preview_path = OUT / "ILAW_SAMPLE_preview.html"
preview_path.write_text(html_doc, encoding="utf-8")
print("WROTE", preview_path.relative_to(ROOT))
print("WROTE", (OUT / "prompt_g11_trig.txt").relative_to(ROOT), f"({len(prompt):,} chars)")
