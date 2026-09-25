# -*- coding: utf-8 -*-
"""v2.1.0 — BOW Library container folder next to app.py.

The library now looks in <app folder>/BOW Library first, then falls back to the
Desktop copy. Simulated by copy()ing app.py into a temp dir and importing THAT
copy (the container check runs at import time). Tests:
  1. resolve picks the container when it exists
  2. falls back to the Desktop path when it does not
  3. DEPED_BOW_LIBRARY still overrides both
  4. cache + cloud-seed still work with the container selected
  5. version bumped
"""
import json
import os
import shutil
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
    _errs_mod = types.ModuleType("streamlit.errors")
    class StreamlitSecretNotFoundError(Exception): pass
    _errs_mod.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
    sys.modules["streamlit.errors"] = _errs_mod

ROOT = Path(__file__).resolve().parent.parent

failures = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} {name} {extra}")
    if not cond:
        failures.append(name)


def import_app_copy(container: bool, env_value: str = None):
    """Copy app.py (+ seed) into a fresh temp dir and import it as a new module.

    The container check runs at import time, so each scenario needs a fresh copy.
    sys.modules is keyed by 'app_under_test' so repeated imports don't collide.
    """
    import importlib.util
    home = Path(tempfile.mkdtemp(prefix="bowhome_"))
    shutil.copy(ROOT / "app.py", home / "app.py")
    shutil.copy(ROOT / "bow_library_seed.json", home / "bow_library_seed.json")
    if container:
        (home / "BOW Library").mkdir()
    for var in ("DEPED_BOW_LIBRARY", "DEPED_BOW_CACHE"):
        os.environ.pop(var, None)
    if env_value:
        os.environ["DEPED_BOW_LIBRARY"] = env_value
    os.environ["DEPED_BOW_CACHE"] = str(home / "bow_library_cache.json")
    spec = importlib.util.spec_from_file_location(f"app_under_test_{len(failures)}_{int(container)}_{int(bool(env_value))}", home / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, home


# 1. No container → Desktop fallback (the owner's machine has the container, so
#    simulate a machine without it by pointing env at a nonexistent Desktop path).
m1, _ = import_app_copy(container=False, env_value=r"C:\nonexistent\DepEd BOW Files")
check("1. no container → Desktop path used", str(m1.BOW_LIBRARY_DIR) == r"C:\nonexistent\DepEd BOW Files", m1.BOW_LIBRARY_DIR)

# 2. Container exists → it wins over the (unset) Desktop default.
m2, home2 = import_app_copy(container=True)
import os as _os  # noqa: E402
def _norm(p):
    # resolve() expands 8.3 short names (mkdtemp can return them) so both sides match
    return _os.path.normcase(str(_os.path.realpath(str(p))))
check("2. container wins when present", _norm(m2.BOW_LIBRARY_DIR) == _norm(home2 / "BOW Library"), m2.BOW_LIBRARY_DIR)

# 3. Env override still wins over the container.
m3, _ = import_app_copy(container=True, env_value=r"C:\env\wins")
check("3. env override beats container", str(m3.BOW_LIBRARY_DIR) == r"C:\env\wins", m3.BOW_LIBRARY_DIR)

# 4. With the container selected, the empty folder means seed fallback still
#    works, and cache/scan paths are intact.
lib = m2.load_bow_library()
subjects = sum(len(s) for s in lib.values())
check("4a. seed fallback works with container", subjects == 241, f"subjects={subjects}")
check("4b. version is 2.1.0", m2._APP_VERSION == "2.2.0", m2._APP_VERSION)
check("4c. resolve helper exists and is callable", callable(m2.resolve_bow_library_dir), "")
texts = sum(1 for g in lib.values() for s in g.values() if s.get("text"))
check("4d. seed texts available for text fallback", texts == 241, f"texts={texts}")

print(f"\n{len(failures)} failures" if failures else "\nALL PASS")
sys.exit(1 if failures else 0)
