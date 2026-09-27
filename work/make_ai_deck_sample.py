# -*- coding: utf-8 -*-
"""Build a real sample deck with AI pictures through the app's own build_presentation().

Uses the keyless picture engine so it runs without any API key.
Output: work/sample_outputs/POWERPOINT_SAMPLE_AI_pictures.pptx
"""
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


def _stub():
    st = types.ModuleType("streamlit")
    errs = types.ModuleType("streamlit.errors")
    class E(Exception): pass
    errs.StreamlitInvalidLayoutContextError = E
    st.errors = errs
    st.__path__ = []
    def _mk(*a, **k): return _CM()
    for name in ("subheader", "info", "warning", "error", "success", "caption", "write", "markdown",
                 "title", "header", "download_button", "expander", "spinner", "divider", "help",
                 "set_page_config", "image", "progress", "empty", "stop", "rerun", "select_slider",
                 "radio", "file_uploader", "metric", "plotly_chart", "dataframe", "table", "link_button"):
        setattr(st, name, _mk)
    st.button = _mk
    st.session_state = {}
    st.sidebar = _Proxy()
    st.form = _mk
    st.form_submit_button = lambda *a, **k: False
    st.columns = lambda n, *a, **k: [_CM() for _ in (range(n) if isinstance(n, int) else n)]
    st.tabs = lambda labels: [_CM() for _ in labels]
    st.cache_data = lambda f=None, **k: (f if f else (lambda g: g))
    st.multiselect = lambda label, options=[], *a, **k: list(options)
    st.text_input = lambda label, value="", *a, **k: ("" if value is None else value)
    st.text_area = lambda label, value="", *a, **k: ("" if value is None else value)
    st.number_input = lambda label, value=0, *a, **k: value
    st.selectbox = lambda label, options=[], *a, **k: (options[0] if options else None)
    st.slider = lambda label, *a, value=None, **k: (value if value is not None else 1)
    st.checkbox = lambda *a, **k: False
    st.secrets = {}
    return st


sys.modules.setdefault("streamlit", _stub())
if "streamlit.errors" not in sys.modules:
    _errs = types.ModuleType("streamlit.errors")
    class StreamlitSecretNotFoundError(Exception): pass
    _errs.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
    sys.modules["streamlit.errors"] = _errs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = Path(tempfile.mkdtemp(prefix="aideck_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402

PLAN = {
    "deck_title": "Session 1 — Trigonometric Identities",
    "subject": "Grade 11 · Advanced Mathematics",
    "theme": {"bg": "F5F9FF", "accent": "2E6FB5", "title": "1A3353", "text": "333333"},
    "slides": [
        {"title": "Trigonometric Identities", "bullets": ["Grade 11 · Advanced Mathematics", "Session 1 of 4"],
         "shape": "none",
         "image_idea": "a big triangle on a maths chalkboard in a bright Filipino classroom, blue and white, geometric shapes"},
        {"title": "Lesson Objectives", "bullets": ["Use the sum and difference formulas", "Verify identities step by step",
                                                   "Solve real-life problems with identities"], "shape": "oval",
         "image_idea": "three pupils raising hands beside a stack of mathematics books in a sunny classroom, yellow and green"},
        {"title": "Motivation: Same Answer?", "bullets": ["Compare sin(45° + 30°) with sin 45° + sin 30°",
                                                          "Do the two really give the same value?"], "shape": "arrow",
         "image_idea": "a curious pupil comparing two calculators on a wooden desk, question mark shapes, bright classroom colors"},
        {"title": "Sum and Difference Formulas", "bullets": ["sin(A ± B) = sin A cos B ± cos A sin B",
                                                              "cos(A ± B) = cos A cos B ∓ sin A sin B"], "shape": "diamond",
         "image_idea": "a large geometric diagram of two angles adding up, drawn in chalk with blue and orange colors, no text"},
        {"title": "Guided Practice", "bullets": ["Find the exact value of sin 75°", "Pair up and check each other's steps"],
         "shape": "rect",
         "image_idea": "two pupils working together on a mathematics worksheet in a school garden, green leaves, morning light"},
        {"title": "Application", "bullets": ["A flagpole casts a shadow at an angle — find its height",
                                             "Which formula did you use, and why?"], "shape": "triangle",
         "image_idea": "a tall flagpole casting a long shadow on a school field with pupils measuring with a tape, sunny afternoon"},
        {"title": "Generalization", "bullets": ["Identities let us rewrite expressions without changing their value",
                                                "Always show every step when verifying"], "shape": "oval",
         "image_idea": "a pupil presenting a clean solution on the board to classmates, warm classroom colors, plants by the window"},
        {"title": "Assignment", "bullets": ["Prove cos(A - B) = cos A cos B + sin A sin B",
                                            "Bring one real-life example next meeting"], "shape": "none",
         "image_idea": "a school bag with mathematics books and a notebook on a desk beside a window, soft afternoon light"},
    ],
}

ENGINE = "Pollinations — free, no API key at all"
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 4

print(f"building with engine={ENGINE} ai_pictures={COUNT}")
deck = app.build_presentation(PLAN, "Ma'am Reyes", "Education — friendly classroom look, soft blues and greens",
                              None, image_engine=ENGINE, image_style=app._DEFAULT_IMAGE_STYLE,
                              image_max=COUNT)
stats = app.st.session_state.get("ppt_img_stats") or {}
out = ROOT / "work" / "sample_outputs" / "POWERPOINT_SAMPLE_AI_pictures.pptx"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(deck)
print("stats:", stats)
print(f"OK {out} {len(deck)/1024:.0f} KB · {len(PLAN['slides'])} slides · {stats.get('ai', 0)} AI picture(s)")
