import sys, types, json, io
import urllib.error

# --- universal streamlit stub so we can import app.py offline ---
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

st_ss = stub.session_state
st_ss["provider"] = "Groq"
st_ss["api_key"] = "gsk_test_key"
st_ss["model_choice"] = "Auto pick (recommended - skips busy models)"

# 1. Groq 403 with real error body -> forbidden message with the body included
def fake_403(provider, key, model, system, user, temperature, max_tokens):
    raise RuntimeError('HTTP 403 from provider: {"error":{"message":"Invalid API Key","type":"invalid_request_error"}}')
app._openai_chat = fake_403
try:
    app.ask_ai("hello")
    print("1. FAIL: expected error")
except RuntimeError as e:
    m = str(e)
    assert "refused every request" in m, m
    assert "NOT a quota" in m, m
    assert "Invalid API Key" in m, m  # real reason surfaced
    print("1. 403 -> honest auth message WITH Groq's real reason")

# 2. 429 quota -> quota message (unchanged behavior)
def fake_429(provider, key, model, system, user, temperature, max_tokens):
    raise RuntimeError('HTTP 429 from provider: {"error":{"message":"Rate limit exceeded"}}')
app._openai_chat = fake_429
try:
    app.ask_ai("hello")
    print("2. FAIL: expected error")
except RuntimeError as e:
    m = str(e)
    assert "quota or rate-limit" in m, m
    print("2. 429 -> quota message preserved")

# 3. 403 body that mentions rate limits -> still quota (quota words checked first)
def fake_403_quota(provider, key, model, system, user, temperature, max_tokens):
    raise RuntimeError('HTTP 403 from provider: {"error":{"message":"org has exceeded its rate limit"}}')
app._openai_chat = fake_403_quota
try:
    app.ask_ai("hello")
    print("3. FAIL: expected error")
except RuntimeError as e:
    assert "quota or rate-limit" in str(e), str(e)
    print("3. 403-with-quota-body -> quota message (correct priority)")

# 4. First model 404, second works -> success
calls = []
def fake_mixed(provider, key, model, system, user, temperature, max_tokens):
    calls.append(model)
    if model == "openai/gpt-oss-120b":
        raise RuntimeError("HTTP 404 from provider: model not found")
    return "OK:" + model
app._openai_chat = fake_mixed
out = app.ask_ai("hello")
assert out.startswith("OK:"), out
assert len(calls) == 2, calls
print("4. 404 on one model -> falls through to next model, success")

# 5. 500 server error -> raises immediately (not classified)
def fake_500(provider, key, model, system, user, temperature, max_tokens):
    raise RuntimeError("HTTP 500 from provider: internal error")
app._openai_chat = fake_500
try:
    app.ask_ai("hello")
    print("5. FAIL: expected error")
except RuntimeError as e:
    assert "500" in str(e) and "refused" not in str(e) and "quota" not in str(e)
    print("5. 500 -> raised as-is (fail fast)")

# 6. _http_json surfaces HTTPError body
class _FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def fake_urlopen(request, timeout=None):
    raise urllib.error.HTTPError("http://x", 403, "Forbidden",
                                 {"Content-Type": "application/json"},
                                 io.BytesIO(b'{"error":{"message":"Invalid API Key"}}'))
orig_urlopen = app.urllib.request.urlopen
app.urllib.request.urlopen = fake_urlopen
try:
    app._http_json("http://x", {}, "k")
    print("6. FAIL: expected error")
except RuntimeError as e:
    assert "HTTP 403" in str(e) and "Invalid API Key" in str(e), str(e)
    print("6. _http_json raises WITH provider body")
finally:
    app.urllib.request.urlopen = orig_urlopen

# 7. Gemini REST path also surfaces body
app.urllib.request.urlopen = fake_urlopen
try:
    app._gemini_via_rest("k", "gemini-x", "s", "u", 0.4, 100)
    print("7. FAIL: expected error")
except RuntimeError as e:
    assert "Invalid API Key" in str(e), str(e)
    print("7. _gemini_via_rest raises WITH provider body")
finally:
    app.urllib.request.urlopen = orig_urlopen

print("ALL 403-CLASSIFICATION TESTS PASSED")
