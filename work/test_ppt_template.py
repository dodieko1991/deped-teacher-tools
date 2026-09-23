"""v1.5.3: user-uploaded PPT template mode — template carries the design, AI fills content."""
import io
import sys
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
fake.columns = lambda *a, **k: [_CM() for _ in (4 if a and isinstance(a[0], (list, tuple)) else a[0],)] if False else [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
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

from pptx import Presentation as _LoadPptx  # noqa: E402
from pptx.util import Inches as _In  # noqa: E402

failures = []


def check(name, condition, extra=""):
    print(f"{'PASS' if condition else 'FAIL'} {name} {extra}")
    if not condition:
        failures.append(name)


def mini_plan(slides=3, theme=None):
    return {
        "deck_title": "Session 1 — Test Deck", "subject": "Science",
        "theme": theme or {"bg": "F5F9FF", "accent": "2E6FB5", "title": "1A3353", "text": "333333"},
        "slides": [{"title": f"Slide {i + 1}", "bullets": [f"Point {i + 1}a", f"Point {i + 1}b"],
                    "shape": "none", "image_idea": "big sun over green hills"} for i in range(slides)],
    }


# Build a 4:3 sample user template with sample slides, theme, and a title layout.
src = _LoadPptx()
src.slide_width, src.slide_height = _In(10), _In(7.5)
tslide = src.slides.add_slide(src.slide_layouts[0])
tslide.shapes.title.text = "Sample School Template"
body = tslide.placeholders[1]
body.text_frame.text = "Old content that must disappear"
buf = io.BytesIO()
src.save(buf)
TEMPLATE_BYTES = buf.getvalue()

# --- 1. Template mode ---
plan = mini_plan()
out = app.build_presentation(plan, "Teacher Chua", "Education", TEMPLATE_BYTES)
check("template deck returns bytes", isinstance(out, bytes) and len(out) > 20000, f"{len(out)} bytes")
deck = _LoadPptx(io.BytesIO(out))
check("template slide size preserved (10in 4:3)", abs(deck.slide_width - _In(10)) < 2000, f"{deck.slide_width}")
check("template slide size height kept", abs(deck.slide_height - _In(7.5)) < 2000)
check("template sample slides wiped", len(deck.slides) == 3, f"{len(deck.slides)} slides")
texts = " | ".join(shape.text_frame.text for slide in deck.slides for shape in slide.shapes if shape.has_text_frame)
check("template sample text gone", "Sample School Template" not in texts and "Old content" not in texts)
check("AI content present", "Slide 1" in texts and "Point 1a" in texts)
check("teacher on title slide", "Teacher Chua" in texts)
# scaled geometry: title box left is 0.6in * (10/13.333) = 0.45in
s1 = deck.slides[0]
title_shapes = [sh for sh in s1.shapes if sh.has_text_frame and "Slide 1" in sh.text_frame.text]
check("title box found", bool(title_shapes))
if title_shapes:
    left_in = title_shapes[0].left / 914400
    check("geometry scaled to 4:3", abs(left_in - 0.45) < 0.05, f"left={left_in:.2f}in")
check("pictures drawn in template mode",
      sum(1 for slide in deck.slides for sh in slide.shapes if sh.shape_type == 13) >= 1)

# --- 2. No-template mode unchanged ---
out2 = app.build_presentation(mini_plan(), "Teacher Chua", "Education", None)
deck2 = _LoadPptx(io.BytesIO(out2))
check("no-template keeps 16:9", abs(deck2.slide_width - _In(13.333)) < 2000)
check("no-template builds 3 slides", len(deck2.slides) == 3)

# --- 3. Corrupt template -> honest error ---
try:
    app.build_presentation(mini_plan(), "T", "Education", b"not-a-pptx")
    check("corrupt template raises", False)
except ValueError as exc:
    check("corrupt template raises", "could not be opened" in str(exc))

# --- 4. 16:9 user template passes through cleanly ---
src169 = _LoadPptx()
src169.slide_width, src169.slide_height = _In(13.333), _In(7.5)
src169.slides.add_slide(src169.slide_layouts[5])
b169 = io.BytesIO()
src169.save(b169)
out3 = app.build_presentation(mini_plan(slides=2), "T", "Education", b169.getvalue())
deck3 = _LoadPptx(io.BytesIO(out3))
check("16:9 template passthrough", abs(deck3.slide_width - _In(13.333)) < 2000 and len(deck3.slides) == 2)

# --- 5. Version ---
check("version is 1.8.0", app._APP_VERSION == "1.8.0", app._APP_VERSION)

print()
if failures:
    print(f"{len(failures)} FAILED: {failures}")
    sys.exit(1)
print("ALL CHECKS PASSED")
