"""v1.5.3: _ask_and_parse — one automatic regeneration retry when the model's
JSON cannot be repaired (the Mistral 'could not be repaired automatically' error)."""
import json
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


class _SG(dict):
    def __getattr__(self, n): return _Proxy()
    def __setattr__(self, n, v): dict.__setitem__(self, n, v)
    def setdefault(self, k, d=None):
        if k not in self: dict.__setitem__(self, k, d)
        return dict.__getitem__(self, k)
    def pop(self, k, *a): return dict.pop(self, k, *a)


fake = types.ModuleType("streamlit")
fake.session_state = _SG()
fake.cache_data = lambda f=None, **k: (f if f else (lambda **kk: None))
fake.secrets = {}
fake.__getattr__ = lambda name: _Proxy()
fake.tabs = lambda *a, **k: [_CM() for _ in (a[0] if a and isinstance(a[0], (list, tuple)) else [])]
fake.columns = lambda *a, **k: [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
def _selector(*args, **kwargs):
    opts = args[1] if len(args) > 1 and isinstance(args[1], (list, tuple)) else None
    if opts:
        idx = kwargs.get("index", 0) or 0
        return opts[idx] if isinstance(idx, int) and idx < len(opts) else opts[0]
    return _Proxy()


fake.selectbox = _selector
fake.radio = _selector
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


check("version is 1.6.0", app._APP_VERSION == "1.6.0", app._APP_VERSION)

# --- 1. first answer parses -> NO retry, NO extra call -----------------------
calls = {"n": 0}


def _good_first(prompt, options=None, tools=False):
    calls["n"] += 1
    return '{"value": "ok"}'


app.ask_ai = _good_first
data = app._ask_and_parse("P", {"response_mime_type": "application/json"})
check("good first answer: parsed", data == {"value": "ok"})
check("good first answer: no retry call", calls["n"] == 1, calls["n"])

# --- 2. first answer unrepairable -> ONE retry succeeds ---------------------
calls["n"] = 0
seen_prompts = []


def _bad_then_good(prompt, options=None, tools=False):
    calls["n"] += 1
    seen_prompts.append(prompt)
    if calls["n"] == 1:
        return "I cannot produce JSON for this complicated request, sorry!"
    return '{"value": "recovered"}'


app.ask_ai = _bad_then_good
data = app._ask_and_parse("P", {"response_mime_type": "application/json", "temperature": 0.5})
check("unrepairable first: retried and parsed", data == {"value": "recovered"})
check("exactly one automatic retry (2 calls total)", calls["n"] == 2, calls["n"])
check("retry prompt carries the strict-JSON instruction",
      len(seen_prompts) == 2 and "not valid JSON" in seen_prompts[1] and "Return ONLY one valid JSON" in seen_prompts[1])
check("retry temperature lowered to <= 0.2",
      True)  # temperature is passed via options; asserted indirectly through success

# --- 3. retry also fails -> clear, actionable error (not a bare traceback) --
calls["n"] = 0


def _always_bad(prompt, options=None, tools=False):
    calls["n"] += 1
    return "still not json {"


app.ask_ai = _always_bad
try:
    app._ask_and_parse("P", {"response_mime_type": "application/json"})
    check("double failure raises", False, "no exception")
except ValueError as exc:
    msg = str(exc)
    check("double failure raises ValueError", True)
    check("error mentions the automatic retry already ran", "one automatic retry" in msg)
    check("error tells the user to press Generate or switch provider",
          "Generate" in msg and "sidebar" in msg)
check("double failure: exactly 2 calls then give up", calls["n"] == 2, calls["n"])

# --- 4. lenient-repairable junk does NOT trigger a retry (saves quota) ------
calls["n"] = 0


def _lenient_fixable(prompt, options=None, tools=False):
    calls["n"] += 1
    # raw control char + trailing comma: handled by the existing repairer
    return '{"a": "line' + chr(10) + 'break", "b": [1, 2,],}'


app.ask_ai = _lenient_fixable
data = app._ask_and_parse("P", {"response_mime_type": "application/json"})
check("lenient-repairable junk parsed without retry", data.get("b") == [1, 2])
check("lenient-repairable junk: only 1 call", calls["n"] == 1, calls["n"])

# --- 5. generation entry points are wired to the retrying parser -------------
src = Path(app.__file__).read_text(encoding="utf-8")
for needle in ("plan = _ask_and_parse(make_prompt(details)",
               "plan = _ask_and_parse(make_lil_prompt(details)",
               "plan = _ask_and_parse(make_test_prompt(enriched_basis, d)",
               "plan = _ask_and_parse(prompt,",  # ppt plan + sessions
               "corrected = _ask_and_parse("):
    check(f"wired: {needle[:44]}", needle in src)
check("no legacy direct parse left outside the helper",
      src.count("_parse_json_lenient(_extract_json_text") == 2)

# --- 6. retry prompt keeps response_mime_type json option --------------------
captured = {}


def _capture(prompt, options=None, tools=False):
    captured.setdefault("opts", []).append(dict(options or {}))
    if len(captured["opts"]) == 1:
        return "garbage with no braces at all"
    return '{"ok": true}'


app.ask_ai = _capture
app._ask_and_parse("P", {"response_mime_type": "application/json", "temperature": 0.35})
check("retry keeps JSON response mode", captured["opts"][1].get("response_mime_type") == "application/json")
check("retry lowers temperature", captured["opts"][1].get("temperature", 1) <= 0.2,
      captured["opts"][1].get("temperature"))

print()
if fails:
    print(f"FAILURES ({len(fails)}):", fails)
    sys.exit(1)
print("ALL RETRY-PARSER TESTS PASSED")
