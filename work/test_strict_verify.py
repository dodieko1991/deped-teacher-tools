"""v1.5.3: STRICT CURRICULUM VERIFICATION RULE — exact text in the prompts,
refusal JSON surfaced as a clean message by the generate functions."""
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


def _selector(*args, **kwargs):
    opts = args[1] if len(args) > 1 and isinstance(args[1], (list, tuple)) else None
    if opts:
        idx = kwargs.get("index", 0) or 0
        return opts[idx] if isinstance(idx, int) and idx < len(opts) else opts[0]
    return _Proxy()


fake.selectbox = _selector
fake.radio = _selector
fake.tabs = lambda *a, **k: [_CM() for _ in (a[0] if a and isinstance(a[0], (list, tuple)) else [])]
fake.columns = lambda *a, **k: [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
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


check("version is 1.9.0", app._APP_VERSION == "2.1.0", app._APP_VERSION)

# --- exact rule text lives in the constant -----------------------------------
rule = app.STRICT_CURRICULUM_VERIFICATION
for phrase in ("STRICT CURRICULUM VERIFICATION RULE",
               "Grade Level + Learning Area + Term + Week",
               "DO NOT invent or infer a topic from general knowledge",
               "Curriculum alignment could not be verified. Please provide the",
               "Do not generate learning objectives, activities, assessments, or",
               "Never fabricate URLs, references, textbook page numbers, or source titles",
               "Teacher-provided resource - verification required"):
    check(f"rule text: {phrase[:42]}", phrase in rule)

# --- wired into all four prompts ---------------------------------------------
details = {"area": "Science", "grade": "Grade 9", "term": "Term 1", "week": "Week 3",
           "title": "T", "teacher": "", "context": "", "sessions": 2, "duration": "60 min",
           "medium": "English", "strategy": app.TEACHING_STRATEGIES[0], "bow": "",
           "note": "", "termweek": "Term 1 · Week 3", "exemplar": "Sample exemplar text."}
ilaw_prompt = app.make_prompt(details)
lil_prompt = app.make_lil_prompt(details)
check("ILAW generation prompt carries the rule", "STRICT CURRICULUM VERIFICATION RULE" in ilaw_prompt)
check("LIL generation prompt carries the rule", "STRICT CURRICULUM VERIFICATION RULE" in lil_prompt)
plan = app._sessions_from_plan({"sessions": [{"session": "Session 1", "topic": "x"}]})
review_prompt = app.make_review_prompt(details, {"sessions": plan})
lil_review = app.make_lil_review_prompt(details, {"sessions": plan})
check("ILAW review prompt carries the rule", "STRICT CURRICULUM VERIFICATION RULE" in review_prompt)
check("LIL review prompt carries the rule", "STRICT CURRICULUM VERIFICATION RULE" in lil_review)

# --- refusal surfaced as a clean error ---------------------------------------
try:
    app._raise_if_curriculum_refusal({"curriculum_verification": "FAILED",
                                      "message": "Curriculum alignment could not be verified. Please provide the corresponding BOW, Lesson Exemplar, or official curriculum source."})
    check("refusal raises", False, "no exception")
except ValueError as exc:
    check("refusal raises ValueError with the agreed message",
          "Curriculum alignment could not be verified" in str(exc), str(exc)[:60])

# normal plans pass through untouched
app._raise_if_curriculum_refusal({"sessions": [{"session": "Session 1"}]})
app._raise_if_curriculum_refusal({"curriculum_verification": "PASSED"})
app._raise_if_curriculum_refusal("not a dict")
check("normal plans pass the guard", True)
try:
    app._raise_if_curriculum_refusal({"curriculum_verification": "FAILED"})  # no message key
    check("refusal without message uses the default text", False, "no exception")
except ValueError as exc:
    check("refusal without message uses the default text",
          "Please provide the corresponding BOW" in str(exc))

# --- generate() stops on refusal (no schema fiddling after) ------------------
refused = {"curriculum_verification": "FAILED", "message": "no source"}


def _refusal_ai(prompt, options=None, tools=False):
    import json
    return json.dumps(refused)


orig_ask = app.ask_ai
app.ask_ai = _refusal_ai
try:
    app.generate("k", {"bow": "", "sessions": 2, "area": "Science", "grade": "9",
                       "term": "1", "week": "3", "strategy": app.TEACHING_STRATEGIES[0],
                       "duration": "60", "medium": "English", "title": "T", "teacher": "",
                       "context": "", "note": ""})
    check("generate stops on refusal", False, "no exception")
except ValueError as exc:
    check("generate stops on refusal", str(exc) == "no source", str(exc))
finally:
    app.ask_ai = orig_ask

print()
if fails:
    print(f"FAILURES ({len(fails)}):", fails)
    sys.exit(1)
print("ALL STRICT-VERIFICATION TESTS PASSED")
