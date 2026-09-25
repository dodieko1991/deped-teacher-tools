# -*- coding: utf-8 -*-
"""v2.0.1 — the bundled BOW seed lets the library work without the Desktop folder.

Simulates Streamlit Cloud: NO Desktop BOW folder, only the repo files that Cloud
deploys (app.py + bow_library_seed.json next to it). Verifies:
  1. load_bow_library() returns the full bundled library (13 grades / 241 subjects)
  2. the missing-folder info message no longer appears in app.py
  branch: local Desktop library still wins over the seed (test 3) via env redirect
"""
import base64
import gzip
import io
import json
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
    st.success = _caption = st.caption = _mk
    st.write = _mk; st.markdown = _mk
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Simulate Streamlit Cloud: an EMPTY BOW folder. The env var must be set BEFORE
# importing app — importing app runs the whole module (UI included), which calls
# load_bow_library() at import time.
CLOUD_TMP = Path(tempfile.mkdtemp(prefix="bowcloud_"))
CLOUD_TMP.mkdir(exist_ok=True)  # exists but empty — like Cloud without the Desktop folder
os.environ["DEPED_BOW_LIBRARY"] = str(CLOUD_TMP)
os.environ["DEPED_BOW_CACHE"] = str(CLOUD_TMP / "bow_library_cache.json")
import app  # noqa: E402

failures = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)


# --- tests ---
lib = app.load_bow_library()
grades = sorted(lib)
subjects = sum(len(s) for s in lib.values())
check("1. seed fallback loads full library", subjects == 241, f"grades={len(grades)} subjects={subjects}")
check("2. all 13 grades present", len(grades) == 13, grades)
check("3. G9 Science entry shape", all(k in lib.get("Grade 9", {}).get("Science", {})
                                       for k in ("terms", "area", "grade")), sorted(lib.get("Grade 9", {}).get("Science", {}))[:6])
g9_terms = lib["Grade 9"]["Science"]["terms"]
check("4. G9 Science has week rows", any(r.get("from") for t in g9_terms for r in t["weeks"]), f"{len(g9_terms)} terms")

# Seed texts decompress
packed = lib["Grade 9"]["Science"].get("text", "")
check("5. seed embeds compressed BOW text", bool(packed), f"{len(packed)} chars")
if packed:
    text = gzip.decompress(base64.b64decode(packed)).decode("utf-8")
    check("6. G9 Science seed text parses", "SCIENCE" in text.upper() and len(text) > 1000, f"{len(text)} chars")
check("7. _seed_text() decompresses", len(app._seed_text("Grade 9", "Science")) > 1000, "")
check("8. _seed_text() empty for unknown subject", app._seed_text("Grade 9", "Nope") == "", "")
check("9. library_bow_text falls back to seed", len(app.library_bow_text("Grade 9", "Science")) > 1000, "")
check("10. library_bow_text unknown subject empty", app.library_bow_text("Grade 9", "Nope") == "", "")

src = (ROOT / "app.py").read_text(encoding="utf-8")
check("11. version 2.0.1", app._APP_VERSION == "2.0.1", app._APP_VERSION)
check("12. missing-library message gone from code",
      "was not found on the Desktop" not in src,
      "message removed because the seed fallback makes the library always available")
check("13. seed file bundled in repo", (ROOT / "bow_library_seed.json").exists(),
      f"{(ROOT / 'bow_library_seed.json').stat().st_size / 1024:.0f} KB")

# A local Desktop library (env-redirected synthetic library with real PDFs) must
# still win over the seed — test the scan branch with a tiny real PDF library.
import shutil  # noqa: E402
from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import (DictionaryObject, NameObject, ArrayObject,  # noqa: E402
                           TextStringObject, NumberObject, DecodedStreamObject)


def write_pdf(path, text):
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    ops = ["BT"]
    y = 750
    for line in text.split("\n"):
        safe = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        ops.append(f"/F1 10 Tf 1 0 0 1 40 {y} Tm ({safe}) Tj")
        y -= 14
    ops.append("ET")
    stream = " ".join(ops).encode("latin-1", "replace")
    page = writer.pages[0]
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = PDF_RES = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    page[NameObject("/Resources")] = resources
    content = DecodedStreamObject()
    content.set_data(stream)
    page[NameObject("/Contents")] = content
    with open(path, "wb") as fh:
        writer.write(fh)


local_tmp = Path(tempfile.mkdtemp(prefix="bowlocal_"))
g9 = local_tmp / "Grade 9"
g9.mkdir(parents=True)
write_pdf(g9 / "[G9] Science.pdf", "SCIENCE\nGrade 9\nFirst Term\nContent Standard\n1 to 3 Local Test Lesson\nbullet one competency here")
os.environ["DEPED_BOW_LIBRARY"] = str(local_tmp)
os.environ["DEPED_BOW_CACHE"] = str(local_tmp / "bow_library_cache.json")
# Fresh session state: clear the single payload memo, then point the module
# constants at the local library and scan branch.
app.st.session_state.clear()
app.BOW_LIBRARY_DIR = local_tmp
app.BOW_LIBRARY_CACHE = local_tmp / "bow_library_cache.json"
local_lib = app.load_bow_library()
check("14. local scan still wins over seed",
      any("Local Test Lesson" in r["lesson"] for t in local_lib["Grade 9"]["Science"]["terms"] for r in t["weeks"]),
      sorted(local_lib.get("Grade 9", {})))
check("15. local library has only the local subject", len(local_lib["Grade 9"]) == 1, sorted(local_lib["Grade 9"]))

print(f"\n{len(failures)} failures" if failures else "\nALL PASS")
sys.exit(1 if failures else 0)
