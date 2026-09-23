import sys, types, json

# --- universal streamlit stub so we can import app.py offline ---
class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False

class _Proxy:
    """Anything: callable, context manager, and every attribute is another _Proxy."""
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return _CM()
    def __getattr__(self, name): return _Proxy()
    def __iter__(self): return iter([_CM(), _CM()])
    def __bool__(self): return False

class _State(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value

stub = _Proxy()
stub.secrets = {}
stub.session_state = _State()
stub.tabs = lambda labels: tuple(_CM() for _ in labels)

def _selectbox(label, options=None, *a, **k):
    try:
        return (options or [])[k.get("index", 0)]
    except Exception:
        return ""
def _text_input(*a, **k):
    return k.get("value", "") or ""

stub.selectbox = _selectbox
stub.text_input = _text_input
stub.text_area = _text_input
stub.file_uploader = lambda *a, **k: None

def _columns(spec):
    n = spec if isinstance(spec, int) else (len(spec) if spec else 2)
    return [_CM() for _ in range(max(1, int(n)))]

stub.columns = _columns
sys.modules["streamlit"] = stub

errors_mod = types.ModuleType("streamlit.errors")
class StreamlitSecretNotFoundError(Exception):
    pass
errors_mod.StreamlitSecretNotFoundError = StreamlitSecretNotFoundError
sys.modules["streamlit.errors"] = errors_mod

sys.path.insert(0, ".")
import app

# 1. EXACT error scenario: raw newline inside a JSON string (Mistral style)
raw = '{\n  "plan_title": "Linear\nInequalities",\n  "sessions": [\n    {\n      "flow": "Step 1\tMotivation\nStep 2\tDiscussion"\n    }\n  ]\n}'
try:
    json.loads(raw)
    print("1. FAIL: strict loads accepted (test invalid)")
except json.JSONDecodeError as e:
    print(f"1. strict rejects raw newline (matches user's error: {e})")

out = app._parse_json_lenient(raw)
assert out["plan_title"] == "Linear\nInequalities", out
assert out["sessions"][0]["flow"] == "Step 1\tMotivation\nStep 2\tDiscussion"
print("2. lenient parses raw-control-char JSON, values preserved")

# 3. Valid JSON still passes unchanged
good = '{"a": "b\\nc", "n": [1,2]}'
assert app._parse_json_lenient(good) == json.loads(good)
print("3. valid JSON unaffected")

# 4. Real-world Mistral shape: lesson-plan skeleton with raw newlines/tabs in strings
mistral_like = '''{
  "plan_title": "Pagbasa ug Pag-sulat",
  "overview": "Ang maong
leksyon nagtukdo...",
  "standards": "Nasodnon nga
standard",
  "sessions": [
    {"topic": "Session A", "objectives": ["Obj 1\twith tab", "Obj 2"], "flow": "Motivation
Discussion
Application"}
  ]
}'''
out2 = app._parse_json_lenient(mistral_like)
assert "leksyon" in out2["overview"] and "\n" in out2["overview"]
assert out2["sessions"][0]["flow"].count("\n") == 2
print("4. lesson-plan-shaped JSON with raw newlines/tabs parses")

# 5. Extraction pipeline end-to-end: fence + chatter + control chars
messy = (
    "Here is your JSON:\n```json\n"
    '{"items": [{"q": "What\nis 2+2?"}]}\n'
    "```\nHope this helps!"
)
ext = app._extract_json_text(messy)
out3 = app._parse_json_lenient(ext)
assert out3["items"][0]["q"] == "What\nis 2+2?"
print("5. _extract_json_text + lenient pipeline works on messy output")

# 6. Escaped newline in proper JSON still handled by strict path first
escaped = '{"flow": "line1\\nline2"}'
assert app._parse_json_lenient(escaped)["flow"] == "line1\nline2"
print("6. proper escaped \\n handled")

print("ALL PARSER TESTS PASSED")
