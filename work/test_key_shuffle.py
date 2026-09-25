"""v1.3.1: answer keys spread across A-D (the 'puros Letter A' fix)."""
import sys, types, io
from collections import Counter
from pathlib import Path


class _CM:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _Proxy:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __call__(self, *a, **k): return _CM()
    def __getattr__(self, name): return _Proxy()


fake = types.ModuleType("streamlit")


class _SG(dict):
    def __getattr__(self, n): return _Proxy()
    def __setattr__(self, n, v): dict.__setitem__(self, n, v)
    def setdefault(self, k, d=None):
        if k not in self: dict.__setitem__(self, k, d)
        return dict.__getitem__(self, k)
    def pop(self, k, *a): return dict.pop(self, k, *a)


fake.session_state = _SG()
fake.secrets = {}
fake.cache_data = lambda f=None, **k: (f if f else (lambda **kk: None))
fake.__getattr__ = lambda name: _Proxy()
for w in ("selectbox", "radio"):
    setattr(fake, w, lambda *a, **k: (a[1][0] if len(a) > 1 and isinstance(a[1], (list, tuple)) else _Proxy()))
fake.tabs = lambda *a, **k: [_CM() for _ in (a[0] if a and isinstance(a[0], (list, tuple)) else [])]
fake.columns = lambda *a, **k: [_CM() for _ in (range(a[0]) if a and isinstance(a[0], int) else (a[0] if a and isinstance(a[0], (list, tuple)) else [1]))]
for w in ("text_input", "text_area"):
    setattr(fake, w, lambda *a, **k: "")
for w in ("button", "checkbox", "download_button", "form_submit_button"):
    setattr(fake, w, lambda *a, **k: False)
fake.file_uploader = lambda *a, **k: None
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


check("v1.9.0", app._APP_VERSION == "2.0.1")
check("prompt has ANSWER KEY SPREAD rule", "ANSWER KEY SPREAD" in app.make_test_prompt("BASIS", {"items": 10, "test_type": "Examination", "mix": {"lots": 40, "mots": 30, "hots": 30}, "hots_min": 3, "grade": "G9", "area": "Science", "term": "T1"}))


def make_item(n, key="A"):
    return {"number": n, "question": f"Q{n}: topic {n}?", "competency": "C1",
            "variants": [{"question": f"Q{n} v{j}", "choices": {"A": f"alpha {n}{j}", "B": f"beta {n}{j}", "C": f"gamma {n}{j}", "D": f"delta {n}{j}"},
                          "answer": key, "rationale": "r"} for j in range(3)]}


# The user's exact complaint: every key on A
test = {"test_title": "Grade 9 Science Exam", "items": [make_item(i) for i in range(1, 21)]}
before = [[sorted(v["choices"].values()) for v in it["variants"]] for it in test["items"]]
app.balance_answer_keys(test)
after = [[sorted(v["choices"].values()) for v in it["variants"]] for it in test["items"]]
check("choice texts preserved", before == after)
letters = [v["answer"] for it in test["items"] for v in it["variants"]]
check("all four letters used", set(letters) == {"A", "B", "C", "D"}, str(Counter(letters)))
check("near-perfect 25% each", set(Counter(letters).values()) == {15}, str(Counter(letters)))
check("no 3-in-a-row same key", all(not(letters[i] == letters[i+1] == letters[i+2]) for i in range(len(letters)-2)))
check("key maps to real choice", all(v["choices"].get(v["answer"]) for it in test["items"] for v in it["variants"]))
t2 = {"test_title": "Grade 9 Science Exam", "items": [make_item(i) for i in range(1, 21)]}
app.balance_answer_keys(t2)
check("deterministic per title", [v["answer"] for it in t2["items"] for v in it["variants"]] == letters)
t3 = {"test_title": "T3", "items": [make_item(i, "ABCD"[i % 4]) for i in range(1, 13)]}
app.balance_answer_keys(t3)
l3 = [v["answer"] for it in t3["items"] for v in it["variants"]]
check("mixed starting keys also balanced", len(Counter(l3)) == 4 and all(not(l3[i] == l3[i+1] == l3[i+2]) for i in range(len(l3)-2)))
bad = {"test_title": "B", "items": [{"number": 1, "variants": [{"question": "x", "choices": {"A": "1"}, "answer": ""}]}, {"number": 2, "variants": []}]}
app.balance_answer_keys(bad)
check("odd/missing data safe", True)

print("\nALL KEY-SHUFFLE TESTS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
