# -*- coding: utf-8 -*-
"""v2.6.0 — real AI-generated pictures in the PowerPoint Generator.

What the teacher asked for:
  * follow the DepEd Tambayan way, where the generator really creates images
  * look at which API keys can generate images, and show ONLY those in the
    dropdown the user picks from
  * if none of the four providers can do it, add another provider for the
    PowerPoint Generator so the slides get genuinely nice pictures

Tested here:
  1. the picture dropdown lists only image-capable engines (Groq/Mistral absent)
  2. the image prompt carries the style preset (or your own words) and "no text"
  3. Gemini, OpenRouter, Pollinations and Together replies all become JPEG bytes
  4. Gemini retries a model with responseModalities when a reply has no image
  5. Auto uses Gemini first when a key exists, then the keyless Pollinations
  6. a failing engine silently falls back, and total failure never crashes
  7. pictures are cached so a retry does not pay twice
  8. the deck uses AI pictures up to the requested count and drawn art after that
  9. the deck prompt asks for a vivid picture description (never text in images)
 10. the PPT tab exposes the engine, style, count and prompt prefix
"""
import base64
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
    st.form = _mk; st.form_submit_button = lambda *a, **k: False
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
    st.button = _mk; st.checkbox = lambda *a, **k: False
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
_tmp = Path(tempfile.mkdtemp(prefix="v260_"))
os.environ["DEPED_BOW_LIBRARY"] = str(_tmp / "empty")
os.environ["DEPED_BOW_CACHE"] = str(_tmp / "cache.json")

import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        fails.append(name)


check("version is 2.6.0", app._APP_VERSION == "2.6.0", app._APP_VERSION)
src = Path(app.__file__).read_text(encoding="utf-8")

# --------------------------------------------------------------------------
# 1. only image-capable engines are offered
# --------------------------------------------------------------------------
names = app.IMAGE_ENGINE_NAMES
joined = " | ".join(names)
check("dropdown lists live image services", all(word in joined for word in ("Gemini image", "OpenRouter", "Pollinations", "Together")), joined[:110])
check("Groq is NOT offered for pictures", "Groq" not in joined)
check("Mistral is NOT offered for pictures", "Mistral" not in joined)
check("a no-AI option is offered", any(e["kind"] == "local" for e in app.IMAGE_ENGINES))
check("every engine declares a kind and a hint", all(e.get("kind") and e.get("hint") for e in app.IMAGE_ENGINES))
check("engines needing a key name it", all(e.get("needs") for e in app.IMAGE_ENGINES if e["kind"] in ("gemini", "openrouter", "together")))
check("keyless engines are marked as such", app.image_engine_key("Pollinations — free, no API key at all") == ""
      and app.image_engine_key(app._LOCAL_IMAGE_ENGINE) == "")

# --------------------------------------------------------------------------
# 2. the image prompt
# --------------------------------------------------------------------------
prompt = app.image_prompt_for("a seed growing in a school garden", style=app._DEFAULT_IMAGE_STYLE)
check("prompt carries the DepEd Tambayan cartoon lead-in", "cartoon vector graphic" in prompt and "Philippine" in prompt, prompt[:70])
check("prompt forbids text inside the picture", "no text" in prompt)
check("prompt keeps the slide description", "seed growing in a school garden" in prompt)
own = app.image_prompt_for("a river", prefix="soft watercolor, pastel palette: ")
check("your own words replace the preset", own.startswith("soft watercolor, pastel palette: ") and "cartoon vector" not in own)
check("every style preset is usable", all(app.IMAGE_STYLE_PRESETS[s].strip() for s in app.IMAGE_STYLE_PRESETS))
check("junk bytes are refused instead of breaking the deck", app._prepare_ai_picture(b"not-an-image") is None)

# --------------------------------------------------------------------------
# 3. fake HTTP layer + real PNG bytes
# --------------------------------------------------------------------------
from PIL import Image  # noqa: E402

_png_buf = io.BytesIO()
Image.effect_noise((240, 150), 60).convert("RGB").save(_png_buf, format="PNG")
PNG = _png_buf.getvalue()
check("test picture is a real PNG", PNG[:8] == b"\x89PNG\r\n\x1a\n" and len(PNG) > 1024, len(PNG))
_pic_prepared = app._prepare_ai_picture(PNG)
check("a real picture is accepted and squared into a JPEG", bool(_pic_prepared) and _pic_prepared[:3] == b"\xff\xd8\xff", len(_pic_prepared or b""))
check("the stored picture fits the deck budget", len(_pic_prepared or b"") <= app._AI_JPEG_BUDGET, len(_pic_prepared or b""))
check("the keyless service's corner logo is trimmed away",
      app._prepare_ai_picture(PNG, trim_bottom=app._POLLINATIONS_LOGO_TRIM) != _pic_prepared)
check("the logo trim is applied to keyless pictures only",
      'trim_bottom=_POLLINATIONS_LOGO_TRIM if kind == "pollinations" else 0.0' in src)

CALLS = {"urls": [], "reply": None}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(request, timeout=None):
    CALLS["urls"].append(getattr(request, "full_url", str(request)))
    reply = CALLS["reply"]
    if isinstance(reply, Exception):
        raise reply
    if callable(reply):
        return _Resp(reply(CALLS["urls"][-1]))
    return _Resp(reply)


app.urllib.request.urlopen = _fake_urlopen


def _gemini_reply(payload):
    return json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png",
                                                                            "data": base64.b64encode(payload).decode()}}]}}]}).encode()


def _reset():
    app.st.session_state.pop("img_cache", None)
    CALLS["urls"] = []


# --------------------------------------------------------------------------
# 4. each provider's reply becomes a picture
# --------------------------------------------------------------------------
_reset()
CALLS["reply"] = _gemini_reply(PNG)
app.st.session_state["provider"], app.st.session_state["api_key"] = "Google Gemini", "gemini-key"
pic, served, err = app.generate_ai_image("life cycle of a plant", engine="Google Gemini image (Nano Banana) — your Gemini key")
check("Gemini picture parsed", bool(pic) and pic[:2] == b"\xff\xd8", f"{served} {err}")
check("Gemini endpoint called with the key", "generativelanguage.googleapis.com" in CALLS["urls"][0] and "gemini-key" in CALLS["urls"][0])

_reset()
CALLS["reply"] = json.dumps({"candidates": [{"content": {"parts": [{"inline_data": {"mime_type": "image/png",
                                                                                  "data": base64.b64encode(PNG).decode()}}]}}]}).encode()
pic2, _, err2 = app.generate_ai_image("water cycle", engine="Google Gemini image (Nano Banana) — your Gemini key")
check("snake_case inline_data parsed too", bool(pic2), err2)

def _capture_urlopen(request, timeout=None):
    """Like _fake_urlopen, but also records the JSON body that was sent."""
    CALLS["urls"].append(getattr(request, "full_url", str(request)))
    try:
        CALLS["last_body"] = json.loads((request.data or b"{}").decode("utf-8"))
    except Exception:
        CALLS["last_body"] = {}
    if isinstance(CALLS["reply"], Exception):
        raise CALLS["reply"]
    if callable(CALLS["reply"]):
        return _Resp(CALLS["reply"](CALLS["urls"][-1], CALLS["last_body"]))
    return _Resp(CALLS["reply"])


_reset()
CALLS["last_body"] = {}


def _two_step(url, body):
    # attempt 1 (bare body) answers with text only; the retry adds responseModalities
    if (body or {}).get("generationConfig", {}).get("responseModalities"):
        return _gemini_reply(PNG)
    return json.dumps({"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}).encode()


app.urllib.request.urlopen = _capture_urlopen
CALLS["reply"] = _two_step
pic3, _, err3 = app.generate_ai_image("volcano", engine="Google Gemini image (Nano Banana) — your Gemini key")
check("a text-only reply is retried and still yields a picture", bool(pic3), f"{len(CALLS['urls'])} call(s) {err3}")
check("the retry asks for IMAGE modality", "responseModalities" in json.dumps(CALLS["last_body"]))
app.urllib.request.urlopen = _fake_urlopen

_reset()
CALLS["reply"] = json.dumps({"created": 1, "data": [{"b64_json": base64.b64encode(PNG).decode(), "media_type": "image/png"}]}).encode()
app.st.session_state["keys"] = {"OpenRouter": "or-key"}
pic4, served4, err4 = app.generate_ai_image("magnet experiment", engine="OpenRouter Image API — your OpenRouter key")
check("OpenRouter picture parsed", bool(pic4), err4)
check("OpenRouter image endpoint used", CALLS["urls"][0].endswith("/api/v1/images"), CALLS["urls"][0])

_reset()
CALLS["reply"] = PNG
pic5, served5, _ = app.generate_ai_image("rainy season", engine="Pollinations — free, no API key at all")
check("keyless Pollinations picture parsed", bool(pic5), served5)
check("Pollinations needs no key in the URL", "key=" not in CALLS["urls"][0] and "image.pollinations.ai/prompt/" in CALLS["urls"][0])

_reset()
CALLS["reply"] = json.dumps({"data": [{"b64_json": base64.b64encode(PNG).decode()}]}).encode()
app.st.session_state["img_keys"] = {"Together AI": "t-key"}
app.urllib.request.urlopen = _capture_urlopen
pic6, _, err6 = app.generate_ai_image("solar system", engine="Together AI — FLUX.1 schnell free endpoint")
check("Together AI picture parsed", bool(pic6) and CALLS["urls"][0].startswith("https://api.together.xyz"), err6)
check("Together uses the free FLUX.1 schnell endpoint", CALLS["last_body"].get("model") == "black-forest-labs/FLUX.1-schnell-Free", CALLS["last_body"].get("model"))
app.urllib.request.urlopen = _fake_urlopen

# --------------------------------------------------------------------------
# 5. Auto order, fallbacks, caching, readiness
# --------------------------------------------------------------------------
app.st.session_state["provider"], app.st.session_state["api_key"] = "Google Gemini", "gemini-key"
chain_with = app._auto_image_engines()
app.st.session_state["provider"], app.st.session_state["api_key"] = "Groq", "groq-key"
chain_without = app._auto_image_engines()
check("Auto tries Gemini first when a Gemini key is set", chain_with and chain_with[0].startswith("Google Gemini"))
check("Auto falls to the keyless service without a Gemini key", chain_without == ["Pollinations — free, no API key at all"], chain_without)

_reset()
app.st.session_state["provider"], app.st.session_state["api_key"] = "Google Gemini", "gemini-key"


def _gemini_down(url, body=None):
    if "generativelanguage" in url:
        raise RuntimeError("quota spent")
    return PNG


CALLS["reply"] = _gemini_down
fallback_pic, fallback_engine, fallback_err = app.generate_ai_image("photosynthesis", engine=app._DEFAULT_IMAGE_ENGINE)
check("a failing engine is replaced by the free one", bool(fallback_pic) and fallback_engine.startswith("Pollinations"), f"{fallback_engine} {fallback_err}")
check("the whole chain really ran", len(CALLS["urls"]) >= 2, len(CALLS["urls"]))

_reset()
app.st.session_state["img_cache"] = {}
CALLS["reply"] = _gemini_reply(PNG)
app.generate_ai_image("same picture", engine="Google Gemini image (Nano Banana) — your Gemini key")
first_calls = len(CALLS["urls"])
app.generate_ai_image("same picture", engine="Google Gemini image (Nano Banana) — your Gemini key")
check("the same picture is cached (no second API call)", len(CALLS["urls"]) == first_calls, f"{first_calls} -> {len(CALLS['urls'])}")

_reset()
CALLS["reply"] = Exception(RuntimeError("everything is down"))
none_pic, none_engine, none_err = app.generate_ai_image("hopeless", engine=app._DEFAULT_IMAGE_ENGINE)
check("total failure returns no picture plus a reason", none_pic is None and none_engine == "" and "down" in none_err, none_err)

app.st.session_state["provider"], app.st.session_state["api_key"] = "Groq", "groq-key"
ready_no_key, msg_no_key = app.image_engine_ready("Google Gemini image (Nano Banana) — your Gemini key")
ready_yes_key, _ = app.image_engine_ready("Pollinations — free, no API key at all")
check("an engine without its key is flagged", ready_no_key is False and "Gemini" in msg_no_key, msg_no_key[:60])
check("the keyless engine is always ready", ready_yes_key is True)
check("Auto and None are always ready", app.image_engine_ready(app._DEFAULT_IMAGE_ENGINE)[0] and app.image_engine_ready(app._LOCAL_IMAGE_ENGINE)[0])

# --------------------------------------------------------------------------
# 6. the deck itself
# --------------------------------------------------------------------------
PLAN = {"deck_title": "Session 1 — Plants", "subject": "Science",
        "theme": {"bg": "F5F9FF", "accent": "2E6FB5", "title": "1A3353", "text": "333333"},
        "slides": [{"title": f"Slide {i}", "bullets": ["one", "two"], "shape": "rect", "image_idea": "a plant in a garden"}
                   for i in range(1, 6)]}

_reset()
app.st.session_state["img_cache"] = {}
deck_local = app.build_presentation(PLAN, "Ma'am Reyes", "Education — friendly classroom look, soft blues and greens",
                                    None, image_engine=app._LOCAL_IMAGE_ENGINE, image_max=4)
stats_local = app.st.session_state["ppt_img_stats"]
check("built-in drawings only when AI is off", deck_local[:2] == b"PK" and stats_local["ai"] == 0 and stats_local["drawn"] == 5, stats_local)

_reset()
app.st.session_state["img_cache"] = {}
_jd_buf = io.BytesIO()
Image.effect_noise((320, 320), 80).convert("RGB").save(_jd_buf, format="JPEG", quality=85)
FAKE_JD = _jd_buf.getvalue()
check("the fake AI picture is a real JPEG", FAKE_JD[:3] == b"\xff\xd8\xff", len(FAKE_JD))


def _fake_generate(description, **kwargs):
    return FAKE_JD, "Google Gemini image (Nano Banana) — your Gemini key", ""


_original_generate = app.generate_ai_image
app.generate_ai_image = _fake_generate
deck_ai = app.build_presentation(PLAN, "Ma'am Reyes", "Nature — earthy greens and browns with organic shapes",
                                 None, image_engine="Google Gemini image (Nano Banana) — your Gemini key",
                                 image_style=app._DEFAULT_IMAGE_STYLE, image_max=3, image_prefix="")
stats_ai = app.st.session_state["ppt_img_stats"]
app.generate_ai_image = _original_generate
check("AI pictures are used for the requested slides", deck_ai[:2] == b"PK" and stats_ai["ai"] == 3, stats_ai)
check("the remaining slides keep drawn pictures", stats_ai["drawn"] == 2, stats_ai)
check("the serving engine is reported", stats_ai["engine"].startswith("Google Gemini"), stats_ai["engine"])

# --------------------------------------------------------------------------
# 7. prompt + UI wiring
# --------------------------------------------------------------------------
_ppt_prompt = app.make_ppt_prompt("LESSON BASIS TEXT", {"slides": 16, "style": "Education", "session_number": 1,
                                                        "session_topic": "Plants", "note": ""})
check("the deck prompt asks for a vivid picture", "VIVID, PICTURE-ONLY" in _ppt_prompt)
check("the deck prompt bans words inside pictures", "never ask for words" in _ppt_prompt.lower() or "Never ask for words" in _ppt_prompt)
check("the old flat-drawing wording is gone", "short description of a simple flat illustration matching the style" not in _ppt_prompt)
check("only image-capable engines are listed in the UI", "Groq and Mistral are text-only" in src)
check("the PPT tab exposes the picture engine", "Picture engine" in src and "Picture style" in src and "AI pictures per deck" in src)
check("the picture count is sent to the deck builder", "image_max=p_img_count" in src and "image_style=p_img_style" in src)
check("a picture test button exists", "Test the picture engine" in src)
check("how a picture was made is reported to the teacher", "AI picture(s) drawn by" in src)
check("Groq/Mistral still work for text (provider hub untouched)", set(app.PROVIDERS) == {"Google Gemini", "OpenRouter", "Groq", "Mistral"})

print()
print(f"{len(fails)} failure(s)" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
