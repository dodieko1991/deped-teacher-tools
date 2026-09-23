import sys, types, json, io

class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False

class _Proxy:
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
stub.selectbox = _selectbox
stub.text_input = lambda *a, **k: k.get("value", "") or ""
stub.text_area = stub.text_input
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

st_ss = stub.session_state
st_ss["provider"] = "Groq"  # no ceiling: 400-retry is the safety net here
st_ss["api_key"] = "gsk_test"
st_ss["model_choice"] = "Auto pick (recommended - skips busy models)"

# 1. EXACT user error: 66812 requested vs 32768 max -> adaptive retry with fitted budget
USER_ERROR = ('HTTP 400 from provider: {"error":{"message":"This endpoint\'s maximum context length '
              'is 32768 tokens. However, you requested about 66812 tokens (1276 of text input, '
              '65536 in the output). Please reduce the length of either one, or use the '
              'context-compression plugin to compress your prompt automatically.","code":400,'
              '"metadata":{"provider_name":null}}}')
budgets = []
def fake_ctx_then_ok(provider, key, model, system, user, temperature, max_tokens):
    budgets.append((model, max_tokens))
    if max_tokens > 32768:
        raise RuntimeError(USER_ERROR)
    return "RETRY-OK"
app._openai_chat = fake_ctx_then_ok
out = app.ask_ai("make a test", {"max_output_tokens": 65536})
assert out == "RETRY-OK", out
assert len(budgets) == 2, budgets
assert budgets[0][1] == 65536, budgets[0]
assert budgets[1][1] == 32768 - 1276 - 1024, budgets[1]  # exact fitted budget
print("1. exact OpenRouter 400 -> same model retried with 30468 output tokens, SUCCESS")

# 2. fit via comma-formatted numbers (OpenAI style: 32,768)
comma_error = 'HTTP 400 from provider: {"error":{"message":"This model\'s maximum context length is 32,768 tokens. However, you requested about 70000 tokens (4,464 of text input, 65536 in the output)."}}'
budgets.clear()
def fake_comma(provider, key, model, system, user, temperature, max_tokens):
    budgets.append((model, max_tokens))
    if max_tokens > 32768:
        raise RuntimeError(comma_error)
    return "COMMA-OK"
app._openai_chat = fake_comma
out = app.ask_ai("make a test", {"max_output_tokens": 65536})
assert out == "COMMA-OK" and budgets[1][1] == 32768 - 4464 - 1024, (out, budgets)
print("2. comma-formatted numbers parsed correctly")

# 3. tiny context model (8192 total, 7000 input -> fit 168 < 4096) -> skips to NEXT model
st_ss["provider"] = "OpenRouter"
st_ss["api_key"] = "sk-or-test"
calls = []
def fake_tiny(provider, key, model, system, user, temperature, max_tokens):
    calls.append((model, max_tokens))
    if model == "qwen/qwen3.8-27b:free":
        raise RuntimeError('HTTP 400 from provider: maximum context length is 8192 tokens (7000 of text input, 65536 in the output)')
    return "NEXT-MODEL-OK"
app._openai_chat = fake_tiny
out = app.ask_ai("make a test", {"max_output_tokens": 65536})
assert out == "NEXT-MODEL-OK", out
assert calls[0][0] == "qwen/qwen3.8-27b:free" and calls[1][0] != "qwen/qwen3.8-27b:free", calls
print("3. context too small -> moved to next model instead of failing")

# 4. context error even after one adaptive retry -> next model, no crash
seq = []
def fake_still_ctx(provider, key, model, system, user, temperature, max_tokens):
    seq.append((model, max_tokens))
    raise RuntimeError('HTTP 400 from provider: maximum context length is 32768 tokens (20000 of text input, 65536 in the output)')
app._openai_chat = fake_still_ctx
try:
    app.ask_ai("make a test", {"max_output_tokens": 65536})
    print("4. FAIL: expected error")
except RuntimeError as e:
    m = str(e)
    assert "None of the OpenRouter models" in m, m
    assert len(seq) >= 2, seq  # first model tried twice (original + fitted budget)
    print(f"4. persistent context error -> tried next models, honest final error ({len(seq)} attempts)")

# 5. NON-context 400 (bad parameter) still fails fast
def fake_bad_param(provider, key, model, system, user, temperature, max_tokens):
    raise RuntimeError('HTTP 400 from provider: {"error":{"message":"invalid parameter: temperature"}}')
app._openai_chat = fake_bad_param
try:
    app.ask_ai("make a test", {"max_output_tokens": 65536})
    print("5. FAIL: expected error")
except RuntimeError as e:
    assert "invalid parameter" in str(e) and "None of the" not in str(e)
    print("5. genuine bad-parameter 400 -> raised immediately (unchanged)")

# 6. _context_retry_budget unit checks
assert app._context_retry_budget(USER_ERROR, 65536) == 30468
assert app._context_retry_budget("some random error about weather", 65536) is None
assert app._context_retry_budget("HTTP 400: maximum context length is 4096 tokens (3000 of text input, 65536 in the output)", 65536) is None  # fit=72 < 4096
print("6. budget helper unit checks OK")

print("ALL CONTEXT-400 TESTS PASSED")
