"""Reproduce the user's PermissionError: feedback.xlsx locked by Excel (standalone)."""
import os
import pathlib
import sys
import tempfile
import types
from pathlib import Path

# ---------------------------------------------------------------- streamlit stub
class _CM:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __call__(self, *args, **kwargs):
        return _CM()

    def __getattr__(self, name):
        return _CM()

    def __iter__(self):
        return iter((_CM(), _CM(), _CM()))

    def __bool__(self):
        return False


class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            state = _State()
            self[name] = state
            return state

    def __setattr__(self, name, value):
        self[name] = value

    def setdefault(self, key, default=None):
        if key not in self or self[key] is None:
            self[key] = default
        return self[key]


stub = types.ModuleType("streamlit")
stub.set_page_config = lambda *a, **k: None
stub.sidebar = _CM()
stub.session_state = _State()
stub.secrets = {}
stub.tabs = lambda labels: tuple(_CM() for _ in labels)
stub.columns = lambda n, **k: tuple(_CM() for _ in range(n if isinstance(n, int) else len(n)))
for _name in ("expander", "container", "form", "spinner"):
    setattr(stub, _name, lambda *a, **k: _CM())
for _name in ("title", "caption", "markdown", "info", "write", "error", "success", "warning",
              "subheader", "header", "button", "download_button", "link_button",
              "form_submit_button", "select_slider", "radio", "rerun"):
    setattr(stub, _name, lambda *a, **k: None)
stub.cache_data = lambda f=None, **k: (f if f else (lambda g: g))
stub.selectbox = lambda *a, **k: (a[1] if len(a) > 1 and a[1] else (k.get("options") or [""]))[0]
stub.text_input = lambda *a, **k: (k.get("value") or "") or ""
stub.text_area = lambda *a, **k: (k.get("value") or "") or ""
stub.file_uploader = lambda *a, **k: None
stub.errors = types.ModuleType("streamlit.errors")
stub.errors.StreamlitSecretNotFoundError = type("StreamlitSecretNotFoundError", (Exception,), {})
sys.modules["streamlit"] = stub
sys.modules["streamlit.errors"] = stub.errors

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

failures = []


def check(name, condition, extra=""):
    print(f"{'PASS' if condition else 'FAIL'} {name} {extra}")
    if not condition:
        failures.append(name)


tmpdir = pathlib.Path(tempfile.mkdtemp())
original_main = app.FEEDBACK_FILE
original_overflow = app.FEEDBACK_OVERFLOW_FILE
original_hook = app.FEEDBACK_HOOK_FILE

app.FEEDBACK_FILE = tmpdir / "feedback.xlsx"
app.FEEDBACK_OVERFLOW_FILE = tmpdir / "feedback_overflow.xlsx"
app.FEEDBACK_HOOK_FILE = tmpdir / "none.txt"
os.environ.pop("FEEDBACK_WEBHOOK_URL", None)

try:
    # Normal flow first
    status = app.save_feedback("Normal User", "⭐⭐⭐⭐⭐", "works", "-")
    check("1. normal flow -> synced", status.startswith("synced"), status)

    # Lock feedback.xlsx exactly like Excel does: lock the first byte of the file
    locked = open(app.FEEDBACK_FILE, "r+b")
    lock_applied = False
    try:
        import msvcrt
        msvcrt.locking(locked.fileno(), msvcrt.LK_NBLCK, 1)
        lock_applied = True
    except (ImportError, OSError):
        pass  # non-Windows dev machines: the open handle still triggers PermissionError on save
    try:
        status = app.save_feedback("Locked Case", "⭐⭐⭐", "file was open in Excel", "-")
        check("2. locked file -> still synced via Google Form", status.startswith("synced"), status)
        check("3. message mentions the overflow file", "overflow" in status, status)
        check("4. overflow file now exists with the row",
              app.FEEDBACK_OVERFLOW_FILE.exists(),
              f"exists={app.FEEDBACK_OVERFLOW_FILE.exists()}")
        from openpyxl import load_workbook
        rows = list(load_workbook(str(app.FEEDBACK_OVERFLOW_FILE)).active.iter_rows(values_only=True))
        check("5. overflow row content intact", len(rows) == 2 and rows[1][1] == "Locked Case", rows)
        status2 = app.save_feedback("Second While Locked", "⭐", "again", "-")
        rows2 = list(load_workbook(str(app.FEEDBACK_OVERFLOW_FILE)).active.iter_rows(values_only=True))
        check("6. second locked submission also lands in overflow", len(rows2) == 3 and rows2[2][1] == "Second While Locked", len(rows2))
        print(f"   (lock_applied={lock_applied}; open file handle itself blocks rewrite on Windows)")
    finally:
        if lock_applied:
            try:
                import msvcrt
                msvcrt.locking(locked.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        locked.close()

    # Lock released -> back to the main file
    status3 = app.save_feedback("After Unlock", "⭐⭐", "recovered", "-")
    from openpyxl import load_workbook
    main_rows = list(load_workbook(str(app.FEEDBACK_FILE)).active.iter_rows(values_only=True))
    check("7. after unlock, main file resumes", status3.startswith("synced") and main_rows[-1][1] == "After Unlock", status3)

finally:
    app.FEEDBACK_FILE = original_main
    app.FEEDBACK_OVERFLOW_FILE = original_overflow
    app.FEEDBACK_HOOK_FILE = original_hook

print()
print("ALL LOCK TESTS PASSED" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
