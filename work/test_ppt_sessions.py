"""Offline tests for the per-session PowerPoint feature (one deck per session)."""
import io
import json
import sys
import types
import zipfile
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
              "form_submit_button", "select_slider", "radio", "rerun", "progress"):
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


# ------------------------------------------------ 1. 16-slide flow definition
check("1. flow has 16 stages", len(app.PPT_SLIDE_FLOW) == 16, len(app.PPT_SLIDE_FLOW))
check("2. flow starts with title", app.PPT_SLIDE_FLOW[0].startswith("Title"))
check("3. flow ends with closing", app.PPT_SLIDE_FLOW[-1].startswith("Closing"))
check("4. flow has HOTS question stage", any("Higher-Order" in part for part in app.PPT_SLIDE_FLOW))

# ------------------------------------------------ 2. prompt carries session scope
prompt = app.make_ppt_prompt("BASIS TEXT", {"slides": 16, "session_number": 3, "session_topic": "Phases of the Moon",
                                            "teacher": "T", "note": ""})
check("5. prompt pins session number", "Session 3" in prompt)
check("6. prompt pins session topic", "Phases of the Moon" in prompt)
check("7. 16-slide rule is one-for-one", "one-for-one" in prompt and "EXACTLY 16" in prompt)
prompt15 = app.make_ppt_prompt("BASIS", {"slides": 15, "session_number": 1, "session_topic": "T",
                                         "teacher": "T", "note": ""})
check("8. non-16 rule keeps all stages", "never drop a stage" in prompt15 and "EXACTLY 15" in prompt15)

# ------------------------------------------------ 3. session detection normalization
captured = {}


class _Resp:
    def read(self):
        return b"OK"


def fake_ask_ai(prompt_text, opts, api_key=None):
    captured["prompt"] = prompt_text
    return json.dumps({
        "subject": "Science",
        "deck_base_title": "Moon Phases",
        "sessions": [
            {"session": 2, "topic": "Waxing phases"},
            {"session": 1, "topic": "Why the moon changes"},
            {"session": 3, "topic": "Eclipses"},
        ],
    })


original_ask_ai = app.ask_ai
app.ask_ai = fake_ask_ai
try:
    meta, sessions = app.generate_session_topic("BASIS")
finally:
    app.ask_ai = original_ask_ai
check("9. sessions sorted by teaching order", [s["session"] for s in sessions] == [1, 2, 3], sessions)
check("10. topics preserved", sessions[2]["topic"] == "Eclipses")
check("11. meta subject read", meta.get("subject") == "Science")
check("12. session-detection prompt asks for JSON", '"sessions"' in captured["prompt"])

app.ask_ai = lambda *a, **k: json.dumps({"sessions": []})
try:
    app.generate_session_topic("BASIS")
    check("13. empty sessions raise a clear error", False, "no error")
except ValueError as exc:
    check("13. empty sessions raise a clear error", "No sessions" in str(exc))

# ------------------------------------------------ 4. deck build per session
deck_plan = {
    "deck_title": "Moon Phases - Session 2",
    "subject": "Science",
    "theme": {"bg": "F5F9FF", "accent": "2E6FB5", "title": "1A3353", "text": "333333"},
    "slides": [{"title": f"Slide {n}", "bullets": ["a", "b"], "shape": "none"} for n in range(1, 17)],
}
if app.Presentation is not None:
    pptx_bytes = app.build_presentation(deck_plan, "Jose Dennis Plaza Chua")
    check("14. 16-slide deck builds", len(pptx_bytes) > 10000, f"{len(pptx_bytes)} bytes")
    check("15. deck is lightweight", len(pptx_bytes) < 200_000, f"{len(pptx_bytes)} bytes")

    # ------------------------------------------------ 5. multi-deck ZIP
    buffer = io.BytesIO()
    archive = zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED)
    for session_number in (1, 2, 3):
        archive.writestr(f"Moon_Phases_Session_{session_number}.pptx", pptx_bytes)
    archive.close()
    zipped = zipfile.ZipFile(io.BytesIO(buffer.getvalue()))
    check("16. ZIP holds 3 session decks", len(zipped.namelist()) == 3, zipped.namelist())
    check("17. ZIP entries are valid pptx", all(zipped.read(name).startswith(b"PK") for name in zipped.namelist()))
else:
    print("SKIP 14-17: python-pptx not installed")

print()
print("ALL PPT-SESSION TESTS PASSED" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
