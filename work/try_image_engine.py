# -*- coding: utf-8 -*-
"""Scratch check: does the keyless image engine really return a picture right now?

Runs the app's own code path (app.IMAGE_ENGINES → generate_ai_image) against the live
network and saves whatever comes back, so the teacher can see a real result.
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
    st.__dict__["button"] = _mk
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
_tmp = Path(tempfile.mkdtemp(prefix="imgtry_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402
from PIL import Image  # noqa: E402

OUT = ROOT / "work" / "sample_outputs"
OUT.mkdir(parents=True, exist_ok=True)

ENGINE = sys.argv[1] if len(sys.argv) > 1 else "Pollinations — free, no API key at all"
IDEA = "two Filipino pupils measuring a tomato plant in a school garden, bright green leaves, sunny morning"

print("engine:", ENGINE)
pic, served, err = app.generate_ai_image(IDEA, engine=ENGINE, style=app._DEFAULT_IMAGE_STYLE, timeout=150)
if not pic:
    print("NO PICTURE:", err)
    raise SystemExit(1)
path = OUT / ("ai_image_" + ENGINE.split(" — ")[0].replace(" ", "_") + ".jpg")
path.write_bytes(pic)
with Image.open(path) as img:
    print("OK", served, img.format, img.size, f"{len(pic)/1024:.0f} KB", path)
