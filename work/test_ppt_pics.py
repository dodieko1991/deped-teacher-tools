"""v1.2.1: real drawn slide pictures (Pillow), 3 MB deck cap, no-Pillow fallback."""
import sys, types, io, zipfile
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


check("version 1.9.0", app._APP_VERSION == "2.0.1")

theme = {"bg": "FFF7FB", "accent": "C94F7C", "title": "4A1B3A", "text": "3B2B33"}
for idea in ("big sun with three rays over green hills",
             "rain clouds and arrows showing the water cycle",
             "planets orbiting the sun in a starry sky",
             "seed growing in three steps in a garden"):
    png = app._draw_pic_png((440, 440), theme, idea, "C94F7C", "FFF7FB", idea)
    check(f"draw: {idea[:24]}", isinstance(png, (bytes, bytearray)) and len(png) > 3000, f"{len(png)}B")

a = app._draw_pic_png((440, 440), theme, "sun over hills", "C94F7C", "FFF7FB", "k1")
b = app._draw_pic_png((440, 440), theme, "ocean waves and fish", "C94F7C", "FFF7FB", "k2")
check("distinct ideas -> distinct art", a != b)

plan = {"deck_title": "S1 Photosynthesis", "subject": "Science", "theme": theme, "slides": [
    {"title": f"Slide {i}", "bullets": ["Full paragraph meaning. " * 3], "shape": "oval",
     "image_idea": f"sun over hills, scene {i}"} for i in range(1, 9)
]}
data = app.build_presentation(plan, "Teacher", "Floral")
check("deck under 3 MB", len(data) < 3_000_000, f"{len(data)/1e6:.2f} MB")
check("deck still light", len(data) < 1_500_000, f"{len(data)/1e6:.2f} MB")
with zipfile.ZipFile(io.BytesIO(data)) as z:
    pics = [n for n in z.namelist() if n.startswith("ppt/media/")]
    slide_xmls = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
    check("8 media pictures", len(pics) == 8, str(len(pics)))
    check("all pictures referenced", sum(1 for n in slide_xmls if b"blip" in z.read(n)) == 8)

# No-Pillow fallback: decks still build, shapes instead of pictures
saved = app._PILImage
app._PILImage = None
try:
    data2 = app.build_presentation(plan, "Teacher", "Floral")
    with zipfile.ZipFile(io.BytesIO(data2)) as z:
        check("no-Pillow: zero media", not [n for n in z.namelist() if n.startswith("ppt/media/")])
        check("no-Pillow: valid deck", len(z.read("[Content_Types].xml")) > 100)
finally:
    app._PILImage = saved

print("\nALL PICTURE TESTS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
