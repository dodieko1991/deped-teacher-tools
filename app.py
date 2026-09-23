import ast
import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

_APP_VERSION = "1.8.0"  # bump this when shipping new updates
from copy import copy
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from openpyxl import Workbook, load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Font
from pypdf import PdfReader

try:  # python-pptx powers the PowerPoint tab; optional so the rest of the app still runs
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches as PptxInches, Pt as PptxPt
except ImportError:  # pragma: no cover - handled gracefully in the PowerPoint tab
    Presentation = None

try:  # Pillow draws the real slide pictures; optional — decks fall back to flat shapes
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFilter as _PILFilter
except ImportError:  # pragma: no cover
    _PILImage = None


class GenaiUnavailableError(ImportError):
    """Raised when the optional google-genai package is not installed."""


try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

    class types:  # noqa: N801 - mirrors the google.genai namespace
        class GenerateContentConfig:
            def __init__(self, *args, **kwargs):
                raise GenaiUnavailableError(
                    "The google-genai package is not installed. Run ILAW_TeacherTools_Setup.bat to repair the installation."
                )

        class Tool:
            def __init__(self, *args, **kwargs):
                raise GenaiUnavailableError(
                    "The google-genai package is not installed. Run ILAW_TeacherTools_Setup.bat to repair the installation."
                )

        class GoogleSearch:
            def __init__(self, *args, **kwargs):
                raise GenaiUnavailableError(
                    "The google-genai package is not installed. Run ILAW_TeacherTools_Setup.bat to repair the installation."
                )


from streamlit.errors import StreamlitSecretNotFoundError

st.set_page_config(page_title="DepEd Teacher Tools Generator", page_icon="📚", layout="wide")
TEMPLATE = Path(__file__).with_name("SAMPLE ILAW FORMAT_WIDE.xlsx")
LIL_TEMPLATE = Path(__file__).with_name("LESSON IMPLEMENTATION LOG TEMPLATE.xlsx")
FEEDBACK_FILE = Path(__file__).with_name("feedback.xlsx")
FEEDBACK_OVERFLOW_FILE = Path(__file__).with_name("feedback_overflow.xlsx")
FEEDBACK_HOOK_FILE = Path(__file__).with_name("feedback_webhook.txt")
_FEEDBACK_WEBHOOK_URL = ""  # optional: Apps Script Web App URL (overrides the Google Form below)
_FEEDBACK_FORM_ID = "1FAIpQLSfDF3n__z-3qqpLYkukDdYeFwSU7ukaShTD2yREXJ7UDryWyA"  # owner's Google Form
_FEEDBACK_FORM_ENTRIES = {  # question entry IDs of the owner's Google Form
    "name": "entry.636003454",
    "rating": "entry.2071256194",
    "feedback": "entry.1408890773",
    "suggestions": "entry.351196024",
}


def feedback_hook_url():
    """Resolve the Google Sheet webhook with no user input: app.py constant, then
    feedback_webhook.txt (owner pastes the URL there once), then an env var."""
    candidates = [_FEEDBACK_WEBHOOK_URL]
    try:
        if FEEDBACK_HOOK_FILE.exists():
            for line in FEEDBACK_HOOK_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    candidates.append(line)
    except OSError:
        pass
    candidates.append(os.getenv("FEEDBACK_WEBHOOK_URL", ""))
    for url in candidates:
        if str(url or "").strip().startswith("http"):
            return str(url).strip()
    return ""


def _append_feedback_row(target, row):
    """Append one row into an xlsx, creating the file when missing.

    A corrupt/unreadable file (e.g. Excel crashed mid-write and left a 0-byte or
    half-saved file) is renamed to .bad and the row starts a fresh file — the
    broken copy is kept for manual recovery instead of blocking new feedback.
    """
    if target.exists():
        try:
            workbook = load_workbook(target)
        except Exception:
            try:
                target.rename(target.with_suffix(".xlsx.bad"))
            except OSError:
                pass
            workbook = None
    else:
        workbook = None
    if workbook is None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Feedback"
        sheet.append(["Submitted at", "Name", "Rating", "Feedback", "Suggestions"])
    else:
        sheet = workbook.active
    sheet.append(row)
    workbook.save(target)


def overflow_hint(status):
    """Friendly tail for the success message when the main xlsx was locked."""
    if "overflow" in status:
        return " Close the feedback.xlsx in Excel — new rows are landing in feedback_overflow.xlsx meanwhile."
    return ""


def save_feedback(name, rating, feedback, suggestions):
    """Insert one feedback row into the local feedback.xlsx (existing rows are never
    edited), then insert the same row into the owner's Google Sheet via the Google
    Form (or an Apps Script webhook when configured). Returns 'synced', 'local-only',
    or 'sync-failed: <reason>'.

    The local save is resilient: when Windows has locked feedback.xlsx (the owner
    currently has it open in Excel), the row goes to feedback_overflow.xlsx instead
    and the message reports the overflow so no feedback is ever lost.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [stamp, (name or "Anonymous").strip(), rating, (feedback or "").strip(), (suggestions or "").strip()]
    try:
        _append_feedback_row(FEEDBACK_FILE, row)
        overflow_note = ""
    except PermissionError:
        _append_feedback_row(FEEDBACK_OVERFLOW_FILE, row)
        overflow_note = " (main file was open in Excel — row saved to feedback_overflow.xlsx)"
    except OSError as exc:
        # Any other local-write failure must not stop the Google Form send.
        overflow_note = f" (local save skipped: {exc})"
    hook = feedback_hook_url()
    if not hook:
        # No Apps Script webhook configured: submit to the owner's Google Form instead.
        # Google Forms accept anonymous posts, so this works with zero setup for every user.
        form_url = f"https://docs.google.com/forms/d/e/{_FEEDBACK_FORM_ID}/formResponse"
        star_count = max(1, str(rating or "").count("⭐")) or 5
        fields = {
            _FEEDBACK_FORM_ENTRIES["name"]: (name or "Anonymous").strip(),
            _FEEDBACK_FORM_ENTRIES["rating"]: str(star_count),
            _FEEDBACK_FORM_ENTRIES["feedback"]: (feedback or "").strip(),
            _FEEDBACK_FORM_ENTRIES["suggestions"]: (suggestions or "").strip(),
        }
        try:
            request = urllib.request.Request(
                form_url, data=urllib.parse.urlencode(fields).encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": _HTTP_UA},
                method="POST")
            urllib.request.urlopen(request, timeout=15).read()
            return "synced" + overflow_note
        except Exception as exc:
            return f"sync-failed: {exc}{overflow_note}"
    try:
        payload = json.dumps({"name": name, "rating": rating, "feedback": feedback, "suggestions": suggestions, "submitted_at": stamp}).encode("utf-8")
        request = urllib.request.Request(hook, data=payload, headers={"Content-Type": "application/json", "User-Agent": _HTTP_UA}, method="POST")
        urllib.request.urlopen(request, timeout=15).read()
        return "synced" + overflow_note
    except Exception as exc:
        return f"sync-failed: {exc}{overflow_note}"
TEACHING_STRATEGIES = [
    "4As Model — Activity, Analysis, Abstraction, Application",
    "4Es Model — Engage, Explore, Explain, Elaborate",
    "5Es Model — Engage, Explore, Explain, Elaborate, Evaluate",
    "7Es Model — Elicit, Engage, Explore, Explain, Elaborate, Evaluate, Extend",
    "5Ps Model — Preparation, Presentation, Practice, Production, Performance",
    "I Do–We Do–You Do — teacher modeling → guided practice → independent practice",
    "Direct Instruction — structured teacher-led instruction",
    "Inquiry-Based Learning — question → investigation → evidence → conclusion",
    "Problem-Based Learning (PBL) — learning organized around a problem",
    "Project-Based Learning — learning through an extended project/product",
    "Experiential Learning Cycle — experience → reflection → conceptualization → experimentation",
    "Discovery Learning — learners discover concepts through exploration",
    "Cooperative Learning — structured collaborative/group learning",
]

SCHEMA = {
    "lesson_title": "string", "overview": "string", "standards_and_competency": "Exact BOW competency, with code when supplied",
    "teacher_notes": ["string"],
    "sessions": [{
        "session": "Session 1", "topic": "one topic string",
        "learning_objectives": "one string; each objective on its own '- ' line",
        "pre_lesson": "one string; readiness/retrieval/motivation only",
        "flow": "one string; in-class sequence; each strategy-model phase on its own line as 'Phase: full-sentence paragraph'",
        "learning_resources": "one string listing real teaching resources, one per '- ' line, ending with the session reference in 'Book Title, Author, Page N' or 'Website Name, URL: link' form",
        "integration": "one string; or N/A",
        "formative_assessment": "one string; check of learning only",
        "extended_learning": "one string; outside-class extension only",
        "reflection": "one string; teacher reflection prompt only",
    }],
}


SOLO_LEVELS = ["Unistructural", "Multistructural", "Relational", "Extended Abstract"]
COGNITIVE_LEVELS = ["Remembering", "Understanding", "Applying", "Analyzing", "Evaluating", "Creating"]
TIER_LEVELS = {"LOTS": ("Remembering", "Understanding"), "MOTS": ("Applying", "Analyzing"), "HOTS": ("Evaluating", "Creating")}
BASIS_TOPIC = "Topic or competency"
BASIS_ILAW = "Uploaded ILAW lesson plan (Excel)"
TEST_MIXES = {
    "LOTS 40% · MOTS 30% · HOTS 30% (DepEd balanced)": {"lots": 40, "mots": 30, "hots": 30},
    "Balanced (LOTS 50% · MOTS 25% · HOTS 25%)": {"lots": 50, "mots": 25, "hots": 25},
    "HOTS emphasis (LOTS 30% · MOTS 30% · HOTS 40%)": {"lots": 30, "mots": 30, "hots": 40},
    "Mostly HOTS (LOTS 20% · MOTS 30% · HOTS 50%)": {"lots": 20, "mots": 30, "hots": 50},
}
TEST_SCHEMA = {
    "test_title": "string",
    "instructions": "one short paragraph of learner instructions",
    "competencies": [{"statement": "exact competency or objective text from the test basis; never invent codes", "days": "integer teaching days allotted to this competency by the official DepEd pacing; use the TEACHING DAYS RESEARCH NOTE; never invent"}],
    "items": [{
        "number": 1, "competency": "exact statement from competencies",
        "variants": [{
            "question": "string",
            "choices": {"A": "string", "B": "string", "C": "string", "D": "string"},
            "answer": "A|B|C|D", "solo_level": "Unistructural|Multistructural|Relational|Extended Abstract",
            "cognitive_level": "Remembering|Understanding|Applying|Analyzing|Evaluating|Creating",
            "rationale": "one sentence explaining the key",
        }, "same shape as above", "same shape as above"],
    }],
}


PLAN_TOP_FIELDS = [("lesson_title", "Lesson title"), ("overview", "Overview"), ("standards_and_competency", "Standards and competency")]
PLAN_SESSION_FIELDS = [
    ("topic", "Topic"),
    ("learning_objectives", "Learning objectives (one per line)"),
    ("pre_lesson", "Pre-lesson"),
    ("flow", "Flow"),
    ("learning_resources", "Learning resources"),
    ("integration", "Integration"),
    ("formative_assessment", "Formative assessment"),
    ("extended_learning", "Extended learning"),
    ("reflection", "Reflection"),
]

EDITABLE_SESSION_FIELDS = [key for key, _ in PLAN_SESSION_FIELDS]


def field_to_text(value):
    """Render a plan field as editable text."""
    if isinstance(value, list):
        return "\n".join(f"- {str(item).lstrip('-• ').strip()}" for item in value)
    return "" if value is None else str(value)


def text_to_field(text, field):
    """Convert edited text back into the plan's stored shape."""
    if field == "learning_objectives":
        return [line.strip().lstrip("-• ").strip() for line in text.splitlines() if line.strip()]
    return text.strip()


def regenerate_field(api_key, plan, details, session_index, field, instruction):
    """[LEGACY v1.0 helper] Rewrite one field. Kept so old callers never break."""
    if session_index >= 0:
        session = plan.get("sessions", [])[session_index]
        current = session.get(field, "")
        scope = session.get("session", f"Session {session_index + 1}")
        context = {key: field_to_text(value) for key, value in session.items() if key != field}
    else:
        current = plan.get(field, "")
        scope = "the plan-level section"
        context = {key: field_to_text(value) for key, value in plan.items() if key not in ("sessions", field)}
    prompt = f"""You are an expert Philippine DepEd teacher refining an ILAW lesson plan.
Rewrite ONLY the "{field}" part of {scope}. Every other part must remain unchanged.
Teacher instruction (what to change or improve): {instruction or "Improve this part - make it more specific, engaging, and age-appropriate while staying aligned with the rest of the plan."}
Keep this part strictly in its ILAW role: {field} must contain only what its name describes.
Stay consistent with the context below and the learning area ({details.get('area', '')}, {details.get('grade', '')}).
For learning_objectives, return one objective per line starting with "- ". Otherwise return plain text.
OTHER PARTS (context only - do not rewrite them):
{json.dumps(context, ensure_ascii=False)}
CURRENT "{field}":
{field_to_text(current)}
Respond ONLY with valid JSON: {{"value": "the rewritten field"}}
"""
    data = _ask_and_parse(prompt, {"response_mime_type": "application/json", "temperature": 0.5})
    return text_to_field(str(data.get("value", "")), field)


def _normalize_option(value, field):
    """Turn one raw option for a field into display/export text."""
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value)
    return "" if value is None else str(value).strip()


def _ensure_single_text(raw, field, fallback=""):
    """Collapse one field's value to a single text string, however the model shaped it.

    The schema asks for one string per cell; if a model still returns a list of
    alternatives (or a dict), the FIRST entry is kept — the old option-1 default."""
    if isinstance(raw, dict):
        raw = list(raw.values())
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    text = _normalize_option(raw, field).strip()
    return text or fallback


def first_option(value, fallback=""):
    """Safely read the first AI option whether the field is a list or a plain string."""
    if isinstance(value, list):
        return str(value[0]).strip() if value else fallback
    return fallback if value is None else str(value).strip()


def _ensure_three_options(raw, field, fallback=""):  # [LEGACY] kept for old session state
    """Guarantee exactly 3 option strings for a plan cell, however the model shaped it."""
    if isinstance(raw, dict):
        raw = list(raw.values())
    options = [_normalize_option(item, field) for item in raw] if isinstance(raw, list) else []
    options = [item for item in options if item]
    if not options:
        options = [fallback or "N/A"]
    while len(options) < 3:
        options.append(options[-1])
    return options[:3]


# ---------------------------------------------------------------------------
# AI PROVIDER HUB - Gemini, OpenRouter, Groq, and Mistral behind one interface.
# Every provider returns plain text, so all features (lesson plan, test paper,
# TOS, answer key, per-cell regeneration) work identically on whichever
# provider the teacher chooses. Each provider has its own fallback model chain:
# when the chosen model is unavailable (404) or out of quota (429/402), the app
# automatically retries the provider's other models with the same request.
# ---------------------------------------------------------------------------
PROVIDERS = {
    "Google Gemini": {
        "sdk": "gemini",
        "key_label": "Google AI API key",
        "key_url": "https://aistudio.google.com/apikey",
        "key_hint": "Free at Google AI Studio: aistudio.google.com/apikey",
        "models": {
            "Auto pick (recommended - skips busy models)": "auto",
            "Fast: gemini-3.6-flash": "gemini-3.6-flash",
            "Fast: gemini-2.5-flash": "gemini-2.5-flash",
            "Fast: gemini-flash-latest": "gemini-flash-latest",
            "Light: gemini-flash-lite-latest": "gemini-flash-lite-latest",
            "Quality: gemini-3.6-pro (slower, has free quota)": "gemini-3.6-pro",
            "Quality: gemini-2.5-pro (slower)": "gemini-2.5-pro",
        },
        "fallback": ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.6-pro"],
    },
    "OpenRouter": {
        "sdk": "openai",
        "base_url": "https://openrouter.ai/api/v1/",
        "max_output_ceiling": 20480,
        "key_label": "OpenRouter API key",
        "key_url": "https://openrouter.ai/keys",
        "key_hint": "Free models included: openrouter.ai/models?max_price=0",
        "models": {
            "Auto pick (recommended - skips busy models)": "auto",
            "Light & fast: qwen/qwen3.8-27b (free)": "qwen/qwen3.8-27b:free",
            "Light & fast: z-ai/glm-5.2 (free)": "z-ai/glm-5.2:free",
            "Fast: google/gemini-2.5-flash": "google/gemini-2.5-flash",
            "Quality: google/gemini-2.5-pro": "google/gemini-2.5-pro",
            "Fast: deepseek/deepseek-chat-v3.1": "deepseek/deepseek-chat-v3.1",
            "Quality: deepseek/deepseek-r1 (reasoning, slower)": "deepseek/deepseek-r1",
        },
        "fallback": ["qwen/qwen3.8-27b:free", "google/gemini-2.5-flash", "deepseek/deepseek-chat-v3.1", "z-ai/glm-5.2:free"],
    },
    "Groq": {
        "sdk": "openai",
        "base_url": "https://api.groq.com/openai/v1/",
        "key_label": "Groq API key",
        "key_url": "https://console.groq.com/keys",
        "key_hint": "Free key at console.groq.com - very fast responses",
        "models": {
            "Auto pick (recommended - skips busy models)": "auto",
            "Fast: openai/gpt-oss-120b": "openai/gpt-oss-120b",
            "Light & fast: openai/gpt-oss-20b": "openai/gpt-oss-20b",
            "Fast: qwen/qwen3.8-27b": "qwen/qwen3.8-27b",
            "Agentic: groq/compound-mini": "groq/compound-mini",
            "Agentic: groq/compound": "groq/compound",
        },
        "fallback": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b", "groq/compound-mini", "groq/compound"],
    },
    "Mistral": {
        "sdk": "openai",
        "base_url": "https://api.mistral.ai/v1/",
        "key_label": "Mistral API key",
        "key_url": "https://console.mistral.ai/api-keys/",
        "key_hint": "Free tier available at console.mistral.ai",
        "models": {
            "Auto pick (recommended - skips busy models)": "auto",
            "Fast: mistral-large-latest (quality)": "mistral-large-latest",
            "Fast: mistral-small-latest (balanced)": "mistral-small-latest",
            "Light & fast: magistral-small-latest": "magistral-small-latest",
            "Fast: ministral-8b-latest (light)": "ministral-8b-latest",
            "Quality: pixtral-large-latest": "pixtral-large-latest",
        },
        "fallback": ["mistral-small-latest", "mistral-large-latest", "magistral-small-latest", "ministral-8b-latest"],
    },
}
_DEFAULT_PROVIDER = "Google Gemini"
_PROVIDER_FALLBACK = {name: cfg["fallback"] for name, cfg in PROVIDERS.items()}
_HTTP_UA = "DepEdTeacherTools/1.0"  # custom UA: Cloudflare (Groq) blocks the default Python-urllib signature with error 1010

# Known context windows (input + output, tokens) per model id — used to clamp the
# output budget and skip models that cannot fit the request at all.
_MODEL_CONTEXT = {
    # OpenRouter
    "qwen/qwen3.8-27b:free": 262144,
    "z-ai/glm-5.2:free": 32768,
    "google/gemini-2.5-flash": 1048576,
    "google/gemini-2.5-pro": 1048576,
    "deepseek/deepseek-chat-v3.1": 163840,
    "deepseek/deepseek-r1": 163840,
    # Groq
    "openai/gpt-oss-120b": 131072,
    "openai/gpt-oss-20b": 131072,
    "qwen/qwen3.8-27b": 131072,
    "groq/compound-mini": 131072,
    "groq/compound": 131072,
    # Mistral
    "mistral-small-latest": 131072,
    "mistral-large-latest": 131072,
    "magistral-small-latest": 131072,
    "ministral-8b-latest": 131072,
    # Gemini
    "gemini-2.5-flash": 1048576,
    "gemini-3.6-flash": 1048576,
    "gemini-flash-latest": 1048576,
    "gemini-flash-lite-latest": 1048576,
}


def initial_api_key():
    try:
        return st.secrets["GOOGLE_API_KEY"]
    except (KeyError, StreamlitSecretNotFoundError):
        return os.getenv("GOOGLE_API_KEY", "")


def _extract_json_text(raw):
    """Pull clean JSON out of a model answer (handles ```json fences and chatter)."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start >= 0:
        closer = text[start]
        depth = 0
        in_str = False
        esc = False
        for index in range(start, len(text)):
            ch = text[index]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        return text[start:]
    raise ValueError("The model did not return valid JSON. Try again, or pick another model/provider in the sidebar.")


def _parse_json_lenient(text):
    """json.loads that tolerates raw control characters, trailing commas, and
    single-quoted strings — the three most common model JSON slips."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    # Last resort 1: escape raw control characters inside strings, then retry.
    fixed = []
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
                fixed.append(ch)
            elif ch == "\\":
                esc = True
                fixed.append(ch)
            elif ch == '"':
                in_str = False
                fixed.append(ch)
            elif ord(ch) < 0x20:
                if ch == "\n":
                    fixed.append("\\n")
                elif ch == "\t":
                    fixed.append("\\t")
                elif ch == "\r":
                    fixed.append("\\r")
                # other control chars are dropped
            else:
                fixed.append(ch)
        else:
            if ch == '"':
                in_str = True
            fixed.append(ch)
    repaired = "".join(fixed)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    # Last resort 2: trailing commas / single-quoted strings (Mistral slips).
    # Python literals accept both, so eval the structure safely via ast.literal_eval.
    py = re.sub(r",(\s*[}\]])", r"\1", repaired)  # drop trailing commas
    try:
        return ast.literal_eval(py)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        py = py.replace("'", '"')
        py = re.sub(r",(\s*[}\]])", r"\1", py)
        try:
            return ast.literal_eval(py)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            raise ValueError("The model's JSON could not be repaired automatically. Try Generate again, or pick another model/provider in the sidebar.")


def _ask_and_parse(prompt, options=None, tools=False):
    """ask_ai + JSON extraction, with ONE automatic regeneration retry.

    Mistral (and some OpenRouter hosts) occasionally return JSON so malformed
    that even the lenient repairer cannot fix it. A single clean retry — asking
    the model to re-emit strict JSON — rescues most of those, so the teacher no
    longer has to press Generate again by hand.
    """
    opts = dict(options or {})
    answer = ask_ai(prompt, opts, tools)
    try:
        return _parse_json_lenient(_extract_json_text(answer))
    except (ValueError, SyntaxError) as exc:
        retry_opts = dict(opts)
        retry_opts["temperature"] = min(retry_opts.get("temperature", 0.4), 0.2)
        retry_prompt = (prompt + "\n\nIMPORTANT: your previous reply was not valid JSON and could not "
                        "be repaired. Return ONLY one valid JSON value exactly matching the requested "
                        "schema — no markdown fences, no commentary, no trailing commas — and escape "
                        "every newline inside JSON strings.")
        try:
            answer2 = ask_ai(retry_prompt, retry_opts, tools)
            return _parse_json_lenient(_extract_json_text(answer2))
        except (ValueError, SyntaxError):
            raise ValueError(
                "The model's JSON could not be repaired automatically (one automatic retry already "
                "failed). Press Generate to try again, or pick another model/provider in the sidebar."
            ) from exc


def _raise_if_curriculum_refusal(data):
    """Surface the strict-verification refusal as a clean, actionable error.

    When the model answers the STRICT CURRICULUM VERIFICATION RULE with the
    agreed refusal JSON, stop the generation here — the teacher sees exactly
    what to upload next instead of a schema/JSON error.
    """
    if isinstance(data, dict) and str(data.get("curriculum_verification", "")).upper() == "FAILED":
        raise ValueError(str(data.get("message") or (
            "Curriculum alignment could not be verified. Please provide the "
            "corresponding BOW, Lesson Exemplar, or official curriculum source.")))


def _raise_http_with_body(exc):
    """Re-raise an HTTPError including the provider's own error message body."""
    try:
        body = exc.read().decode("utf-8", "replace")[:400]
    except Exception:
        body = ""
    raise RuntimeError(f"HTTP {exc.code} from provider: {body or exc.reason}") from exc


def _http_json(url, payload, key, timeout=240):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": _HTTP_UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _raise_http_with_body(exc)


def _openai_chat(provider, key, model, system, user, temperature, max_tokens):
    cfg = PROVIDERS[provider]
    if provider == "OpenRouter":
        payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": temperature, "max_tokens": max_tokens}
    else:
        payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": temperature, "max_tokens": max_tokens}
    data = _http_json(cfg["base_url"] + "chat/completions", payload, key)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        message_text = json.dumps(data)[:400]
        raise RuntimeError(f"Unexpected reply from {provider}: {message_text}")


def _gemini_via_rest(key, model, system, user, temperature, max_tokens, tools=False):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if tools:
        body["tools"] = [{"googleSearch": {}}]
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={urllib.parse.quote(key)}")
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "User-Agent": _HTTP_UA}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        _raise_http_with_body(exc)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"] or ""
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected reply from Gemini: {json.dumps(data)[:400]}")


def _gemini_sources_rest(raw_data):
    sources, seen = [], set()
    for candidate in (raw_data or {}).get("candidates", []):
        for chunk in ((candidate.get("groundingMetadata") or {}).get("groundingChunks") or []):
            web = chunk.get("web") or {}
            url = web.get("uri")
            if url and url not in seen:
                seen.add(url)
                sources.append({"title": web.get("title") or "Online source", "url": url})
                if len(sources) == 4:
                    return sources
    return sources


def call_gemini(client, contents, config):
    """Legacy helper kept so old call sites keep working: ask the active provider."""
    wants_json = bool(getattr(config, "response_mime_type", None) if not isinstance(config, dict) else config.get("response_mime_type"))
    return ask_ai(contents, {"response_mime_type": "application/json"} if wants_json else {})


def _parse_int(token):
    return int(token.replace(",", ""))


def _context_retry_budget(message, current_max):
    """Detect a provider 'maximum context length' (HTTP 400) error and compute an
    output-token budget that fits the model's window. Returns None when the
    message is not a context error or nothing useful fits (caller should try
    the next model instead of retrying)."""
    msg = message.lower()
    if not ("context length" in msg or "too many tokens" in msg or "context window" in msg):
        return None
    m = re.search(r"maximum context length[^\d]*(\d[\d,]*)", msg)
    in_m = re.search(r"(\d[\d,]*) of (the )?text input", msg)
    if m:
        ctx = _parse_int(m.group(1))
        in_tok = _parse_int(in_m.group(1)) if in_m else 4096
        fit = ctx - in_tok - 1024
    else:
        fit = current_max // 2
    return fit if fit >= 4096 else None


def ask_ai(prompt, options=None, tools=False):
    """One entry point for every AI feature on every provider.

    Uses the provider/key/model chosen in the sidebar. When the chosen model is
    unavailable or its quota is spent, the provider's other models are tried
    automatically with the same request, so a generation almost never dies just
    because one model is busy.
    """
    options = options or {}
    provider_name = st.session_state.get("provider", _DEFAULT_PROVIDER)
    cfg = PROVIDERS.get(provider_name, PROVIDERS[_DEFAULT_PROVIDER])
    key = (st.session_state.get("api_key") or "").strip()
    if not key:
        raise RuntimeError(f"Add your {cfg['key_label']} in the sidebar first.")
    chosen = st.session_state.get("model_choice", "Auto pick (recommended - skips busy models)")
    chosen_model = cfg["models"].get(chosen, "auto")
    fallback = _PROVIDER_FALLBACK.get(provider_name, [])
    if cfg["sdk"] == "gemini":
        if chosen_model == "auto":
            candidates = fallback
        else:
            candidates = [chosen_model] + [m for m in fallback if m != chosen_model]
    else:
        candidates = fallback if chosen_model == "auto" else [chosen_model] + [m for m in fallback if m != chosen_model]
    temperature = options.get("temperature", 0.4)
    max_tokens = options.get("max_output_tokens", 16384)
    ceiling = cfg.get("max_output_ceiling")
    if ceiling:
        max_tokens = min(max_tokens, ceiling)
    if options.get("response_mime_type") == "application/json":
        system = ("You are an expert Philippine DepEd teacher assistant. You ALWAYS reply with a single "
                  "valid JSON value and absolutely no markdown fences, commentary, or extra text.")
    else:
        system = "You are an expert Philippine DepEd teacher assistant doing careful, verifiable research."
    errors = []
    saw_quota = False
    saw_forbidden = False

    def _do_call(model, budget):
        if cfg["sdk"] == "gemini":
            if genai is not None:
                client = genai.Client(api_key=key)
                gen_cfg = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    max_output_tokens=budget,
                    **({"tools": [types.Tool(google_search=types.GoogleSearch())]} if tools else {}),
                )
                response = client.models.generate_content(model=model, contents=prompt, config=gen_cfg)
                if tools:
                    try:
                        st.session_state["last_grounding"] = response
                    except Exception:
                        pass
                return response.text or ""
            return _gemini_via_rest(key, model, system, prompt, temperature, budget, tools)
        return _openai_chat(provider_name, key, model, system, prompt, temperature, budget)

    est_in = max(512, len(prompt) // 3)  # rough prompt token estimate for context checks
    for model in candidates:
        budget = max_tokens
        ctx = _MODEL_CONTEXT.get(model)
        if ctx:
            feasible = ctx - est_in - 1024
            if feasible < 4096:
                errors.append(f"{model}: context window ({ctx:,} tokens) too small for this prompt (~{est_in:,} input tokens)")
                continue
            budget = min(max_tokens, feasible)
        retried_ctx = False
        retried_402 = False
        upstream_retries = 0
        while True:
            try:
                text = _do_call(model, budget)
                try:
                    st.session_state["model_used"] = f"{provider_name} · {model}"
                except Exception:
                    pass
                return text
            except Exception as exc:
                message = str(exc)
                msg_low = message.lower()
                fit = _context_retry_budget(message, budget)
                if fit is not None and fit < budget and not retried_ctx:
                    retried_ctx = True
                    errors.append(f"{model}: context limit — retrying with {fit} output tokens")
                    budget = fit
                    continue
                afford = re.search(r"can only afford (\d[\d,]*)", message)
                if afford and "402" in message and not retried_402:
                    fit402 = _parse_int(afford.group(1)) - 512
                    if fit402 >= 4096:
                        retried_402 = True
                        errors.append(f"{model}: key credits allow ~{afford.group(1)} output tokens — retrying with {fit402:,}")
                        budget = fit402
                        continue
                if "temporarily rate-limited upstream" in msg_low and upstream_retries < 2:
                    upstream_retries += 1
                    errors.append(f"{model}: upstream busy — waiting 20 s, retry {upstream_retries}/2")
                    time.sleep(20)
                    continue
                errors.append(f"{model}: {message[:180]}")
                if "context length" in msg_low or "too many tokens" in msg_low or "context window" in msg_low:
                    break  # this model's window is too small for the request; try the next model
                if "404" in message or "NOT_FOUND" in message or "no longer available" in msg_low or "does not exist" in msg_low or "decommissioned" in msg_low:
                    break
                if "429" in message or "RESOURCE_EXHAUSTED" in message or "rate limit" in msg_low or "quota" in msg_low or "402" in message or "token budget" in msg_low:
                    saw_quota = True
                    break
                if "403" in message or "forbidden" in msg_low or "401" in message or "invalid api key" in msg_low or "unauthorized" in msg_low or "permission denied" in msg_low:
                    saw_forbidden = True
                    break
                raise
    if saw_quota:
        raise RuntimeError(
            f"Every {provider_name} model available to this key returned quota or rate-limit errors. "
            "Free tiers are limited per minute and per day, and each provider has its own separate quota. "
            "Options: (1) wait a minute if you sent several requests quickly; (2) wait until tomorrow for "
            "the daily free quota; (3) switch to another provider in the sidebar and use its key — or "
            "(4) enable pay-as-you-go on this provider. "
            f"Details: {' | '.join(errors)}"
        )
    if saw_forbidden:
        raise RuntimeError(
            f"{provider_name} refused every request from this key (403 Forbidden / 401 Unauthorized). "
            "This is a key or account problem, NOT a quota one. Common causes: the key was copied "
            "incompletely or has since been deleted, the provider account still needs email/phone "
            "verification, or the provider does not serve your region yet. Create a fresh key on the "
            "provider's website (sidebar guide link) or switch provider in the sidebar. "
            f"Details: {' | '.join(errors)}"
        )
    raise RuntimeError(
        f"None of the {provider_name} models could serve this request. Check your key and internet "
        f"connection, or switch provider in the sidebar. Details: {' | '.join(errors)}"
    )


def read_any_document(uploaded_file):
    """Read PDF, Word, or Excel uploads into one text block for AI grounding."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(uploaded_file)
    if suffix in (".docx",):
        document = Document(BytesIO(uploaded_file.getvalue()))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        text = "\n".join(parts)
        if not text.strip():
            raise ValueError("No readable text was found in this Word file.")
        return text[:60000]
    if suffix in (".doc",):
        raise ValueError("Please save the file as .docx (Word 2007+) and upload again — old .doc files cannot be read.")
    return read_ilaw_excel(uploaded_file)


def extract_pdf_text(uploaded_file):
    reader = PdfReader(BytesIO(uploaded_file.getvalue()))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise ValueError("No readable text was found. Use a text-based PDF, not a scanned image PDF.")
    return text[:60000]


# ---------------------------------------------------------------------------
# DepEd Budget of Work (BOW) parsing — the official Three-Term BOW layout is
# consistent across subjects: 'First/Second/Third Term' sections, each with a
# bulleted Content Standard, a Performance Standard, week rows ('1 to 3' →
# lesson title → bulleted learning competencies) and a 'Suggested Activities'
# list. PDF extraction often emits one word per line; everything is normalized
# before parsing so the same parser works on PDF, Word, and Excel BOWs.
# ---------------------------------------------------------------------------
_BOW_BULLET = r"[●•▪◦]"
_BOW_WEEK_ROW_RE = re.compile(r"\b(\d{1,2})\s*to\s*(\d{1,2})\b")
_BOW_TERM_MARKERS = (("Term 1", r"\bFirst\s+Term\b"), ("Term 2", r"\bSecond\s+Term\b"), ("Term 3", r"\bThird\s+Term\b"))
_KNOWN_AREAS = ("Araling Panlipunan", "Edukasyon sa Pagpapakatao", "Edukasyong Pantahanan at Pangkabuhayan",
                "Technology and Livelihood Education", "Mathematics", "Science", "English", "Filipino",
                "Physical Education", "Health", "Music", "Arts", "MAPEH", "TLE")


def _clean_bow_phrase(text):
    """Tidy one parsed BOW phrase: collapse whitespace, strip stray bullets/dashes."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    text = re.sub(r"^[-–—\s]+", "", text)
    text = re.sub(r"Page\s+\d+\s+of\s+\d+.*$", "", text)
    return text.strip(" -–—|").strip()


def parse_bow(raw_text):
    """Parse an official DepEd Three-Term Budget of Work into structured terms.

    Returns a list of {term, content_standards, performance_standard, weeks,
    suggested_activities}; weeks rows carry {weeks, from, to, lesson,
    competencies}. Returns [] when the text does not look like a BOW so the app
    can fall back to using the raw upload text only.
    """
    raw = str(raw_text or "")
    if "term" not in raw.lower() or not _BOW_WEEK_ROW_RE.search(raw):
        return []
    norm = re.sub(r"===== PAGE \d+ =====", " ", raw)
    norm = re.sub(r"Page\s+\d+\s+of\s+\d+\s+Last\s+updated", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    marks = sorted((m.start(), label) for label, pattern in _BOW_TERM_MARKERS
                   for m in re.finditer(pattern, norm, re.IGNORECASE))
    if not marks:
        return []
    terms = []
    for index, (start, label) in enumerate(marks):
        segment = norm[start + len(label): marks[index + 1][0] if index + 1 < len(marks) else len(norm)]
        term = {"term": label, "content_standards": [], "performance_standard": "", "weeks": [], "suggested_activities": []}
        standards = re.search(r"Content\s+Standards?(.*?)(Performance\s+Standard|$)", segment, re.IGNORECASE | re.DOTALL)
        if standards:
            term["content_standards"] = [p for p in (_clean_bow_phrase(x) for x in re.split(_BOW_BULLET, standards.group(1))) if len(p) > 20]
        performance = re.search(r"Performance\s+Standard(.*?)(?=\b\d{1,2}\s*to\s*\d{1,2}\b|$)", segment, re.IGNORECASE | re.DOTALL)
        if performance:
            term["performance_standard"] = _clean_bow_phrase(performance.group(1))
        activities = re.search(r"Suggested\s+Activities", segment, re.IGNORECASE)
        week_zone = segment[:activities.start()] if activities else segment
        rows = list(_BOW_WEEK_ROW_RE.finditer(week_zone))
        for row_index, match in enumerate(rows):
            lo, hi = int(match.group(1)), int(match.group(2))
            if not (1 <= lo <= hi <= 20):
                continue
            body = week_zone[match.end(): rows[row_index + 1].start() if row_index + 1 < len(rows) else len(week_zone)]
            parts = re.split(_BOW_BULLET, body, maxsplit=1)
            title = _clean_bow_phrase(parts[0])[:160] or "Lesson"
            competencies = [c for c in (_clean_bow_phrase(x) for x in re.split(_BOW_BULLET, parts[1] if len(parts) > 1 else "")) if len(c) > 25]
            term["weeks"].append({"weeks": f"{lo} to {hi}", "from": lo, "to": hi, "lesson": title, "competencies": competencies})
        if activities:
            term["suggested_activities"] = [a for a in (_clean_bow_phrase(x) for x in re.split(_BOW_BULLET, segment[activities.end():])) if len(a) > 25]
        if term["weeks"] or term["content_standards"]:
            terms.append(term)
    return terms


def _bow_area_grade(raw):
    """Best-effort Learning Area + Grade detection from a BOW header/footer.

    Grade detection scans the WHOLE document (not just the header) because some
    BOW layouts only carry the grade in the filename or a footer line.
    """
    whole = str(raw or "")
    head = whole[:800]
    grade_match = (re.search(r"Grade\s*[:\-]?\s*(\d{1,2})", head, re.IGNORECASE)
                   or re.search(r"\bGrade\s*[:\-]?\s*(\d{1,2})\b", whole, re.IGNORECASE))
    grade = f"Grade {grade_match.group(1)}" if grade_match else ""
    area = next((candidate for candidate in _KNOWN_AREAS
                 if re.search(rf"\b{re.escape(candidate)}\b", head, re.IGNORECASE)), "")
    if not area:
        pipe = re.search(r"\|\s*([A-Z][A-Za-z &]{2,40})", head)
        area = pipe.group(1).strip() if pipe else ""
    return area, grade


def detect_exemplar_meta(raw_text):
    """Detect Learning Area, Grade, Term, and Week from an uploaded Lesson Exemplar.

    Official DepEd exemplars carry a header like 'Learning Area: GENERAL MATHEMATICS
    Grade Level: 11 / Semester: FIRST Quarter: FIRST Unit: 1' plus week markers in
    the body. Returns a dict of display-ready values; empty strings when not found.
    """
    norm = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    meta = {"area": "", "grade": "", "term": "", "week": ""}
    role_words = ("specialist", "writer", "expert", "developer", "reviewer", "panel",
                  "team", "coordinator", "chair", "teacher in charge", "illustrator")
    candidates = re.findall(
        r"Learning Area\s*:\s*([A-Za-z][A-Za-z &]{1,40}?)(?=\s+(?:Grade|Semester|Quarter|Unit|Week|Intended)\b|[.,;]|$)",
        norm, re.IGNORECASE)
    picked = ""
    for candidate in candidates:
        cleaned = candidate.strip().strip("|:").strip()
        if not cleaned or any(word in cleaned.lower() for word in role_words):
            continue
        if cleaned.upper() == cleaned or any(re.search(rf"\b{re.escape(known)}\b", cleaned, re.IGNORECASE) for known in _KNOWN_AREAS):
            picked = cleaned.title() if cleaned.isupper() else cleaned
            break
        picked = picked or (cleaned.title() if cleaned.isupper() else cleaned)
    if not picked:
        fallback = re.search(r"Lesson Exemplar (?:in|for)\s+([A-Za-z][A-Za-z &]{2,40}?)(?=\s+(?:Quarter|Unit|Week|This|L\b)|[.,]|$)", norm, re.IGNORECASE)
        if fallback:
            picked = fallback.group(1).strip().title()
    meta["area"] = picked
    grade_match = re.search(r"Grade\s*Level\s*:?\s*(\d{1,2})", norm, re.IGNORECASE) or re.search(r"\bGrade\s*[:\-]?\s*(\d{1,2})\b", norm, re.IGNORECASE)
    meta["grade"] = f"Grade {grade_match.group(1)}" if grade_match else ""
    semester = re.search(r"Semester\s*:?\s*(First|Second)", norm, re.IGNORECASE)
    quarter = re.search(r"Quarter\s*:?\s*(First|Second|Third|Fourth|1|2|3|4)\b", norm, re.IGNORECASE)
    if semester:
        meta["term"] = "Term 1" if semester.group(1).lower() == "first" else "Term 2"
    elif quarter:
        quarter_num = {"first": 1, "second": 2, "third": 3, "fourth": 3, "1": 1, "2": 2, "3": 3, "4": 3}.get(quarter.group(1).lower(), 1)
        meta["term"] = f"Term {quarter_num}"
    week_match = re.search(r"\bWeeks?\s+(\d{1,2})(?:\s*(?:to|-|–)\s*(\d{1,2}))?\b", norm, re.IGNORECASE)
    if week_match:
        meta["week"] = f"Week {week_match.group(1)}"
    return meta


def week_lookup_for(struct, label):
    """Resolve a week-dropdown label back to (term_index, term, row) from the parsed BOW."""
    if not label or not struct:
        return None
    match = re.match(r"^(Term \d)\s*·\s*Week (\d+)", str(label))
    if not match:
        return None
    term_name, week_num = match.group(1), int(match.group(2))
    for term_index, term in enumerate(struct, start=1):
        if str(term["term"]).lower() != term_name.lower():
            continue
        for row in term["weeks"]:
            if row["from"] <= week_num <= row["to"]:
                return term_index, term, row
    return None


def match_bow_row(struct, term, week):
    """Prompt hint naming the BOW week row that matches the teacher's Term + Week.
    Overlapping ranges resolve to the FIRST matching row in the selected term."""
    week_number = re.search(r"\d{1,2}", str(week or ""))
    if not week_number or not struct:
        return ""
    week_num = int(week_number.group(0))
    wanted = str(term or "").strip().lower()
    candidates = [t for t in struct if str(t["term"]).lower() == wanted] or list(struct)
    for t in candidates:
        for row in t["weeks"]:
            if row["from"] <= week_num <= row["to"]:
                return (f"\nBOW MATCH — the teacher selected {t['term']}, Week {week_num}. The matching Budget of Work row is "
                        f"'Weeks {row['weeks']}: {row['lesson']}'. Use THIS row's lesson title and learning competencies "
                        f"(first matching row when ranges overlap); do not use rows from other terms or weeks.")
    return ""


def summarize_bow(struct, term=None, week=None):
    """Render the parsed BOW as an explicit, AI-ready summary block."""
    lines = ["PARSED BOW SUMMARY (machine-extracted from the uploaded Budget of Work — authoritative for terms, standards, week rows, competencies, and activities):"]
    for t in struct:
        lines.append(f"\n=== {t['term'].upper()} ===")
        if t["content_standards"]:
            lines.append("Content Standards:")
            lines.extend(f"  • {c}" for c in t["content_standards"])
        if t["performance_standard"]:
            lines.append(f"Performance Standard: {t['performance_standard']}")
        lines.append("Week rows (week range → lesson title → learning competencies):")
        for row in t["weeks"]:
            lines.append(f"  • Weeks {row['weeks']}: {row['lesson']}")
            lines.extend(f"      - {c}" for c in row["competencies"])
        if t["suggested_activities"]:
            lines.append("Suggested Activities:")
            lines.extend(f"  • {a}" for a in t["suggested_activities"])
    if week:
        lines.append(f"\nNOTE: the teacher selected {term or 'a term'} / {week}. The lesson for this plan is the row whose week "
                     "range contains that week — when two ranges overlap, use the FIRST matching row in that term. "
                     "Never use week rows from other terms or other weeks.")
    return "\n".join(lines)


@st.cache_data
def read_document_cached(filename, data):
    """read_any_document, cached on file bytes so reruns don't re-parse uploads."""
    class _Uploaded:
        name = filename
        def getvalue(self):
            return data
    return read_any_document(_Uploaded())


def _strategy_phases(strategy):
    """Extract the phase names from a TEACHING_STRATEGIES entry for prompt guidance."""
    tail = str(strategy or "").split("—")[-1]
    if "→" in tail:
        return [p.strip() for p in tail.split("→") if p.strip()]
    return [p.strip() for p in tail.split(",") if p.strip()]


def make_prompt(d):
    return f"""You are an expert Philippine DepEd teacher creating a DRAFT weekly ILAW lesson plan.
ILAW means Intentions, Learning Experiences, Assessing Learning, and Ways Forward.
Use the supplied competency source as the basis for learning competencies and pacing. Do not invent
competency codes or claim DepEd approval. Create exactly {d['sessions']} learner-centered sessions —
no fewer, no more: the "sessions" array in your JSON must contain exactly {d['sessions']} objects,
numbered "Session 1" to "Session {d['sessions']}" in teaching order; their activity times should fit
approximately {d['duration']} each. Use {d['medium']}.
{CURRICULUM_SOURCE_PRIORITY}
{STRICT_CURRICULUM_VERIFICATION}
Required teaching strategy model: {d['strategy']}. The FLOW must explicitly use this model's phases
in their logical order. Do not substitute another teaching strategy model. For models whose phase is
called Evaluate or Extend, describe that phase as part of the in-class procedure in FLOW, but keep the
formal assessment details in formative_assessment and any outside-class task in extended_learning.
Keep each part strictly in its designated ILAW row:
- pre_lesson: only learner readiness, prior-knowledge activation, motivation, or well-being check.
- learning_objectives: unpack the competency into SMART objectives. Do NOT go beyond the Bloom's
  taxonomy level of the learning competency — if the competency targets "apply", do not write
  "create" or "evaluate" objectives. Cover Knowledge, Skills, and Attitude (KSA): include at least
  one knowledge objective, one skills objective, and one attitude/values objective.
- flow: only the in-class teaching-learning procedure needed to meet the objectives. Include sequencing,
  teacher/learner actions, collaboration, guided practice, and independent practice. NEVER include a
  formative assessment, extended learning/homework, feedback/closure, or teacher reflection here.
  FORMAT: write EACH phase of {d['strategy']} on its own line as 'PhaseName: paragraph'. The phases of
  {d['strategy']} are exactly: {', '.join(_strategy_phases(d['strategy']))}. Never merge two phases into
  one paragraph — every phase starts on a FRESH line with its 'PhaseName:' label. The paragraph after
  each label is 3 to 6 full sentences describing concrete teacher and learner actions. No numbering, no
  asterisks, no markdown; the 'Label:' prefix and the line breaks are the only formatting.
- learning_resources: list the actual teaching materials for that session, one per '- ' line, and END the
  list with exactly ONE reference for the session in one of these two forms:
  '- Book Title, Author, Page N' (for a book) or '- Website Name, URL: full link' (for a website).
  Use REAL, well-known references suited to the topic (official DepEd materials, established textbooks,
  reputable education sites). Never invent an author, page number, or URL; when a page is unknown write
  'Page: not stated', and when a deep link is unknown give the site's main page.
- formative_assessment: only the evidence-gathering task and learner support/accommodations. The
  assessment MUST directly address the learning objectives — every objective is measurable by at
  least one assessment item or task.
- extended_learning (Ways Forward): only optional outside-class reinforcement/enrichment. Prepare a
  HIGHER-LEVEL activity or enhancement for the next lesson (for advanced learners) rather than plain
  homework.
- reflection: only a teacher-facing question or note after the session.
SOURCE FIDELITY — before writing anything, review the plan against the source:
- If a BOW text is supplied below, verify every competency and pacing against it; if no BOW is
  supplied, work ONLY from well-known public DepEd curriculum sources for the learning area and grade.
- For every Learning Competency, Objective, Activity, Assessment, Strategy, and Ways Forward:
  verify it is supported by the selected lesson; identify anything taken from another lesson;
  identify anything invented or unsupported; REMOVE unsupported content; preserve original activity
  titles and numbers; and make sure the Component is NOT merely a repetition of the Learning Area.
- Return only the corrected ILAW plan.
Extra teacher instructions (follow these unless they conflict with the rules above): {d.get('note') or 'None'}
Respond ONLY with valid JSON matching this schema, with no markdown or extra keys:
{json.dumps(SCHEMA)}
Learning area: {d['area']}; Grade/section: {d['grade']}; Term: {d['term']}; Week: {d['week']}
Lesson title: {d['title'] or 'Create an appropriate title'}; Teacher: {d['teacher'] or 'Not specified'}
Learner/classroom context: {d['context'] or 'Not specified'}
{d.get('bow_match', '')}
BOW TEXT:
{d['bow']}
"""


def _sessions_from_plan(plan):
    """Read a plan's sessions list regardless of dict/list shape."""
    sessions = plan.get("sessions") or []
    if isinstance(sessions, dict):
        sessions = list(sessions.values())
    return sessions


def _enforce_session_count(plan, expected, retry_prompt):
    """Force the plan's session list to be exactly `expected` long.

    Some models — most often through OpenRouter — return fewer (or more) sessions
    than requested. One strict retry first; truncate or pad only as a last resort.
    """
    sessions = _sessions_from_plan(plan)
    if expected and len(sessions) != expected:
        try:
            retry_plan = _ask_and_parse(retry_prompt, {"response_mime_type": "application/json", "temperature": 0.2})
            retry_sessions = _sessions_from_plan(retry_plan)
            if len(retry_sessions) == expected:
                plan, sessions = retry_plan, retry_sessions
        except Exception:
            pass
    if len(sessions) > expected:
        sessions = sessions[:expected]
    plan["sessions"] = sessions
    while len(sessions) < expected:
        sessions.append({"session": f"Session {len(sessions) + 1}", "topic": "N/A"})
    return plan


CURRICULUM_SOURCE_PRIORITY = """CURRICULUM SOURCE PRIORITY
When determining the lesson for the selected Grade Level, Learning Area,
Term, and Week, follow this order:
1. Use the teacher-provided curriculum document, BOW, or Lesson Exemplar
   if available.
2. If no relevant uploaded source is available, search for an official
   DepEd source corresponding to the exact Grade Level, Learning Area,
   Term, and Week.
3. If an official DepEd source cannot be found, use reputable educational
   sources only as secondary references.
4. Never determine the lesson solely from general knowledge.
5. Never use an unrelated lesson from an uploaded document merely because
   it belongs to the same grade level or subject.
6. Never combine content from different weeks or lessons.
7. If multiple sources disagree, prioritize the official DepEd source and
   do not silently choose an unsupported topic.
8. If the lesson cannot be verified, clearly report:
   "Curriculum alignment could not be verified from the available sources."
   """


STRICT_CURRICULUM_VERIFICATION = """STRICT CURRICULUM VERIFICATION RULE:

Do not generate an ILAW lesson plan until the lesson topic and learning
competency have been verified for the exact:

Grade Level + Learning Area + Term + Week.

If the lesson topic cannot be verified from a reliable curriculum source,
DO NOT invent or infer a topic from general knowledge.

Return:

"Curriculum alignment could not be verified. Please provide the
corresponding BOW, Lesson Exemplar, or official curriculum source."

Do not generate learning objectives, activities, assessments, or
Ways Forward based on an unverified topic.

Never fabricate URLs, references, textbook page numbers, or source titles.

If a reference cannot be verified, omit it or label it as:
"Teacher-provided resource - verification required."

WHEN THE LESSON CANNOT BE VERIFIED, respond ONLY with this JSON and nothing else:
{"curriculum_verification": "FAILED", "message": "Curriculum alignment could not be verified. Please provide the corresponding BOW, Lesson Exemplar, or official curriculum source."}
"""


REVIEW_CHECKLIST = """- Verify that it is supported by the selected lesson.
- Identify anything taken from another lesson.
- Identify anything invented or unsupported.
- Remove unsupported content.
- Preserve original activity titles and numbers.
- Ensure the Component is not merely a repetition of the Learning Area."""


def make_review_prompt(details, plan):
    """Second-pass prompt: review the drafted ILAW against the BOW (or, when no BOW
    was uploaded, the public DepEd curriculum sources) and return only the corrected plan."""
    source = (details.get("bow") or "").strip()
    source_block = f"BUDGET OF WORK (the source to verify against):\n{source[:40000]}" if source else (
        "NO BOW was uploaded — search your knowledge of the official public DepEd curriculum "
        f"for this learning area and grade thoroughly, and verify the plan against it.")
    return f"""You are an expert Philippine DepEd teacher reviewing a drafted weekly ILAW lesson plan.
Review the generated ILAW Lesson Plan against the BOW if one is supplied; when none is supplied,
research the competency in the public DepEd curriculum thoroughly instead.
For every Learning Competency, Objective, Activity, Assessment, Strategy, and Ways Forward:
{REVIEW_CHECKLIST}
{CURRICULUM_SOURCE_PRIORITY}
{STRICT_CURRICULUM_VERIFICATION}
Return ONLY the corrected ILAW plan as JSON — the full plan in the same schema, with every problem
fixed and nothing else changed. Keep the exact same number of sessions ({len(_sessions_from_plan(plan))}).
Keep every strategy-model phase on its own 'PhaseName: paragraph' line exactly as drafted.
Respond ONLY with valid JSON matching this schema, with no markdown or extra keys:
{json.dumps(SCHEMA)}
Learning area: {details.get('area', '')}; Grade/section: {details.get('grade', '')}; Term: {details.get('term', '')}; Week: {details.get('week', '')}
Required teaching strategy model: {details.get('strategy', '')}
{source_block}
DRAFT TO REVIEW AND CORRECT:
{json.dumps(plan, ensure_ascii=False)}
"""


def make_lil_review_prompt(details, plan):
    """Second-pass prompt: review the drafted LIL against the Lesson Exemplar and
    return only the corrected log."""
    return f"""You are an expert Philippine DepEd teacher reviewing a drafted Lesson Implementation Log (LIL).
Review the generated LIL against the source Lesson Exemplar below.
For every Learning Competency, Objective, Activity, Assessment, Strategy, and Ways Forward:
{REVIEW_CHECKLIST}
{CURRICULUM_SOURCE_PRIORITY}
{STRICT_CURRICULUM_VERIFICATION}
Return ONLY the corrected LIL as JSON — the full log in the same schema, with every problem fixed
and nothing else changed. Keep the exact same number of sessions ({len(_sessions_from_plan(plan))}).
Keep every strategy-model phase on its own 'PhaseName: paragraph' line exactly as drafted.
Respond ONLY with valid JSON matching this schema, with no markdown or extra keys:
{json.dumps(LIL_SCHEMA)}
Learning area: {details.get('area', '')}; Teacher: {details.get('teacher', '')}; Term/Week: {details.get('termweek', '')}
Required teaching strategy model: {details.get('strategy', '')}
LESSON EXEMPLAR (the source to verify against):
{(details.get('exemplar') or '')[:40000]}
DRAFT TO REVIEW AND CORRECT:
{json.dumps(plan, ensure_ascii=False)}
"""


def _gemini_sources_sdk(response):
    """Extract grounded source links from a google-genai SDK response."""
    sources, seen = [], set()
    metadata = getattr(response.candidates[0], "grounding_metadata", None) if response.candidates else None
    for chunk in getattr(metadata, "grounding_chunks", []) or []:
        web = getattr(chunk, "web", None)
        url = getattr(web, "uri", None) if web else None
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": getattr(web, "title", "Online source"), "url": url})
            if len(sources) == 4:
                break
    return sources


def find_competency_online(d):
    """Find a candidate competency and return grounded sources for the Excel references row."""
    offline = "" if st.session_state.get("provider", _DEFAULT_PROVIDER) == _DEFAULT_PROVIDER else (
        "Note: this provider may not have live web search. Use only official DepEd sources you are certain "
        "of, and say so explicitly when unsure. Never invent a competency, URL, title, or page number.\n")
    prompt = f"""Search the public web for an official DepEd Budget of Work / curriculum source relevant to:
Learning area: {d['area']}; Grade level: {d['grade']}; Term: {d['term']}; Week: {d['week']}.
{offline}Return a concise plain-text research note with the exact competency code and wording if found.
For every source you discuss, write its title, URL, and "Page: <number>" only when a page number is
explicitly visible in the source PDF; otherwise write "Page: not stated". Do not invent a competency,
URL, title, or page number."""
    note = ask_ai(prompt, tools=True)
    return note, st.session_state.get("last_sources", [])


def read_ilaw_excel(uploaded_file):
    """Read the first sheet of an uploaded ILAW lesson plan into one text block."""
    workbook = load_workbook(BytesIO(uploaded_file.getvalue()), data_only=True)
    lines = []
    for sheet in workbook.worksheets:
        lines.append(f"--- Sheet: {sheet.title} ---")
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value not in (None, ""):
                    text = str(cell.value).strip()
                    if text:
                        lines.append(f"{cell.coordinate}: {text}")
    return "\n".join(lines)[:60000]


def extract_pptx_slides(basis):
    """Turn an ILAW basis (Excel text or raw text) into structured slide outlines.

    Returns (meta, slides): meta carries title/subject/teacher; slides is a list of
    {title, bullets, session} dicts covering every session in the plan.
    """
    meta = {"title": "Untitled lesson", "subject": "", "teacher": "", "sessions": 0}
    slides = []
    raw_lines = basis.splitlines()
    for line in raw_lines:
        m = re.match(r"^[A-Z]+\d+:\s*(.+)$", line.strip())
        if not m:
            continue
        text = m.group(1).strip()
        low = text.lower()
        if meta["title"] == "Untitled lesson" and low.startswith("lesson title"):
            meta["title"] = text.split(":", 1)[1].strip() if ":" in text else text
        elif low.startswith("learning area") or low.startswith("subject"):
            meta["subject"] = text.split(":", 1)[1].strip() if ":" in text else text
        elif low.startswith("teacher") and not meta["teacher"]:
            meta["teacher"] = text.split(":", 1)[1].strip() if ":" in text else text
    session_pattern = re.compile(r"session\s*(\d+)", re.I)
    current = None
    for line in raw_lines:
        m = re.match(r"^[A-Z]+14:\s*(.+)$", line.strip())  # row 14 = session headers in the ILAW template
        if m:
            sm = session_pattern.search(m.group(1))
            if sm:
                current = int(sm.group(1))
                slides.append({"title": m.group(1).strip(), "bullets": [], "session": current})
        m2 = re.match(r"^[A-Z]+19:\s*(.+)$", line.strip())  # row 19 = learning objectives
        if m2 and current:
            for bullet in re.split(r"[\n•]+", m2.group(1)):
                bullet = bullet.strip().lstrip("-• ").strip()
                if bullet:
                    slides.append({"title": f"Objectives — Session {current}", "bullets": [bullet], "session": current})
        m3 = re.match(r"^[A-Z]+23:\s*(.+)$", line.strip())  # row 23 = flow
        if m3 and current and slides:
            for bullet in re.split(r"[\n•]+", m3.group(1)):
                bullet = bullet.strip().lstrip("-• ").strip()
                if bullet:
                    slides.append({"title": f"Flow — Session {current}", "bullets": [bullet], "session": current})
    if not slides:  # plain-text basis (topic string): let the AI structure it later
        slides = [{"title": meta["title"], "bullets": [], "session": 0}]
    meta["sessions"] = len({s["session"] for s in slides if s["session"]})
    return meta, slides


STRANDS = [
    ("Strand 1\n40%\nRemembering/\nUnderstanding", ("Remembering", "Understanding")),
    ("Strand 2\n30%\nApplying/\nAnalyzing", ("Applying", "Analyzing")),
    ("Strand 3\n30%\nEvaluating/\nCreating", ("Evaluating", "Creating")),
]
BOOKMAN = "Bookman Old Style"


def school_year(now=None):
    """Return the DepEd-style school year string, e.g. 2026-2027."""
    moment = now or date.today()
    start = moment.year if moment.month >= 6 else moment.year - 1
    return f"{start}-{start + 1}"


def fmt_ranges(numbers):
    """Format item numbers as consecutive ranges: '1-2, 5, 8-9'."""
    numbers = sorted({int(n) for n in numbers})
    parts, start, prev = [], None, None
    for number in numbers:
        if start is None:
            start = prev = number
        elif number == prev + 1:
            prev = number
        else:
            parts.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = number
    if start is not None:
        parts.append(str(start) if start == prev else f"{start}-{prev}")
    return ", ".join(parts)


def build_tos(items, days_map=None):
    """DepEd-style TOS rows: competency, teaching days, %, item count, and item ranges per strand."""
    days_map = {k: v for k, v in (days_map or {}).items()}
    rows = []
    competencies = list(dict.fromkeys(item.get("competency", "") or "Unlabeled competency" for item in items))
    days_per = {}
    for competency in competencies:
        try:
            days_per[competency] = max(1, int(days_map.get(competency)))
        except (TypeError, ValueError):
            days_per[competency] = 5  # fallback when the official pacing is not stated
    total_days = max(1, sum(days_per.values()))
    for competency in competencies:
        group = [item for item in items if (item.get("competency", "") or "Unlabeled competency") == competency]
        numbers = [item.get("number") for item in group]
        try:
            first = min(int(n) for n in numbers)
        except (TypeError, ValueError):
            first = 10**9
        rows.append({
            "competency": competency,
            "days": days_per[competency],
            "pct": f"{100 * days_per[competency] / total_days:.2f}%",
            "items": len(group),
            "strands": [fmt_ranges(item.get("number") for item in group if item.get("cognitive_level") in levels) for _, levels in STRANDS],
            "_first": first,
        })
    rows.sort(key=lambda row: row["_first"])  # oldest/first-taught lesson on top of the TOS
    for row in rows:
        row.pop("_first")
    return rows


def make_test_prompt(basis, d):
    return f"""You are an expert Philippine DepEd teacher writing a multiple-choice test paper
administered as a {d['test_type']}.
Base every item ONLY on the test basis supplied below; do not introduce outside topics.
Create exactly {d['items']} multiple-choice items with exactly 4 choices (A-D) each and exactly one correct answer.
IMPORTANT: For EVERY item, write THREE complete alternative versions of that item (same competency, same number,
same cognitive tier). Each alternative must ask about the same competency from a different angle or scenario, with
its OWN 4 choices, correct answer, and rationale. The teacher will pick one alternative per item. Structure each item
as: {{"number": n, "competency": "...", "variants": [version1, version2, version3]}} — always exactly 3 variants.
Tier mix: LOTS {d['mix']['lots']}% Remembering/Understanding, MOTS {d['mix']['mots']}% Applying/Analyzing, HOTS {d['mix']['hots']}% Evaluating/Creating.
Tag each item with one Bloom's cognitive level and the matching SOLO level: Remembering/Understanding items are
Unistructural or Multistructural, Applying/Analyzing items are Relational, Evaluating/Creating items are Extended Abstract.
At least {d['hots_min']} items must be HOTS (Evaluating or Creating).
Read the test basis and determine the teaching sequence of its learning competencies: which lesson was
taught FIRST (oldest) down to the most RECENT lesson. Group all items of the same competency together
and number them following that sequence - the oldest lesson gets the lowest item numbers, and the most
recent lesson the highest. Never invent competency codes.
Set each competency's days from the TEACHING DAYS RESEARCH NOTE in the test basis; when a competency says
"days not stated", estimate its days proportionally to the items you assign it. Use the real day counts
(1, 2, 3, 5, 6, or more days) — never give every competency the same number unless the source truly does.
Choices must be plausible; distractors must reflect common learner misconceptions. Write all four choices in
parallel structure and with almost the same length and wording pattern as the correct answer, so learners can
never guess the key from length alone. Spread any extra detail evenly across all choices, and avoid "all of the
above", "none of the above", and joke options.
ANSWER KEY SPREAD: do NOT put every correct answer under the same letter. Vary the position of the correct
choice across items so the keys are roughly evenly distributed among A, B, C, and D — never three or more
consecutive items sharing the same key letter.
Extra teacher instructions (follow these unless they conflict with the rules above): {d.get('note') or 'None'}
Respond ONLY with valid JSON matching this schema, with no markdown or extra keys:
{json.dumps(TEST_SCHEMA)}
Grade level and section: {d['grade']}; Subject/learning area: {d['area']}; Term: {d['term']}
TEST BASIS:
{basis}
"""


def research_competency_days(basis, d):
    """Grounded web research on official DepEd pacing: teaching days per competency."""
    offline = "" if st.session_state.get("provider", _DEFAULT_PROVIDER) == _DEFAULT_PROVIDER else (
        "Note: this provider may not have live web search. State days only for official DepEd documents you "
        "are certain about; otherwise write \"days not stated\". Never invent days, titles, or URLs.\n")
    prompt = f"""Search the public web for the official DepEd Budget of Work (BOW) or curriculum guide pacing.
Learning area: {d['area']}; Grade level: {d['grade']}; Term: {d['term']}.
{offline}List each distinct learning competency from the test basis below. For EACH competency, state the number
of teaching days the official source allots to it — for example "5 days". A competency may be allotted
1, 2, 3, 4, 5, 6, or more days; do not assume they are equal. If the official pacing is not stated for a
competency, write "days not stated". Also state the term's total teaching days if the source shows it.
Do not invent days, titles, or URLs.
TEST BASIS:
{basis[:8000]}"""
    note = ask_ai(prompt, tools=True)
    sources = st.session_state.get("last_sources", [])
    note = note or ""
    if not note.strip():
        note = ("No public source was found. Days will be distributed evenly (5 days each); "
                "edit the TOS if you know the official pacing.")
    return note, sources


def _norm_key_letter(value):
    """Normalize an answer like 'a', 'A.', '(B)' to its bare letter, or None when invalid."""
    match = re.search(r"[A-Da-d]", str(value or ""))
    return match.group(0).upper() if match else None


def balance_answer_keys(test):
    """Spread every variant's answer key across A–D so learners can't pattern-match.

    The AI tends to pile keys on one letter (usually A). Variants are walked in order
    against a repeating shuffled ABCD cycle, and each variant's correct choice is
    swapped into its slot — texts are preserved exactly, only the letters move.
    Because every cycle block contains each letter once, the distribution stays even
    and no key repeats more than twice in a row. Deterministic per test title.
    """
    items = test.get("items", [])
    rng = random.Random(str(test.get("test_title", "keys")))
    targets = []
    while len(targets) < sum(len(it.get("variants", [])) for it in items) + 8:
        block = ["A", "B", "C", "D"]
        rng.shuffle(block)
        targets.extend(block)
    position = 0
    for item in items:
        for variant in item.get("variants", []):
            choices = variant.get("choices") if isinstance(variant.get("choices"), dict) else None
            current = _norm_key_letter(variant.get("answer"))
            if not choices or not current or not str(choices.get(current, "")).strip():
                continue
            if len([letter for letter in "ABCD" if str(choices.get(letter, "")).strip()]) != 4:
                continue
            target = targets[position % len(targets)]
            position += 1
            if target != current:
                choices[current], choices[target] = choices[target], choices[current]
                variant["choices"] = choices
                variant["answer"] = target
    return test


def generate_test(api_key, basis, d):
    d["days_note"], d["day_sources"] = research_competency_days(basis, d)
    enriched_basis = basis + "\n\nTEACHING DAYS RESEARCH NOTE — verify before use:\n" + d["days_note"]
    plan = _ask_and_parse(make_test_prompt(enriched_basis, d),
        {"response_mime_type": "application/json", "temperature": 0.35, "max_output_tokens": 65536},
    )
    items = plan.get("items", [])
    for index, item in enumerate(items, 1):
        item.setdefault("number", index)
        raw_variants = item.get("variants") or []
        if isinstance(raw_variants, dict):
            raw_variants = list(raw_variants.values())
        variants = []
        for raw in raw_variants:
            if not isinstance(raw, dict):
                continue
            if raw.get("question") and raw.get("choices"):  # already a full variant
                variants.append(raw)
            elif raw.get("question"):  # variant missing choices: keep question only
                variants.append(raw)
        if not variants and item.get("question"):  # flat item → wrap as the single variant
            variants.append({key: item.get(key) for key in ("question", "choices", "answer", "solo_level", "cognitive_level", "rationale") if key in item})
        while len(variants) < 3:
            variants.append(dict(variants[-1])) if variants else variants.append({"question": "(No variant returned)", "choices": {}, "answer": "", "rationale": ""})
        item["variants"] = variants[:3]
        item.pop("question", None)
        item.pop("choices", None)
    balance_answer_keys(plan)
    return plan


def show_test(test, d=None):
    """Per-question variant grid: 3 AI versions of every item; the teacher picks one."""
    st.session_state.setdefault("test_picks", {})
    st.subheader(test.get("test_title", "Test Paper Generator"))
    st.info(test.get("instructions", ""))
    st.caption("Competencies covered (teaching days from researched official pacing):")
    for competency in test.get("competencies", []):
        days = competency.get("days")
        days_text = f" — **{days} day{'s' if days != 1 else ''}**" if isinstance(days, (int, float)) else ""
        st.markdown(f"- {competency.get('statement', '')}{days_text}")
    if d and d.get("days_note"):
        with st.expander("📅 Teaching-days research (verify before use)"):
            st.write(d["days_note"])
            for source in d.get("day_sources", []):
                st.markdown(f"- [{source['title']}]({source['url']})")
    st.markdown("##### 🎛️ Pick one version per question — Version A is used wherever you make no choice.")
    for item in test.get("items", []):
        number = item.get("number")
        first_variant = (item.get("variants") or [{}])[0]
        with st.expander(f"{number}. {str(first_variant.get('question', item.get('competency', '')))[:90]}"):
            variants = item.get("variants") or []
            cols = st.columns(3)
            for variant_index, column in enumerate(cols):
                variant = variants[variant_index] if variant_index < len(variants) else {}
                picked = st.session_state.test_picks.get(number, 0)
                letter = "ABC"[variant_index]
                body = (f"<b>{variant.get('question', '—')}</b><br><br>"
                        + "<br>".join(f"{ch}. {variant.get('choices', {}).get(ch, '')}" for ch in "ABCD")
                        + f"<br><br><b>Key: {variant.get('answer', '')}</b> — {variant.get('rationale', '')}"
                        + f"<br><i>SOLO: {variant.get('solo_level', '')} · {variant.get('cognitive_level', '')}</i>")
                with column:
                    if picked == variant_index:
                        st.markdown(f"<div style='border:2px solid #2e7d32;border-radius:8px;padding:8px;background:#e8f5e9;'><b>Version {letter}</b> · Selected<br>{body}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='border:1px solid #bbb;border-radius:8px;padding:8px;background:#fafafa;'><b>Version {letter}</b><br>{body}</div>", unsafe_allow_html=True)
                    if st.button(f"Pick {letter}", key=f"variant_{number}_{variant_index}", use_container_width=True):
                        st.session_state.test_picks[number] = variant_index
                        st.rerun()
    items = test.get("items", [])
    counts = {tier: sum(1 for item in items if ((item.get("variants") or [{}])[st.session_state.test_picks.get(item.get("number"), 0)]).get("cognitive_level") in levels) for tier, levels in TIER_LEVELS.items()}
    st.caption(f"{len(items)} questions · current picks: LOTS {counts['LOTS']} · MOTS {counts['MOTS']} · HOTS {counts['HOTS']}")


def picked_test(test):
    """Collapse the picked test into the v1.0 single-variant shape for export."""
    picks = st.session_state.get("test_picks", {})
    chosen = {"test_title": test.get("test_title", ""), "instructions": test.get("instructions", ""), "competencies": test.get("competencies", []), "items": []}
    for item in test.get("items", []):
        variants = item.get("variants") or [{}]
        variant = variants[picks.get(item.get("number"), 0)] if variants else {}
        chosen["items"].append({
            "number": item.get("number"), "question": variant.get("question", ""),
            "choices": variant.get("choices", {}), "answer": variant.get("answer", ""),
            "solo_level": variant.get("solo_level", ""), "cognitive_level": variant.get("cognitive_level", ""),
            "competency": item.get("competency", ""), "rationale": variant.get("rationale", ""),
        })
    return chosen


def set_margins(section, size=0.65):
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attr, Inches(size))


def bookman_run(paragraph, text, size=14, bold=False):
    run = paragraph.add_run(text)
    run.font.name = BOOKMAN
    run.font.size = Pt(size)
    run.bold = bold
    return run


def centered_line(document, text, size=14, bold=False):
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    bookman_run(paragraph, text, size, bold)
    return paragraph


def export_test_docx(test, d):
    """Return a ZIP of three DepEd-formatted Word files: test paper, answer key, and TOS."""
    items = test.get("items", [])
    grade_number = re.search(r"grade\s*(\d+)", str(d.get("grade", "")), re.I)
    subject_text = str(d.get("area", "Subject")).strip()
    if grade_number and not re.search(rf"\b{grade_number.group(1)}\b", subject_text):
        subject_text = f"{subject_text} {grade_number.group(1)}"
    subject = subject_text.upper() or "SUBJECT"
    sy = school_year()
    term_text = str(d.get("term", "Term 1"))
    term_label = term_text.upper() if term_text.upper().startswith("TERM") else f"TERM {term_text}"
    type_text = str(d.get("test_type", "Examination")).strip() or "Examination"
    exam_title = f"{term_label} {type_text.upper()}"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{subject_text} {term_text}").strip("_")
    type_clean = re.sub(r"[^A-Za-z0-9]+", "_", type_text).strip("_")

    # --- Examination (Letter portrait) ---
    exam = Document()
    exam.sections[0].page_width, exam.sections[0].page_height = Inches(8.5), Inches(11)
    set_margins(exam.sections[0])
    centered_line(exam, subject, bold=True)
    centered_line(exam, exam_title, bold=True)
    centered_line(exam, f"SY {sy}")
    centered_line(exam, "")
    for line in ("Name: _______________________________\tDate: ________________________",
                 "Section: _____________________________\tTeacher: _____________________"):
        bookman_run(exam.add_paragraph(), line)
    centered_line(exam, "")
    bookman_run(exam.add_paragraph(), test.get("instructions", "Read each item carefully. Choose the letter of the correct answer and write it on the space provided before each number."), bold=True)
    for item in items:
        centered_line(exam, "")
        bookman_run(exam.add_paragraph(), f"_____{item.get('number')}. {item.get('question', '')}")
        for letter in "ABCD":
            bookman_run(exam.add_paragraph(), f"{letter}. {item.get('choices', {}).get(letter, '')}")

    # --- Answer Key (Letter portrait, No./Ans. grid in tens) ---
    key = Document()
    key.sections[0].page_width, key.sections[0].page_height = Inches(8.5), Inches(11)
    set_margins(key.sections[0], 0.7)
    centered_line(key, subject, bold=True)
    centered_line(key, f"{exam_title} - ANSWER KEY", bold=True)
    centered_line(key, f"SY {sy}")
    centered_line(key, "")
    key_table = key.add_table(rows=1 + min(len(items), 10), cols=10)
    key_table.style = "Table Grid"
    key_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for column in range(0, 10, 2):
        for offset, text in enumerate(("No.", "Ans.")):
            cell = key_table.cell(0, column + offset)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            bookman_run(cell.paragraphs[0], text, 12, True)
    for position, item in enumerate(items):
        row, column = 1 + position % 10, (position // 10) * 2
        for cell, text in ((key_table.cell(row, column), str(item.get("number"))),
                           (key_table.cell(row, column + 1), str(item.get("answer", "")))):
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            bookman_run(cell.paragraphs[0], text, 12)
    for column in range(10):
        for cell in key_table.columns[column].cells:
            cell.width = Inches(0.55)

    # --- TOS (A4 landscape, three cognitive strands) ---
    tos = Document()
    section = tos.sections[0]
    section.page_width, section.page_height = Inches(11.69), Inches(8.27)
    section.orientation = WD_ORIENT.LANDSCAPE
    set_margins(section, 0.5)
    centered_line(tos, subject, bold=True)
    centered_line(tos, "Table of Specifications", bold=True)
    centered_line(tos, f"SY {sy}")
    centered_line(tos, term_text)
    centered_line(tos, "")
    days_map = {c.get("statement"): c.get("days") for c in test.get("competencies", [])}
    rows = build_tos(items, days_map)
    table = tos.add_table(rows=2 + len(rows), cols=7)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Learning Competencies", "No. of\nDays", "%", "No. of\nItems", *(name for name, _ in STRANDS)]
    for column, text in enumerate(headers):
        cell = table.cell(0, column)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        bookman_run(cell.paragraphs[0], text, 11, True)
    for row_index, row in enumerate(rows, 1):
        values = [row["competency"], str(row["days"]), row["pct"], str(row["items"]), *row["strands"]]
        for column, text in enumerate(values):
            cell = table.cell(row_index, column)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if column == 0 else WD_ALIGN_PARAGRAPH.CENTER
            bookman_run(cell.paragraphs[0], text, 11)
    strand_totals = [sum(1 for item in items if item.get("cognitive_level") in levels) for _, levels in STRANDS]
    totals = ["TOTAL", str(sum(row["days"] for row in rows)), "100%", str(len(items)), *(str(count) for count in strand_totals)]
    for column, text in enumerate(totals):
        cell = table.cell(len(rows) + 1, column)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT if column == 0 else WD_ALIGN_PARAGRAPH.CENTER
        bookman_run(cell.paragraphs[0], text, 11, True)
    widths = (Inches(3.5), Inches(0.7), Inches(0.9), Inches(0.9), Inches(1.6), Inches(1.6), Inches(1.6))
    for column, width in enumerate(widths):
        for cell in table.columns[column].cells:
            cell.width = width

    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for filename, document in ((f"{slug}_{type_clean}.docx", exam), (f"{slug}_Answer_Key.docx", key), (f"{slug}_TOS.docx", tos)):
            buffer = BytesIO()
            document.save(buffer)
            bundle.writestr(filename, buffer.getvalue())
    archive.seek(0)
    return archive.getvalue()


# Canonical 16-slide pedagogical flow the user requested; the AI maps lesson
# content onto this structure for every session deck.
PPT_SLIDE_FLOW = [
    "Title Slide — topic, subject, grade level",
    "Learning Objectives — show what learners should be able to do",
    "Lesson Motivation / Engage — question, scenario, or short activity",
    "Prior Knowledge — recall or review of the previous lesson",
    "Lesson Introduction — context or problem to explore",
    "Lesson Content 1 — first key concept: definitions and explanations in full paragraphs",
    "Lesson Content 2 — second key concept: definitions and explanations in full paragraphs",
    "Lesson Content 3 — third key concept: definitions and explanations in full paragraphs",
    "Example / Demonstration — one concrete example",
    "Guided Activity — teacher-guided learner activity",
    "Application — apply the concept to a real situation",
    "Higher-Order Question — analyze / evaluate / create",
    "Assessment — quick questions or activity",
    "Generalization — key takeaway of the session",
    "Assignment / Extension — follow-up task",
    "Closing — summary or reflection",
]

# Design presets; the AI turns the chosen style into a concrete theme.
PPT_DESIGN_STYLES = [
    "Education — friendly classroom look, soft blues and greens",
    "Floral — soft petals/leaf accents, pastel pinks and greens",
    "Business — clean and professional, navy, gray and white",
    "Research — academic minimal, maroon, cream and gold",
    "Nature — earthy greens and browns with organic shapes",
    "Space / Science — deep blue and violet with stars and planets",
    "Colorful Playful — bright cheerful colors for young learners",
    "Minimal — plain white with one strong accent color",
]


def make_ppt_prompt(basis, d):
    flow_text = "\n".join(f"{index + 1}. {part}" for index, part in enumerate(PPT_SLIDE_FLOW))
    if d.get("slides") == 16:
        flow_rule = (
            f"Create EXACTLY 16 slides that follow this flow one-for-one (slide number = flow number):\n{flow_text}\n"
            "Fill each slide with the session's actual content. The three Lesson Content slides (6-8) split the "
            "session's main concepts into three teachable chunks."
        )
    else:
        flow_rule = (
            f"Create EXACTLY {d['slides']} slides and keep the SPIRIT of this 16-slide flow — every deck must still "
            f"start with Title, then Objectives, Motivation, Prior Knowledge, Introduction, then Lesson Content, "
            "Example, Guided Activity, Application, Higher-Order Question, Assessment, Generalization, Assignment, and Closing. "
            "Merge or split the middle Content slides to fit the requested count, never drop a stage:"
            f"\n{flow_text}"
        )
    return f"""You are an expert Philippine DepEd teacher designing a simple, lightweight classroom PowerPoint.
Lesson subject: {d.get('deck_subject') or 'unknown'}. Deck base title: {d.get('deck_base_title') or '(infer from the lesson basis)'}.
DECK SCOPE: this deck covers ONLY Session {d['session_number']}: {d['session_topic']}.
Create one standalone deck for this session only — other sessions get their own decks.
{flow_rule}

MEANINGFUL CONTENT RULE: the Lesson Content slides (and Example, Application, Generalization) must TEACH.
For every Lesson Content slide give 2 to 3 bullets, and each bullet must be a FULL paragraph of 3 to 6
complete sentences that actually explains the concept (what it means, why it matters, how it works).
NEVER write short fragments like 'Definition of X' or 'Concept 1' — write the actual meaning in words,
as if a good teacher were explaining it to the class. Other slides keep short learner-friendly lines.

DESIGN STYLE: {d.get('style') or 'Education — friendly classroom look, soft blues and greens'}.
Translate this style into a concrete, calm color theme (bg, accent, title, text as RRGGBB hex) that
suits the subject, and choose 'shape' values that match the style (e.g., petals/ovals for Floral,
clean rectangles for Business, diamonds for Research, circles/stars for Space).

PICTURES: every content slide gets a real drawn illustration generated from 'image_idea'.
Describe a simple flat scene that matches the slide topic AND the style (e.g., 'big sun with three
rays over green hills', 'rain clouds and arrows showing the water cycle', 'seed growing in three
steps in a garden', 'planets orbiting the sun in a starry sky'). Mention concrete objects (sun,
hills, water, plants, animals, stars, buildings) so the drawing is recognizable.

Respond ONLY with valid JSON, no markdown:
{{"deck_title": "string (include the session number)", "subject": "string", "theme": {{"bg": "RRGGBB hex", "accent": "RRGGBB hex", "title": "RRGGBB hex", "text": "RRGGBB hex"}}, "slides": [{{"title": "max 8 words", "bullets": ["see content rules above"], "shape": "rect|oval|triangle|diamond|arrow|none", "image_idea": "short description of a simple flat illustration matching the style"}}]}}
Rules: slide 1 is the title slide (deck_title + one subtitle bullet with subject and grade level).
Choose a color theme that is DISTINCT from decks of the other sessions (avoid harsh neon colors).
Extra teacher instructions: {d.get('note') or 'None'}
LESSON BASIS:
{basis[:20000]}
"""


# --------------------------------------------------------------------------------------
# Slide picture engine: turns the AI's 'image_idea' words into a real drawn PNG.
# Vector-style flat illustration, upscaled with anti-aliasing, JPEG-compressed —
# the whole deck stays well under the 3 MB cap.
# --------------------------------------------------------------------------------------
_TOPIC_STEMS = [
    "water", "sun", "star", "plant", "seed", "tree", "leaf", "flower", "animal", "bird", "fish",
    "earth", "moon", "cloud", "rain", "volcano", "rock", "magnet", "light", "heat", "food",
    "book", "school", "community", "family", "money", "map", "history", "health", "body", "cell",
    "atom", "energy", "force", "weather", "farm", "market", "river", "mountain", "forest", "ocean",
]

class _Pt:
    """Tiny point helper for the SVG-style renderer."""

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)

    def __add__(self, other):
        return _Pt(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return _Pt(self.x - other.x, self.y - other.y)

    def __mul__(self, factor):
        return _Pt(self.x * factor, self.y * factor)

    def rotated(self, degrees):
        angle = math.radians(degrees)
        cos, sin = math.cos(angle), math.sin(angle)
        return _Pt(self.x * cos - self.y * sin, self.x * sin + self.y * cos)


def _mix_color(hex_color, factor, toward=(255, 255, 255)):
    hex_color = re.sub(r"[^0-9a-fA-F]", "", str(hex_color or ""))[:6] or "2E6FB5"
    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(int(c + (t - c) * factor) for c, t in zip(rgb, toward))


def _pick_scene_words(text):
    words = re.findall(r"[a-zA-Z]+", str(text or "").lower())
    hits = [w for w in words if w in _TOPIC_STEMS]
    rng = random.Random(str(text or "")[:80])
    if not hits:
        hits = [rng.choice(_TOPIC_STEMS)]
    return hits[:3], rng


def _scene_plan(image_idea, rng):
    """Map idea words to a few scene elements (sky/hills/sun/plants/etc.)."""
    words = re.findall(r"[a-zA-Z]+", str(image_idea or "").lower())
    plan = {"has_sun": False, "has_cloud": False, "has_hills": False, "has_water": False,
            "has_plants": False, "has_ground": False, "has_stars": False, "has_bird": False}
    def has(*keys):
        return any(k in words for k in keys)
    plan["has_ground"] = True
    if has("sun", "light", "solar", "energy", "summer", "day"):
        plan["has_sun"] = True
    if has("cloud", "rain", "weather", "sky", "water", "cycle", "evaporation"):
        plan["has_cloud"] = True
    if has("hill", "mountain", "land", "field", "farm", "forest", "nature", "tree", "plant", "volcano"):
        plan["has_hills"] = True
    if has("water", "sea", "ocean", "river", "lake", "rain", "fish", "wave", "cycle"):
        plan["has_water"] = True
    if has("plant", "tree", "flower", "seed", "leaf", "garden", "farm", "grow", "crop"):
        plan["has_plants"] = True
    if has("space", "star", "night", "planet", "moon", "galaxy", "universe"):
        plan["has_stars"] = True
        plan["has_ground"] = False
    if has("bird", "fly", "wing", "animal"):
        plan["has_bird"] = True
    if not any((plan["has_sun"], plan["has_cloud"], plan["has_hills"], plan["has_water"], plan["has_plants"], plan["has_stars"])):
        pick = rng.choice(["sun", "hills", "water", "plants"])
        plan[f"has_{pick}"] = True
    return plan


def _draw_pic_png(size, theme, image_idea, accent_hex, bg_hex, key_text):
    """Render one flat, style-aware illustration as PNG bytes (None when Pillow is missing)."""
    if _PILImage is None:
        return None
    scale = 2
    width, height = size[0] * scale, size[1] * scale
    base = _mix_color(bg_hex, 0.35)
    img = _PILImage.new("RGB", (width, height), base)
    draw = _PILDraw.Draw(img)
    rng = random.Random(str(image_idea or "") + str(key_text or ""))
    accent = _mix_color(accent_hex, 0.0)
    accent2 = _mix_color(accent_hex, 0.35)
    accent3 = _mix_color(accent_hex, 0.6)
    scene = _scene_plan(image_idea, rng)
    words, _ = _pick_scene_words(image_idea)

    if scene["has_stars"]:
        draw.rectangle([0, 0, width, height], fill=_mix_color("101840", 0.0, toward=_mix_color(bg_hex, 0.1, toward=(0, 0, 0))))
        for _ in range(26):
            sx, sy, sr = rng.randint(6, width - 6), rng.randint(6, height - 6), rng.randint(2, 5)
            draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(240, 240, 250))
        draw.ellipse([width * 0.6, height * 0.12, width * 0.82, height * 0.34], fill=(235, 238, 250))
        draw.ellipse([width * 0.55, height * 0.08, width * 0.74, height * 0.28], fill=_mix_color(bg_hex, 0.15))
    elif scene["has_water"] and not scene["has_hills"]:
        draw.rectangle([0, 0, width, height], fill=_mix_color(accent_hex, 0.82))
        for i in range(5):
            y = height * (0.45 + 0.11 * i)
            draw.arc([width * (0.05 + 0.02 * i) - 40, y, width * (0.45 + 0.02 * i) + 40, y + 46], 200, 340, fill=(255, 255, 255), width=7)
            draw.arc([width * (0.52 + 0.02 * i) - 40, y + 12, width * (0.92 + 0.02 * i) + 40, y + 58], 200, 340, fill=(255, 255, 255), width=7)
        if scene["has_sun"]:
            draw.ellipse([width * 0.68, height * 0.06, width * 0.88, height * 0.26], fill=(255, 214, 102))
    else:
        draw.rectangle([0, 0, width, height], fill=_mix_color(bg_hex, 0.62))
        if scene["has_cloud"]:
            for cx, cy, s in ((0.24, 0.16, 1.0), (0.34, 0.12, 0.8), (0.16, 0.2, 0.7)):
                r = 26 * s * scale / 2
                draw.ellipse([width * cx - r, height * cy - r, width * cx + r, height * cy + r], fill=(255, 255, 255))
        if scene["has_sun"]:
            draw.ellipse([width * 0.72, height * 0.07, width * 0.9, height * 0.25], fill=(255, 210, 90))
            for i in range(8):
                ang = i * 45 + 22
                cx, cy = width * 0.81, height * 0.16
                dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                draw.line([cx + dx * 46, cy + dy * 46, cx + dx * 62, cy + dy * 62], fill=(255, 210, 90), width=6)
        if scene["has_bird"]:
            for bx, by in ((0.5, 0.2), (0.58, 0.28)):
                px, py = width * bx, height * by
                draw.arc([px - 18, py - 10, px + 2, py + 10], 200, 330, fill=(70, 70, 90), width=5)
                draw.arc([px - 2, py - 10, px + 18, py + 10], 210, 340, fill=(70, 70, 90), width=5)
        horizon = height * 0.66
        if scene["has_hills"]:
            draw.polygon([(0, horizon + 8), (width * 0.3, horizon - height * 0.2), (width * 0.6, horizon + 8)], fill=_mix_color(accent_hex, 0.35, toward=(60, 110, 60)))
            draw.polygon([(width * 0.35, horizon + 8), (width * 0.72, horizon - height * 0.26), (width, horizon + 8)], fill=_mix_color(accent_hex, 0.5, toward=(60, 110, 60)))
        draw.rectangle([0, horizon, width, height], fill=_mix_color(accent2, 0.55, toward=(120, 170, 110)))
        if scene["has_water"]:
            draw.rectangle([0, height * 0.78, width, height], fill=_mix_color("3E8FC4", 0.35))
            for i in range(3):
                y = height * (0.8 + 0.05 * i)
                draw.arc([width * 0.1 - 30, y, width * 0.4 + 30, y + 30], 200, 340, fill=(255, 255, 255), width=5)
        if scene["has_plants"]:
            for gx in (0.2, 0.68):
                base_x, base_y = width * gx, horizon + height * 0.06
                trunk_w = 10
                draw.rectangle([base_x - trunk_w / 2, base_y - height * 0.22, base_x + trunk_w / 2, base_y], fill=_mix_color("8A5A33", 0.1))
                for ang in (-70, -35, 0, 35, 70):
                    top = _Pt(base_x, base_y - height * 0.24)
                    tip = top + _Pt(0, -height * 0.1).rotated(ang)
                    draw.line([top.x, top.y, tip.x, tip.y], fill=_mix_color("8A5A33", 0.1), width=7)
                cy = base_y - height * 0.34
                for ang in (-60, -30, 0, 30, 60):
                    leaf = _Pt(base_x, cy) + _Pt(0, -height * 0.09).rotated(ang)
                    lx, ly = leaf.x, leaf.y
                    draw.ellipse([lx - 24, ly - 24, lx + 24, ly + 24], fill=_mix_color(accent_hex, 0.25, toward=(70, 150, 70)))
            for sx in (0.42, 0.86):
                stem_top = _Pt(width * sx, horizon + height * 0.1)
                base = _Pt(width * sx, horizon + height * 0.28)
                draw.line([base.x, base.y, stem_top.x, stem_top.y], fill=_mix_color("4E7A3A", 0.1), width=6)
                for ang in (-150, -90, -30):
                    pet = stem_top + _Pt(-16, 0).rotated(ang)
                    draw.ellipse([pet.x - 12, pet.y - 12, pet.x + 12, pet.y + 12], fill=_mix_color(accent_hex, 0.1, toward=(230, 130, 170)))
        else:
            for _ in range(3):
                gx = rng.uniform(0.08, 0.9)
                draw.ellipse([width * gx - 14, horizon + 6, width * gx + 14, horizon + 26], fill=_mix_color(accent_hex, 0.4, toward=(90, 140, 80)))

    if words and rng.random() < 0.9:
        cx, cy = width * 0.5, height * 0.42
        r = min(width, height) * 0.16
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent, outline=(255, 255, 255), width=6)
        for i in range(8):
            ang = i * 45
            tip = _Pt(cx, cy) + _Pt(0, -r * 1.9).rotated(ang)
            base = _Pt(cx, cy) + _Pt(0, -r * 1.15).rotated(ang)
            draw.line([base.x, base.y, tip.x, tip.y], fill=accent, width=8)
    img = img.resize(size, _PILImage.LANCZOS)
    img = img.filter(_PILFilter.GaussianBlur(0.4))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


def _hex_color(value, fallback):
    """Parse a 6-digit hex color safely; fall back when the model misbehaves."""
    text = re.sub(r"[^0-9a-fA-F]", "", str(value or ""))
    return RGBColor.from_string((text or fallback).upper()[:6])


_PIC_MAX_W, _PIC_MAX_H = 440, 440  # on-slide inches*96; kept small so decks stay light
_PIC_JPEG_BUDGET = 150_000  # ~146 KB per picture max; flat art lands far below, keeping decks light


def _draw_slide_picture(theme, image_idea, accent_hex, bg_hex, key_text):
    """Draw the slide's real picture (PNG→JPEG bytes), or None when Pillow is unavailable."""
    png = _draw_pic_png((_PIC_MAX_W, _PIC_MAX_H), theme, image_idea, accent_hex, bg_hex, key_text)
    if not png:
        return None
    return _shrink_picture_jpeg(png)


def _shrink_picture_jpeg(png_bytes):
    """Recompress a drawn PNG into a small JPEG so the deck never balloons in size."""
    if _PILImage is None:
        return png_bytes
    try:
        with _PILImage.open(BytesIO(png_bytes)) as img:
            quality = 88
            while quality >= 30:
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if buf.tell() <= _PIC_JPEG_BUDGET:
                    return buf.getvalue()
                quality -= 12
            return buf.getvalue()
    except Exception:
        return png_bytes


def build_presentation(plan, teacher, style=None, template_file=None):
    """Build the .pptx: style-aware theme, drawn slide pictures, ~under the 3 MB cap.

    With `template_file` (uploaded .pptx/.potx bytes), the user's own template
    carries the design: its slide size, masters, layouts, and theme are kept, its
    slides are emptied, and the AI-designed content is written onto its blankest
    layout. The AI theme colors still color the accent bar and picture frame so
    slides stay cohesive, and slide backgrounds are left as the template made them.
    """
    if Presentation is None:
        raise RuntimeError("The python-pptx package is missing. Run ILAW_TeacherTools_Setup.bat to repair the installation.")
    theme = plan.get("theme") or {}
    bg = _hex_color(theme.get("bg"), "F5F9FF")
    accent = _hex_color(theme.get("accent"), "2E6FB5")
    title_c = _hex_color(theme.get("title"), "1A3353")
    text_c = _hex_color(theme.get("text"), "333333")
    base_scale = 1.0
    if template_file:
        try:
            deck = Presentation(BytesIO(template_file))
        except Exception as exc:
            raise ValueError(f"The PPT template could not be opened ({exc}). Save it as a normal .pptx or .potx and try again.")
        # Empty the template's sample slides but keep its masters, layouts, and theme.
        slide_ids = deck.slides._sldIdLst
        for sld_id in list(slide_ids):
            try:
                deck.part.drop_rel(sld_id.rId)
            except Exception:
                pass
            slide_ids.remove(sld_id)
        # Scale the 13.33in x 7.5in design grid onto the template's slide size.
        base_scale = min(deck.slide_width / PptxInches(13.333), deck.slide_height / PptxInches(7.5))
        # Use the template's blankest layout so no placeholder ghosts linger.
        blank = min(deck.slide_layouts, key=lambda lay: (len(lay.placeholders), 0 if "blank" in (lay.name or "").lower() else 1))
    else:
        deck = Presentation()
        deck.slide_width, deck.slide_height = PptxInches(13.333), PptxInches(7.5)  # 16:9
        blank = deck.slide_layouts[6]

    def D(design_inches):
        """Convert a design-grid inch value to the deck's actual slide size."""
        return PptxInches(design_inches * base_scale)

    def add_slide(title, bullets, shape_name="none", is_title_slide=False, image_png=None):
        slide = deck.slides.add_slide(blank)
        if not template_file:
            bgfill = slide.background.fill
            bgfill.solid()
            bgfill.fore_color.rgb = bg
        box = slide.shapes.add_textbox(D(0.6), D(0.35), D(12.1), D(1.1))
        frame = box.text_frame
        frame.word_wrap = True
        paragraph = frame.paragraphs[0]
        paragraph.text = title or ""
        paragraph.font.size = PptxPt(36)
        paragraph.font.bold = True
        paragraph.font.color.rgb = title_c
        paragraph.alignment = PP_ALIGN.LEFT
        accentbar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, D(0.6), D(1.45), D(3.2), D(0.07))
        accentbar.fill.solid()
        accentbar.fill.fore_color.rgb = accent
        accentbar.line.fill.background()
        if is_title_slide and teacher:
            sub = slide.shapes.add_textbox(D(0.6), D(4.3), D(12.1), D(0.6))
            sub_frame = sub.text_frame
            sub_frame.word_wrap = True
            sub_par = sub_frame.paragraphs[0]
            sub_par.text = f"Teacher: {teacher}"
            sub_par.font.size = PptxPt(20)
            sub_par.font.color.rgb = accent
            sub_par.alignment = PP_ALIGN.LEFT
        body = slide.shapes.add_textbox(D(0.9), D(1.85), D(8.2 if not image_png else 7.7), D(5.1))
        body_frame = body.text_frame
        body_frame.word_wrap = True
        first = True
        for bullet in (bullets or [])[:6]:
            paragraph = body_frame.paragraphs[0] if first else body_frame.add_paragraph()
            first = False
            paragraph.text = f"• {str(bullet)[:120]}"
            paragraph.font.size = PptxPt(20)
            paragraph.font.color.rgb = text_c
            paragraph.space_after = PptxPt(10)
        shape_map = {"oval": MSO_SHAPE.OVAL, "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE, "diamond": MSO_SHAPE.DIAMOND, "arrow": MSO_SHAPE.RIGHT_ARROW}
        shape_type = shape_map.get(str(shape_name or "none").lower())
        if image_png:
            # Real drawn picture, framed with an accent border for a polished look.
            framepad = PptxInches(0.09)
            frame = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, D(8.96), D(2.06),
                                           D(4.13), D(4.13))
            frame.fill.solid()
            frame.fill.fore_color.rgb = accent
            frame.line.fill.background()
            frame.adjustments[0] = 0.045
            try:
                frame.shadow.inherit = False
            except Exception:
                pass
            slide.shapes.add_picture(BytesIO(image_png), D(9.05), D(2.15), width=D(3.95), height=D(3.95))
        elif shape_type is not None:
            decor = slide.shapes.add_shape(shape_type, D(9.6), D(2.3), D(2.9), D(2.9))
            decor.fill.solid()
            decor.fill.fore_color.rgb = accent
            decor.line.fill.background()
            try:
                decor.shadow.inherit = False
            except Exception:
                pass
        return slide

    total_deck_budget = 2_700_000  # stay safely under the requested 3 MB deck ceiling
    for index, slide_plan in enumerate(plan.get("slides", [])):
        idea = str(slide_plan.get("image_idea") or "").strip()
        pic = _draw_slide_picture(theme, idea, str(theme.get("accent") or "2E6FB5"), str(theme.get("bg") or "F5F9FF"),
                                  f"{index}-{slide_plan.get('title', '')}") if idea else None
        slide = add_slide(slide_plan.get("title", f"Slide {index + 1}"), slide_plan.get("bullets", []), slide_plan.get("shape", "none"),
                          is_title_slide=index == 0, image_png=pic)
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


def generate_session_topic(basis):
    """Ask the AI to split the lesson basis into its sessions and return session metadata.

    Returns a list of {"session": int, "topic": str} dicts — one per session found.
    """
    prompt = f"""Read the ILAW lesson plan below and list its teaching sessions.
Respond ONLY with valid JSON, no markdown:
{{"subject": "string", "deck_base_title": "short lesson title", "sessions": [{{"session": 1, "topic": "main topic of this session in a few words"}}]}}
Include EVERY session found in the plan, in teaching order. The topic must be specific to that session,
not a repeat of the lesson title.
LESSON BASIS:
{basis[:15000]}
"""
    data = _ask_and_parse(prompt, {"response_mime_type": "application/json", "temperature": 0.2, "max_output_tokens": 8192})
    sessions = data.get("sessions") or []
    if isinstance(sessions, dict):
        sessions = list(sessions.values())
    cleaned = []
    for index, item in enumerate(sessions, 1):
        if isinstance(item, dict) and str(item.get("topic", "")).strip():
            cleaned.append({"session": int(item.get("session") or index), "topic": str(item.get("topic")).strip()})
    if not cleaned:
        raise ValueError("No sessions with topics were found in the uploaded lesson plan. Make sure the file lists its sessions and topics.")
    cleaned.sort(key=lambda item: item["session"])
    return data, cleaned


def generate_ppt_plan(basis, d):
    """Ask the AI for a lightweight slide plan grounded in the uploaded ILAW."""
    prompt = make_ppt_prompt(basis, d)
    plan = _ask_and_parse(prompt, {"response_mime_type": "application/json", "temperature": 0.4, "max_output_tokens": 16384})
    plan["_prompt"] = prompt
    return plan


# ---------------------------------------------------------------------------
# ILAW-LIL — Lesson Implementation Log. One session per log, generated from an
# uploaded Lesson Exemplar (PDF/Word/Excel). Same 3-option pick flow as the ILAW
# tab; the export fills the DepEd LESSON IMPLEMENTATION LOG template in place.
# ---------------------------------------------------------------------------
LIL_SCHEMA = {
    "log_title": "string", "overview": "string",
    "component": "string",
    "learning_competency": "exact competency text taken from the Lesson Exemplar; never invent codes",
    "sessions": [{
        "session": "Session 1", "topic": "one topic string",
        "learning_objectives": "one string; each objective on its own '- ' line",
        "learning_resources": "one string; official learning resources for the session (one per '- ' line); the Lesson Exemplar itself is always first",
        "flow": "one string; in-class sequence; each strategy-model phase on its own line as 'Phase: full-sentence paragraph'; the activities inside each phase come from the Lesson Exemplar — original names, sequence, and content",
        "learning_experience": "one string; the Lesson Exemplar or instructional material utilized including title/pages, activities and tasks",
        "assessing_learning": "one string; the formative assessment administered (e.g., Oral Questioning, Exit Ticket, Written Quiz) with the actual items or prompts",
        "ways_forward": "one string; lines among: Proceed as planned, Reteach, Remediation, Enrichment, Modify next lesson, Other instructional adjustments",
        "worked_well": "one string; what worked well during the instruction",
        "remediation": "one string; learners requiring remediation/intervention (names are NOT known to the AI, describe groups/needs only)",
        "enrichment": "one string; learners ready for enrichment (describe groups/needs only)",
        "adjustments": "one string; instructional adjustments for the succeeding week",
    }],
}

LIL_SESSION_FIELDS = [
    ("topic", "Topic"),
    ("learning_objectives", "Learning objectives (one per line)"),
    ("learning_resources", "Learning Resources / Learning Exemplars"),
    ("flow", "Flow"),
    ("learning_experience", "Learning Experience (L)"),
    ("assessing_learning", "Assessing Learning (A)"),
    ("ways_forward", "Ways Forward (W)"),
    ("worked_well", "Reflection: What worked well"),
    ("remediation", "Reflection: Learners requiring remediation/intervention"),
    ("enrichment", "Reflection: Learners ready for enrichment"),
    ("adjustments", "Reflection: Instructional adjustments for the succeeding week"),
]


def make_lil_prompt(d):
    """Prompt for one Lesson Implementation Log session from the uploaded exemplar."""
    phases = ', '.join(_strategy_phases(d['strategy']))
    return f"""You are an expert Philippine DepEd teacher creating a DRAFT Lesson Implementation Log (LIL) based on a Lesson Exemplar.
A Lesson Implementation Log documents what was implemented in class based on a Lesson Exemplar.
READ THE ENTIRE LESSON EXEMPLAR THOROUGHLY — it contains one or more complete lessons with their
objectives, activities, and assessment items. Use it as the sole basis: copy the learning competency,
objectives, activities, and assessment items from it as closely as possible — never invent content
that is not in the exemplar. Do not invent learner names: when learners are described, refer to groups
or needs only.
PRIMARY SOURCE RULE: Use the Lesson Exemplar as the primary source. Do not invent activities,
strategies, learning competencies, or assessment tasks that are not supported by the exemplar. You
may distribute the exemplar's existing activities across the specified number of instructional days
({d['sessions']} sessions), but preserve the original activity names, sequence, and content. The
required teaching strategy model only structures the FLOW phases — the activities you place inside
each phase must be the exemplar's own activities, under their original names and in their original
sequence.
Required teaching strategy model: {d['strategy']}. The FLOW must explicitly use this model's phases in
their logical order. FORMAT: write EACH phase of {d['strategy']} on its own line as 'PhaseName: paragraph'.
{CURRICULUM_SOURCE_PRIORITY}
{STRICT_CURRICULUM_VERIFICATION}
The phases of {d['strategy']} are exactly: {phases}. Never merge two phases into one paragraph — every
phase starts on a FRESH line with its 'PhaseName:' label; each paragraph is 2 to 5 full sentences.
No numbering, no asterisks, no markdown; the 'Label:' prefix and line breaks are the only formatting.
- ways_forward: respond as lines, one per option, e.g. '- Proceed as planned' — pick the realistic one
  first, then alternatives. When enrichment is realistic, prepare a HIGHER-LEVEL activity or
  enhancement for the next lesson.
- learning_objectives: unpack the exemplar's competency into SMART objectives. Do NOT go beyond the
  Bloom's taxonomy level of the learning competency. Cover Knowledge, Skills, and Attitude (KSA).
- assessing_learning: the assessment MUST directly address the session's learning objectives — every
  objective is measurable by at least one item or task from the exemplar.
SOURCE FIDELITY — before writing anything, review the log against the Lesson Exemplar:
- Verify every Learning Competency, Objective, Activity, Assessment, Strategy, and Ways Forward is
  supported by the selected lesson in the exemplar; identify anything taken from another lesson;
  identify anything invented or unsupported; REMOVE unsupported content; preserve the exemplar's
  original activity titles and numbers; and make sure the Component is NOT merely a repetition of
  the Learning Area.
- Return only the corrected LIL.
Extra teacher instructions (follow these unless they conflict with the rules above): {d.get('note') or 'None'}
Respond ONLY with valid JSON matching this schema, with no markdown or extra keys:
{json.dumps(LIL_SCHEMA)}
Learning area: {d['area']}; Teacher: {d['teacher'] or 'Not specified'}; Term/Week: {d['termweek']}
Produce exactly {d['sessions']} session object(s) in the "sessions" array — numbered "Session 1" to
"Session {d['sessions']}" — one Lesson Implementation Log per session, in teaching order.
LESSON EXEMPLAR TEXT:
{d['exemplar'][:60000]}
"""


def generate_lil(api_key, details):
    """Generate the LIL draft (3 options per cell) from the uploaded Lesson Exemplar."""
    details["ai_provider"] = st.session_state.get("provider", _DEFAULT_PROVIDER)
    plan = _ask_and_parse(make_lil_prompt(details),
                          {"response_mime_type": "application/json", "temperature": 0.35})
    _raise_if_curriculum_refusal(plan)
    expected = int(details.get("sessions") or len(_sessions_from_plan(plan)) or 1)
    plan = _enforce_session_count(plan, expected, make_lil_prompt(details) + (
        f"\nCRITICAL: your previous answer had the wrong number of session objects. Return ONLY the "
        f"JSON schema with exactly {expected} session object(s), numbered Session 1 to Session {expected}.\n"))
    # Review & correction pass — verify the draft against the Lesson Exemplar and
    # return only the corrected log.
    try:
        with st.spinner("Reviewing the log against the Lesson Exemplar before showing it..."):
            corrected = _ask_and_parse(
                make_lil_review_prompt(details, plan),
                {"response_mime_type": "application/json", "temperature": 0.15})
        if isinstance(corrected, dict) and _sessions_from_plan(corrected):
            corrected = _enforce_session_count(corrected, expected,
                                               make_lil_review_prompt(details, corrected) +
                                               f"\nCRITICAL: your corrected answer had the wrong number of session objects. Return ONLY the JSON schema with exactly {expected} session object(s).\n")
            plan = corrected
    except Exception:
        pass  # the draft stands if the review call fails (quota, network, etc.)
    sessions = plan["sessions"]
    for index, session in enumerate(sessions):
        session.setdefault("session", f"Session {index + 1}")
        for field, _ in LIL_SESSION_FIELDS:
            session[field] = _ensure_single_text(session.get(field), field,
                                                 fallback="- Proceed as planned" if field == "ways_forward" else "")
    for field in ("log_title", "overview", "component", "learning_competency"):
        plan[field] = _ensure_single_text(plan.get(field), field)
    return plan


def lil_export(plan, d, picks=None):
    """Fill the DepEd LESSON IMPLEMENTATION LOG template with ALL sessions.

    The template has five session columns (C to G) under the Day headers — one
    generated session goes into each column, in teaching order, so ONE Excel file
    carries the whole week. The template's header (logo, division lines), yellow
    label cells, per-row guide texts, and the REMINDER block are preserved
    untouched: only blank detail cells receive AI content. Dates and times stay
    blank; Term/Week is the joined user input; the teacher's name goes to
    'Prepared by'.
    """
    if not LIL_TEMPLATE.exists():
        raise FileNotFoundError("The Lesson Implementation Log template is missing from the app folder.")

    def picked(options, pick_index=None):
        """Read one field value; accepts both the new single-string shape and the
        legacy 3-option list (option 1 = what is shown/exported)."""
        options = options if isinstance(options, list) else [options]
        options = [str(item) for item in options if str(item).strip()]
        if not options:
            return ""
        if isinstance(pick_index, int) and 0 <= pick_index < len(options):
            return clean_cell_text(options[pick_index])
        return clean_cell_text(options[0])

    workbook = load_workbook(LIL_TEMPLATE)
    sheet = workbook.active
    sessions = plan.get("sessions") or [{}]
    picks = picks or {}

    def shown(session_index, field):
        item = sessions[session_index] if session_index < len(sessions) else {}
        options = item.get(field) if isinstance(item, dict) else None
        return picked(options, picks.get((session_index, field)))

    def write(coord, value):
        """Write only cells that are blank in the template — never yellow label cells."""
        cell = sheet[coord]
        fill = cell.fill
        is_yellow = (fill is not None and fill.patternType == "solid"
                     and getattr(fill.start_color, "rgb", None) not in (None, "00000000", "FFFFFFFF"))
        if is_yellow:
            raise ValueError(f"Refusing to overwrite the yellow template cell {coord}.")
        cell.value = value

    write("E10", d["teacher"] or "")        # after the 'Teacher:' label
    write("G10", d["area"])                  # after the 'Learning Area:' label
    write("B11", d["grade"])
    write("E11", d["termweek"])             # Term/Week joined during export
    write("G11", "")                         # Dates/Time left blank by design
    # INTENTIONS — competency spans the week (template merges C15:G15); component
    # goes to the first column. Per-session detail cells are C18..G28, one column
    # per session.
    write("C14", clean_cell_text(plan.get("component") or ""))
    write("C15", clean_cell_text(first_option(plan.get("learning_competency"))))
    # WEEKLY IMPLEMENTATION LOG + INTENTIONS detail — one session per column C..G.
    for column_index in range(5):
        column = "CDEFG"[column_index]
        write(f"{column}18", shown(column_index, "learning_objectives"))
        write(f"{column}19", bold_references_rich(shown(column_index, "learning_resources"), template=LIL_TEMPLATE, cell=f"{column}19"))
        write(f"{column}21", bold_flow_rich(shown(column_index, "flow"), template=LIL_TEMPLATE, cell=f"{column}21"))
        write(f"{column}22", shown(column_index, "assessing_learning"))
        write(f"{column}23", format_references_text(shown(column_index, "ways_forward")))
        write(f"{column}25", shown(column_index, "worked_well"))
        write(f"{column}26", shown(column_index, "remediation"))
        write(f"{column}27", shown(column_index, "enrichment"))
        write(f"{column}28", shown(column_index, "adjustments"))
    if (d["teacher"] or "").strip():
        write("A31", d["teacher"].strip())   # 'Prepared by' name; template placeholder kept when blank
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def generate(api_key, details):
    details["ai_provider"] = st.session_state.get("provider", _DEFAULT_PROVIDER)
    if not details["bow"]:
        research_note, online_sources = find_competency_online(details)
        details["bow"] = "ONLINE RESEARCH NOTE — verify before use:\n" + research_note
        details["reference_source"] = (
            "Google Search grounding" if details["ai_provider"] == _DEFAULT_PROVIDER
            else f"{details['ai_provider']} AI research note"
        ) + "; teacher verification required."
        details["online_sources"] = online_sources
        details["online_research_note"] = research_note
    else:
        details["reference_source"] = "Budget of Work (BOW) PDF uploaded by teacher."
    plan = _ask_and_parse(make_prompt(details),
        {"response_mime_type": "application/json", "temperature": 0.35},
    )
    _raise_if_curriculum_refusal(plan)
    expected = int(details.get("sessions") or len(_sessions_from_plan(plan)) or 1)
    plan = _enforce_session_count(plan, expected, make_prompt(details) + (
        f"\nCRITICAL: your previous answer had the wrong number of session objects. Return ONLY the "
        f"JSON schema with exactly {expected} session objects, numbered Session 1 to Session {expected}.\n"))
    # Review & correction pass — verify the draft against the BOW (or the public
    # DepEd curriculum when no BOW was uploaded) and return only the corrected plan.
    try:
        with st.spinner("Reviewing the plan against the BOW/source before showing it..."):
            corrected = _ask_and_parse(
                make_review_prompt(details, plan),
                {"response_mime_type": "application/json", "temperature": 0.15})
        if isinstance(corrected, dict) and _sessions_from_plan(corrected):
            corrected = _enforce_session_count(corrected, expected,
                                               make_review_prompt(details, corrected) +
                                               f"\nCRITICAL: your corrected answer had the wrong number of session objects. Return ONLY the JSON schema with exactly {expected} session objects.\n")
            plan = corrected
    except Exception:
        pass  # the draft stands if the review call fails (quota, network, etc.)
    sessions = plan["sessions"]
    for index, session in enumerate(sessions):
        session.setdefault("session", f"Session {index + 1}")
        for field in EDITABLE_SESSION_FIELDS:
            fallback = "N/A" if field == "integration" else ""
            if field == "learning_objectives":
                fallback = "- Objectives not returned"
            session[field] = _ensure_single_text(session.get(field), field, fallback)
    for field in ("lesson_title", "overview", "standards_and_competency"):
        plan[field] = _ensure_single_text(plan.get(field), field)
    return plan


# Characters Excel forbids inside worksheet XML (openpyxl raises "cannot be used
# in worksheets"). Models like Mistral emit LaTeX with form feeds ('\f\frac'),
# vertical tabs, and other control bytes inside their JSON strings.
_ILLEGAL_XLSX_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_cell_text(text):
    """Remove XML-illegal control characters, keeping newlines and tabs."""
    return _ILLEGAL_XLSX_RE.sub("", str(text or ""))


def cell_text(value):
    """Convert Gemini JSON values into a value Excel can store in one cell."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n\n".join(cell_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(f"{key.replace('_', ' ').title()}: {cell_text(item)}" for key, item in value.items())
    return clean_cell_text(value)


LABEL_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 '’\-]{0,40}?)\s*:\s*(.+)$", re.S)

# Reference lines: 'Book Title, Author, Page N' or 'Website Name, URL: link'
_BOOK_REF_RE = re.compile(r"^(?P<title>[^,\n]{2,120}),\s*(?P<author>[^,\n]{2,120}),\s*(?P<page>(?:(?:p|pp|page|pages)\.?\s*[\d\u2013\-,\s]+|[^,\n]*not\s+stated[^,\n]*))$", re.I)
_SITE_REF_RE = re.compile(r"^(?P<name>[^,\n]{2,120}),\s*(?:URL:\s*)?(?P<url>(?:https?://|www\.)\S+)$", re.I)


def format_references_text(text):
    """Normalize a references block: each reference on its own bullet line.

    Books stay as 'Title, Author, Page N'; websites as 'Website Name, URL: link'.
    Handles blobs, markdown leftovers, and multi-line entries alike.
    """
    value = clean_cell_text(str(text or "").strip())
    if not value:
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", value)
    out = []
    for raw in value.split("\n"):
        line = raw.strip().lstrip("-• ").strip()
        if not line:
            continue
        out.append(f"• {line}" if not line.startswith("•") else line)
    return "\n".join(out)


def bold_references_rich(text, template=None, cell="B23"):
    """Rich text for the References row: the reference itself on each bullet line.

    For books, the Title is bold; for websites, the Site Name is bold. Excel-valid
    runs only (explicit fonts, no empty rPr, no newline-only runs).
    """
    plain = format_references_text(text)
    if not plain:
        return ""
    font_name, font_size = _flow_base_font(template, cell)
    font_size = 12.0
    label_font = InlineFont(rFont=font_name, sz=font_size, b=True)
    body_font = InlineFont(rFont=font_name, sz=font_size, b=False)
    entries = [line.strip()[2:].strip() if line.strip().startswith("• ") else line.strip()
               for line in plain.split("\n") if line.strip()]
    if len(entries) == 1:
        match = _BOOK_REF_RE.match(entries[0]) or _SITE_REF_RE.match(entries[0])
        if match:
            bold_part = match.group("title") if "title" in match.groupdict() else match.group("name")
            return CellRichText(TextBlock(label_font, bold_part),
                                TextBlock(body_font, entries[0][len(bold_part):]))
        return entries[0]
    rich = CellRichText()
    last = len(entries) - 1
    for index, entry in enumerate(entries):
        head, sep, tail = entry.partition(": ")
        match = _BOOK_REF_RE.match(entry) or _SITE_REF_RE.match(entry)
        bullet = "• "
        if match:
            bold_part = match.group("title") if "title" in match.groupdict() else match.group("name")
            rich.append(TextBlock(body_font, f"{bullet}"))
            rich.append(TextBlock(label_font, bold_part))
            rest = entry[len(bold_part):]
            rich.append(TextBlock(body_font, f"{rest}\n" if index < last else rest))
        elif sep:
            rich.append(TextBlock(body_font, f"{bullet}"))
            rich.append(TextBlock(label_font, head))
            rich.append(TextBlock(body_font, f": {tail}\n" if index < last else f": {tail}"))
        else:
            rich.append(TextBlock(body_font, f"{bullet}{entry}\n" if index < last else f"{bullet}{entry}"))
    return rich


_FLOW_LABELS = [
    # multi-word labels first so the regex prefers them over their one-word tails
    "Guided Practice", "Independent Practice", "Group Work", "Warm-up", "Warmup",
    "I Do", "We Do", "You Do",
    "Modeling", "Orientation", "Demonstration",
    # 4As / 5Es / 7Es
    "Elicit", "Engage", "Explore", "Explain", "Elaborate", "Evaluate", "Extend",
    "Activity", "Analysis", "Abstraction", "Application",
    # 5Ps Model
    "Preparation", "Presentation", "Practice", "Production", "Performance",
    # Inquiry-Based Learning
    "Question", "Hypothesis", "Investigation", "Evidence", "Conclusion",
    # Experiential Learning Cycle
    "Experience", "Reflection", "Conceptualization", "Experimentation",
    # Direct Instruction and generic procedure steps
    "Lecture", "Input", "Model", "Motivation", "Drill", "Review", "Discussion",
    "Sharing", "Processing", "Generalization", "Closure", "Hook",
]
_FLOW_LABEL_RE = re.compile(r"(?i)(?<![A-Za-z])(" + "|".join(re.escape(label) for label in _FLOW_LABELS) + r")\s*:\s*")


def format_flow_text(text):
    """Normalize flow text to bullet form: each model phase on its own 'Label: paragraph' line.

    Works whether the phases arrive as one long blob, pre-lineated, or mixed — every
    'Label:' occurrence starts its own line so 4Es/5Es/7Es all render as bullets.
    """
    value = clean_cell_text(str(text or "").strip())
    if not value:
        return ""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", value)            # leftover **bold** markers first
    value = re.sub(r"^\s*[*•\-]\s*", "", value, flags=re.M)          # then stray bullets/dashes
    out_lines = []
    for raw_line in value.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        parts = _FLOW_LABEL_RE.split(line)
        if len(parts) >= 3:
            # A dangling fragment before the first label ('Guide' + 'Question: ...')
            # re-joins that label; otherwise it glues to the previous bullet.
            lead = parts[0].strip()
            start = 1
            if lead:
                if out_lines:
                    out_lines[-1] = f"{out_lines[-1]} {lead}"
                else:
                    out_lines.append(f"{lead} {parts[1].strip().title()}: {parts[2].strip()}")
                    start = 3
            for i in range(start, len(parts) - 1, 2):
                out_lines.append(f"{parts[i].strip().title()}: {parts[i + 1].strip()}")
        elif out_lines:
            # Wrapped continuation (no phase label) — glue it back onto the previous bullet.
            out_lines[-1] = f"{out_lines[-1]} {line}"
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def flow_html(text):
    """Flow as safe HTML for the pick grid: bold label + bullet per phase, one line each."""
    import html as _html
    lines = [line for line in format_flow_text(text).split("\n") if line.strip()]
    pieces = []
    for line in lines:
        match = LABEL_LINE_RE.match(line)
        if match:
            pieces.append(f"&bull; <b>{_html.escape(match.group(1))}:</b> {_html.escape(match.group(2))}")
        else:
            pieces.append(f"&bull; {_html.escape(line)}")
    return "<br>".join(pieces)


_BASE_FLOW_FONT = {}


def _flow_base_font(template=None, cell="B23"):
    """Read a template's body font once so rich runs inherit the sheet's own look."""
    key = (str(template or TEMPLATE), cell)
    if key not in _BASE_FLOW_FONT:
        try:
            font = load_workbook(template or TEMPLATE).active[cell].font
            _BASE_FLOW_FONT[key] = (font.name or "Calibri", float(font.size or 11))
        except Exception:
            _BASE_FLOW_FONT[key] = ("Calibri", 11.0)
    return _BASE_FLOW_FONT[key]


def bold_flow_rich(text, template=None, cell="B23"):
    """Return openpyxl rich text with the phase label bold, e.g. **Activity:** paragraph.

    Excel-valid by construction: the newline lives INSIDE a run that has real content
    (never a newline-only run), and every run carries explicit font properties — a bare
    ``<rPr/>``, an all-default run, or an unpreserved ``<t>\n</t>`` makes Excel
    "repair" the sheet (Repaired Records: String properties).
    """
    plain = format_flow_text(text)
    if not plain:
        return ""
    font_name, font_size = _flow_base_font(template, cell)
    lines = []
    for line in plain.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = LABEL_LINE_RE.match(line)
        lines.append((match.group(1).strip(), match.group(2).strip()) if match else ("", line))
    if len(lines) == 1 and not lines[0][0]:
        return lines[0][1]
    rich = CellRichText()
    label_font = InlineFont(rFont=font_name, sz=font_size, b=True)
    body_font = InlineFont(rFont=font_name, sz=font_size, b=False)
    last_index = len(lines) - 1
    for index, (label, body) in enumerate(lines):
        if label:
            rich.append(TextBlock(label_font, f"{label}: "))
        body_text = f"{body}\n" if index < last_index else body
        rich.append(TextBlock(body_font, body_text))
    return rich


def excel_export(plan, d, picks=None):
    if not TEMPLATE.exists():
        raise FileNotFoundError("The ILAW Excel template is missing from the app folder.")

    def picked(options, pick_index=None):
        """Read one field value; accepts both the new single-string shape and the
        legacy 3-option list (option 1 = what is shown/exported)."""
        options = options if isinstance(options, list) else [options]
        options = [str(item) for item in options if str(item).strip()]
        if not options:
            return ""
        if isinstance(pick_index, int) and 0 <= pick_index < len(options):
            return clean_cell_text(options[pick_index])
        return clean_cell_text(options[0])

    workbook = load_workbook(TEMPLATE)
    sheet = workbook["WEEKLY LESSON PLAN"]
    picks = picks or {}  # [LEGACY] old 3-option picks; single-output plans ignore them
    sheet["B8"], sheet["B9"], sheet["B10"] = first_option(plan.get("lesson_title")), d["area"], d["teacher"]
    sheet["B11"], sheet["B12"], sheet["B13"] = d["grade"], d["week"], d["sessions"]
    # Declaration of AI use — DO 3 s.2026 Annex A wording; only the teacher's name,
    # the AI used, and the learning area are filled in.
    ai_name = d.get("ai_provider", "AI tools")
    teacher_name = str(d.get("teacher") or "").strip() or "Name of the Teacher"
    sheet["B15"] = (
        f"Consistent with the policy guidelines on the use of AI in basic education, I, {teacher_name}, "
        f"hereby declare that I have used AI tools to assist in the preparation and delivery of teaching and "
        f"learning materials. I used {ai_name} to generate the {d['area']} Lesson Plan for the purposes of "
        "lesson planning, content generation, and assessment structuring. The prompt(s) used were Curriculum "
        "unpacking and ILAW flow generation prompts. I affirm that the use of AI tools was intended solely to "
        "enhance the quality of instructional material, align with curriculum standards, and support the "
        "teaching and learning process. All outputs have been reviewed, adapted, edited, and validated using "
        "my professional expertise and agency to ensure accuracy, appropriateness, and alignment with "
        "learners' developmental needs/levels.\n\nLikewise, I affirm that no confidential learner information "
        "or sensitive institutional information/data was shared with the AI platform/app identified above in "
        "the process.\n\nSee DO 3 s.2026 Annex A."
    )
    # References: one real reference per session (from that session's learning resources),
    # plus grounded web sources and the competency source when available.
    references = []
    for item in plan.get("sessions", []):
        raw = first_option(item.get("learning_resources")) if isinstance(item, dict) else ""
        for line in str(raw or "").split("\n"):
            line = re.sub(r"^[-•\s]*", "", line.strip()).strip()
            if _BOOK_REF_RE.match(line) or _SITE_REF_RE.match(line):
                references.append(line)
                break
    if d.get("online_sources"):
        references.extend(f"{source['title']}, URL: {source['url']}" for source in d["online_sources"][:4])
    if d.get("bow_filename"):
        references.append(f"Uploaded BOW file: {d['bow_filename']}")
    if not references:
        references.append(f"{d.get('reference_source', 'Competency source not recorded')} Term: {d['term']}; Week: {d['week']}.")
    sheet["B16"] = bold_references_rich("\n".join(f"- {ref}" for ref in references))
    sheet["B18"] = cell_text(plan.get("standards_and_competency", ""))
    sheet["B20"] = clean_cell_text(d["context"]) or "Consider learners' prior knowledge, interests, languages, and support needs."
    columns = ["B", "C", "D", "E", "F"]
    for index, column in enumerate(columns):
        item = plan.get("sessions", [])[index] if index < len(plan.get("sessions", [])) else {}
        sheet[f"{column}14"] = item.get("session", f"SESSION {index + 1}") if item else ""
        sheet[f"{column}19"] = cell_text(picked(item.get("learning_objectives"), picks.get((index, "learning_objectives")))) if item else ""
        sheet[f"{column}22"] = cell_text(picked(item.get("pre_lesson"), picks.get((index, "pre_lesson")))) if item else ""
        sheet[f"{column}23"] = bold_flow_rich(picked(item.get("flow"), picks.get((index, "flow")))) if item else ""
        sheet[f"{column}24"] = bold_references_rich(picked(item.get("learning_resources"), picks.get((index, "learning_resources")))) if item else ""
        sheet[f"{column}25"] = cell_text(picked(item.get("integration"), picks.get((index, "integration")))) if item else ""
        sheet[f"{column}27"] = cell_text(picked(item.get("formative_assessment"), picks.get((index, "formative_assessment")))) if item else ""
        sheet[f"{column}29"] = cell_text(picked(item.get("extended_learning"), picks.get((index, "extended_learning")))) if item else ""
        sheet[f"{column}30"] = cell_text(picked(item.get("reflection"), picks.get((index, "reflection")))) if item else ""
    # Preserve the wide-column sizing and visual structure supplied by the template.
    for column in columns:
        for row in (14, 19, 22, 23, 24, 25, 27, 29, 30):
            cell = sheet[f"{column}{row}"]
            alignment = copy(cell.alignment)
            alignment.wrap_text = True
            alignment.vertical = "top"
            cell.alignment = alignment
    # TERM/WEEK in the template's own A12 label row (B12 is a merged B12:F12 cell).
    sheet["B12"] = f"{d['term']} / {d['week']}"
    # Auto-fit every content row so the full text is visible without manual resizing:
    # estimate one text line per ~55 characters of a 41-wide column and add padding.
    for row in (15, 16, 18, 19, 20, 22, 23, 24, 25, 27, 29, 30):
        value = sheet[f"B{row}"].value
        plain_len = len(str(value)) if value is not None else 0
        if isinstance(value, CellRichText):
            plain_len = len("".join(str(block.text) for block in value))
        extra = max(len(str(sheet[f"{col}{row}"].value or "")) for col in ("C", "D", "E", "F"))
        lines = max(1, math.ceil(max(plain_len, extra) / 55))
        sheet.row_dimensions[row].height = min(409.0, max(30.0, lines * 15.0 + 8))
    # Keep the declaration (B15) and references (B16) body text readable.
    for ref in ("B15", "B16"):
        font = sheet[ref].font
        sheet[ref].font = Font(name=font.name, size=max(11.0, float(font.size or 11)))
    for column in columns:
        for row in (14, 19, 22, 23, 24, 25, 27, 29, 30):
            cell = sheet[f"{column}{row}"]
            font = cell.font
            if float(font.size or 11) < 11.0:
                cell.font = Font(name=font.name, size=11.0, bold=font.bold, italic=font.italic)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output.getvalue()


def show_plan(plan):
    """Read-only single-result view of the reviewed ILAW plan."""
    st.subheader(first_option(plan.get("lesson_title"), "ILAW Lesson Plan"))
    st.info(first_option(plan.get("overview")))
    st.write(f"**Standards and competency:** {first_option(plan.get('standards_and_competency'))}")
    st.caption(f"Teaching Strategy Model: {st.session_state.details.get('strategy', '')}")
    for index, item in enumerate(plan.get("sessions", [])):
        session_label = item.get("session", f"Session {index + 1}")
        with st.expander(f"🧩 {session_label}: {first_option(item.get('topic'))}", expanded=index == 0):
            for field, label in PLAN_SESSION_FIELDS:
                st.markdown(f"**{label}**")
                body = first_option(item.get(field))
                if field == "flow":
                    st.markdown(flow_html(body), unsafe_allow_html=True)
                elif field == "learning_resources":
                    import html as _html
                    st.markdown("<br>".join(_html.escape(line) for line in format_references_text(body).split("\n")), unsafe_allow_html=True)
                else:
                    st.markdown(body.replace("\n", "  \n"))


st.title("📚 DepEd Teacher Tools Generator")
st.caption("Developed by: Jose Dennis Plaza Chua")
st.caption(f"Version {_APP_VERSION}")
with st.sidebar:
    st.header("AI Provider Hub")
    st.caption(f"v{_APP_VERSION}")
    provider = st.selectbox("AI provider", list(PROVIDERS), index=list(PROVIDERS).index(_DEFAULT_PROVIDER),
                            help="All providers work identically in this app. Each has a free tier and its own separate quota, so switching provider also switches quota pools.")
    st.session_state["provider"] = provider
    cfg = PROVIDERS[provider]
    initial = initial_api_key() if provider == _DEFAULT_PROVIDER else st.session_state.get("keys", {}).get(provider, "")
    api_key = st.text_input(cfg["key_label"], value=initial, type="password",
                            help="Stored only for this browser session; never saved by the app.")
    keys = st.session_state.setdefault("keys", {})
    keys[provider] = api_key
    st.session_state["api_key"] = api_key
    if st.session_state.get("model_used"):
        st.caption(f"Using model: {st.session_state['model_used']}")
    st.caption("Free tiers are limited per minute and per day — a quota (429) error usually means today's limit is spent. Just switch provider above and paste that provider's key; every provider generates the same outputs.")
    st.caption("Your API key and uploads are not saved by this app.")
    with st.expander("🔑 How to get an API key (small guide)"):
        st.markdown(
            f"1. Click the button below — it opens the official **{provider}** API-key page.\n"
            "2. Sign in with your account (a Google account for Gemini).\n"
            "3. Click **Create API key** / **Create key** and copy it.\n"
            "4. Paste it in the key box above.\n\n"
            "Free tiers: Gemini and Groq keys are free instantly; OpenRouter shows free models at cost 0; Mistral has a free experimental tier."
        )
        st.link_button(f"Get a {provider} API key", cfg["key_url"], use_container_width=True)
    with st.expander("⚙️ AI model (optional)"):
        model_choice = st.selectbox("Model", list(cfg["models"]), index=0,
                                    help="'Auto pick' skips busy or exhausted models automatically. 'Fast' models answer quicker; 'Quality' models think more but are slower. This list can change as providers update their models.")
        st.session_state["model_choice"] = model_choice
        chosen_model = cfg["models"].get(model_choice, "auto")
        if chosen_model != "auto":
            st.caption(f"Requests will use **{chosen_model}** first, with the provider's other models kept as automatic fallback.")
        else:
            st.caption("The app picks the first working model each time and skips busy or exhausted ones automatically.")
    if st.button("🔎 Test this key", use_container_width=True,
                 help="Sends one tiny test request to check the key, account access, and model availability before you generate anything."):
        try:
            with st.spinner(f"Testing {provider} key..."):
                ask_ai("Reply with the single word OK.", {"max_output_tokens": 512})
            st.success(f"Key works. ({st.session_state.get('model_used', provider)})")
        except Exception as test_exc:
            st.error(f"Key test failed: {test_exc}")

    # ------------------------------------------------------------------
    # Teacher feedback — insert-only into feedback.xlsx next to the app,
    # and automatically into the owner's Google Sheet through their Google
    # Form (anonymous posts, zero setup for users). No URL entry anywhere.
    # ------------------------------------------------------------------
    with st.expander("💬 Feedback & suggestions"):
        st.caption("Insert-only: every submission is appended as a new row — existing rows are never edited. "
                   "Sends automatically to the developer's Google Form and Google Sheet.")
        fb_name = st.text_input("Name", key="fb_name")
        fb_rating = st.select_slider("Rating", options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], value="⭐⭐⭐⭐⭐")
        fb_text = st.text_area("Feedback", key="fb_text", placeholder="What works well? What needs fixing?")
        fb_sugg = st.text_area("Suggestions", key="fb_sugg", placeholder="Any feature you want added or changed?")
        if st.button("Send feedback", type="primary", use_container_width=True):
            if not (fb_text.strip() or fb_sugg.strip()):
                st.warning("Write a little feedback or a suggestion first.")
            else:
                status = save_feedback(fb_name, fb_rating, fb_text, fb_sugg)
                if status == "synced" or status.startswith("synced"):
                    st.success("Salamat! Your feedback was saved and sent to the Google Sheet." + overflow_hint(status))
                elif status == "local-only":
                    st.success("Salamat! Your feedback was saved locally." + overflow_hint(status))
                else:
                    st.success("Salamat! Your feedback was saved locally." + overflow_hint(status))
                    st.caption(f"Google Sheet sync did not go through — it will not affect your submission. ({status})")

lesson_tab, lil_tab, test_tab, ppt_tab = st.tabs(["📘 ILAW Lesson Plan", "📗 ILAW-LIL (Implementation Log)", "📝 Test Paper Generator", "🖥️ PowerPoint Generator"])

with lesson_tab:
    st.caption("Step 1 — upload your BOW. The app reads the terms, week rows, competencies, standards, and activities, "
               "then fills Learning Area and Lesson name for you. Step 2 — pick the Term, Week, and Teaching Strategy.")

    # --- STEP 1: BOW upload comes FIRST and feeds everything below it. ---
    st.subheader("1 · Budget of Work (BOW)")
    bow_file = st.file_uploader("Upload BOW — PDF, Word, or Excel", type=["pdf", "docx", "xlsx", "xlsm", "xls"],
                                key="ilaw_bow",
                                help="The official DepEd Three-Term Budget of Work. It is parsed into terms, week rows, "
                                     "competencies, standards, and suggested activities — the AI's primary source.")
    bow_struct, bow_area_hint, bow_grade_hint = [], "", ""
    if bow_file:
        try:
            bow_raw = read_document_cached(bow_file.name, bow_file.getvalue())
            bow_struct = parse_bow(bow_raw)
            st.session_state["ilaw_bow_raw"] = bow_raw
            bow_area_hint, bow_grade_hint = _bow_area_grade(bow_raw)
            if bow_struct:
                total_rows = sum(len(t["weeks"]) for t in bow_struct)
                st.success(f"BOW parsed: {len(bow_struct)} term(s), {total_rows} week row(s), "
                           f"{sum(len(t['suggested_activities']) for t in bow_struct)} suggested activities.")
                with st.expander("See what the app read from your BOW"):
                    for t in bow_struct:
                        rows = " · ".join(f"Wk {r['weeks']}: {r['lesson']}" for r in t["weeks"][:12])
                        st.markdown(f"**{t['term']}** — {len(t['content_standards'])} content standard(s); week rows: {rows or 'none detected'}")
            else:
                st.info("This file was read but no official Three-Term BOW structure (First/Second/Third Term with week rows) "
                        "was detected. The full text will still be sent to the AI as the basis.")
        except Exception as exc:
            st.error(f"Could not read the BOW file: {exc}")
            bow_struct = []
    else:
        st.info("No BOW uploaded yet — the AI will search public DepEd sources and produce a provisional draft. "
                "Upload a BOW for the most accurate lesson.")

    # --- STEP 2: lesson details. Learning Area + Lesson name lock when a BOW is present. ---
    bow_locked = bool(bow_struct)
    week_lookup = {}
    bow_term_index = None
    if bow_struct:
        hit = week_lookup_for(bow_struct, st.session_state.get("ilaw_week_bow"))
        bow_term_index = hit[0] if hit else None
    with st.form("ilaw_form"):
        st.subheader("2 · Lesson details")
        left, right = st.columns(2)
        with left:
            area = st.text_input("Learning area / subject *", placeholder="e.g., Science",
                                 value=bow_area_hint or "", disabled=bow_locked,
                                 help="Filled automatically from the uploaded BOW." if bow_locked else None)
            grade = st.text_input("Grade level and section *", placeholder="e.g., Grade 9 – Hydrogen",
                                  value=bow_grade_hint or "", key="ilaw_grade")
            if bow_struct:
                week_options = []
                for t_index, t in enumerate(bow_struct, start=1):
                    for row in t["weeks"]:
                        label = f"{t['term']} · Week {row['weeks']} — {row['lesson'][:60]}"
                        week_options.append(label)
                        week_lookup[label] = (t_index, t, row)
                week = st.selectbox("Week (from your BOW) *", week_options, key="ilaw_week_bow",
                                    help="Every week row found in the BOW. The matching lesson title and "
                                         "competencies are used verbatim.")
            else:
                week = st.text_input("Week *", placeholder="e.g., Week 3", key="ilaw_week_text")
            term = st.selectbox("Term", ["Term 1", "Term 2", "Term 3"], key="ilaw_term",
                                disabled=bow_locked,
                                index=(bow_term_index - 1) if bow_locked and bow_term_index else None,
                                help="Auto-selected from your BOW week row." if bow_locked else None)
            strategy = st.selectbox("Teaching Strategy Model *", TEACHING_STRATEGIES, index=None, placeholder="Select a required model", key="ilaw_strategy")
        with right:
            auto_title = ""
            if bow_struct:
                hit = week_lookup.get(week)
                auto_title = hit[2]["lesson"] if hit else (bow_struct[0]["weeks"][0]["lesson"] if bow_struct[0]["weeks"] else "")
            title = st.text_input("Name of lesson", value=auto_title, disabled=bow_locked,
                                  key="ilaw_lesson_locked",
                                  placeholder="Auto-filled from the BOW week row",
                                  help="Filled automatically from the matching BOW week row." if bow_locked else None)
            sessions = st.selectbox("Number of sessions", [1, 2, 3, 4, 5], key="ilaw_sessions")
            duration = st.selectbox("Duration per session", ["40 minutes", "50 minutes", "60 minutes"], key="ilaw_duration")
            medium = st.selectbox("Medium of instruction", ["English", "Filipino", "Cebuano", "Mother tongue / local language", "Mixed"], key="ilaw_medium")
        teacher = st.text_input("Teachers Name (optional)", key="ilaw_teacher")
        context = st.text_area("Learner/classroom context (optional)", key="ilaw_context")
        note = st.text_area("Additional instructions (optional) — your own prompt to improve the output", placeholder="e.g., Use more hands-on activities; include local examples from Agusan del Sur; emphasize group work; keep language simple for struggling readers.", help="Anything you add here is sent to the AI as extra instructions for your lesson plan.", key="ilaw_note")
        submitted = st.form_submit_button("Generate ILAW lesson plan", type="primary", use_container_width=True)

    if submitted:
        missing = [label for label, value in {"Learning area": area, "Grade level and section": grade, "Week": week, "Teaching Strategy Model": strategy}.items() if not value or not str(value).strip()]
        if missing:
            st.error("Please complete: " + ", ".join(missing))
        elif not api_key.strip():
            st.error(f"Add your {cfg['key_label']} in the sidebar.")
        else:
            try:
                with st.spinner("Reading the BOW and creating your ILAW lesson plan..."):
                    bow_text = ""
                    if bow_file:
                        bow_text = st.session_state.get("ilaw_bow_raw") or read_document_cached(bow_file.name, bow_file.getvalue())
                    bow_title = ""
                    if bow_struct:
                        hit = week_lookup.get(week)
                        if hit:
                            bow_title = hit[2]["lesson"]
                            week = f"Week {hit[2]['from']}"
                            term = hit[1]["term"]
                    details = {"area": area, "grade": grade, "term": term, "week": week, "strategy": strategy,
                               "title": bow_title or title, "sessions": sessions, "duration": duration, "medium": medium,
                               "teacher": teacher, "context": context, "note": note.strip(),
                               "bow": (summarize_bow(bow_struct, term, week) + "\n\nRAW BOW TEXT:\n" + bow_text) if bow_struct else bow_text,
                               "bow_filename": bow_file.name if bow_file else "",
                               "bow_match": match_bow_row(bow_struct, term, week)}
                    st.session_state.plan, st.session_state.details = generate(api_key, details), details
            except Exception as exc:
                st.error(f"Could not generate the lesson plan: {exc}")

    if plan := st.session_state.get("plan"):
        show_plan(plan)
        if st.session_state.details.get("reference_source", "").startswith("Google Search"):
            st.warning("No BOW was uploaded. This is a provisional online-search draft—verify the competency code and wording against the official BOW before use.")
        else:
            st.warning("AI-generated draft only. Verify BOW alignment, learner needs, references, and your school's requirements before use.")

        try:
            st.download_button("Download ILAW Excel file", excel_export(plan, st.session_state.details), "ilaw-lesson-plan.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        except Exception as exc:
            st.error(f"Could not prepare the Excel file: {exc}")

with lil_tab:
    st.caption("Create a Lesson Implementation Log (LIL) from an uploaded Lesson Exemplar. The exemplar is REQUIRED — "
               "the app reads it first and auto-detects the Learning Area, Grade Level, and Term. All sessions export to ONE "
               "DepEd LIL Excel file; Dates/Time stay blank for you to fill in.")
    if not LIL_TEMPLATE.exists():
        st.error("The LESSON IMPLEMENTATION LOG TEMPLATE.xlsx file is missing from the app folder. Run ILAW_TeacherTools_Setup.bat to repair.")
    # --- STEP 1: upload the Lesson Exemplar first — it drives every other field. ---
    st.subheader("1 · Lesson Exemplar (required)")
    lil_file = st.file_uploader("Upload Lesson Exemplar * (PDF, Word, or Excel) — the basis of the log",
                                type=["pdf", "docx", "xlsx", "xlsm", "xls"], key="lil_file")
    lil_meta = {"area": "", "grade": "", "term": "", "week": ""}
    if lil_file:
        try:
            lil_raw = st.session_state.get("lil_exemplar_raw") or read_document_cached(lil_file.name, lil_file.getvalue())
            st.session_state["lil_exemplar_raw"] = lil_raw
            lil_meta = detect_exemplar_meta(lil_raw)
            found = [f"{label}: {value}" for label, value in
                     (("Learning Area", lil_meta["area"]), ("Grade", lil_meta["grade"]),
                      ("Term", lil_meta["term"]), ("Week", lil_meta["week"])) if value]
            if found:
                st.success("Detected from your exemplar — " + " · ".join(found) +
                           ". The locked fields below are filled from it.")
            else:
                st.info("Exemplar read, but no standard DepEd header (Learning Area / Grade Level / Semester / Quarter) "
                        "was detected. Fill the fields below manually — the full exemplar text is still the AI's basis.")
            with st.expander("See what the app read from your exemplar"):
                st.markdown(lil_raw[:1500].replace("\n", "  \n") + ("…" if len(lil_raw) > 1500 else ""))
        except Exception as exc:
            st.error(f"Could not read the exemplar file: {exc}")
            lil_meta = {"area": "", "grade": "", "term": "", "week": ""}
    else:
        st.info("Upload the Lesson Exemplar first — the app detects the Learning Area, Grade Level, and Term from it, "
                "then you only confirm the rest.")
    # --- STEP 2: log details. Fields lock when the exemplar provided them. ---
    lil_locked_area = bool(lil_meta["area"])
    lil_locked_grade = bool(lil_meta["grade"])
    lil_locked_term = bool(lil_meta["term"])
    lil_term_index = int(lil_meta["term"].split()[-1]) if lil_locked_term else None
    with st.form("lil_form"):
        st.subheader("2 · Log details")
        l_left, l_right = st.columns(2)
        with l_left:
            lil_area = st.text_input("Learning Area *", value=lil_meta["area"], placeholder="e.g., Science",
                                     disabled=lil_locked_area,
                                     help="Detected from the uploaded exemplar." if lil_locked_area else None,
                                     key="lil_area")
            lil_term = st.selectbox("Term", ["Term 1", "Term 2", "Term 3"], key="lil_term",
                                    disabled=lil_locked_term, index=(lil_term_index - 1) if lil_locked_term else None,
                                    help="Detected from the exemplar's Semester/Quarter." if lil_locked_term else None)
            lil_week = st.text_input("Week *", value=lil_meta["week"], placeholder="e.g., Week 3", key="lil_week")
            lil_sessions = st.selectbox("Number of sessions (one log is generated per session)", [1, 2, 3, 4, 5], key="lil_sessions")
        with l_right:
            lil_teacher = st.text_input("Teachers Name *", placeholder="Used as 'Prepared by' on the log", key="lil_teacher")
            lil_grade = st.text_input("Grade level and section *", value=lil_meta["grade"], placeholder="e.g., Grade 9 – Hydrogen",
                                      disabled=lil_locked_grade,
                                      help="Detected from the uploaded exemplar." if lil_locked_grade else None,
                                      key="lil_grade")
            lil_strategy = st.selectbox("Teaching Strategy Model *", TEACHING_STRATEGIES, index=None, placeholder="Select a required model", key="lil_strategy")
        lil_note = st.text_area("Additional instructions (optional) — your own prompt to improve the output", placeholder="e.g., Base the flow on the second lesson in the exemplar; keep the assessment short; highlight cooperative learning.", help="Anything you add here is sent to the AI as extra instructions for your implementation log.", key="lil_note")
        lil_submitted = st.form_submit_button("Generate ILAW-LIL", type="primary", use_container_width=True)

    if lil_submitted:
        lil_missing = [label for label, value in {
            "Learning Area": lil_area, "Teachers Name": lil_teacher, "Grade level and section": lil_grade,
            "Week": lil_week, "Teaching Strategy Model": lil_strategy,
        }.items() if not value or not str(value).strip()]
        if lil_file is None:
            lil_missing.append("Lesson Exemplar upload (required)")
        if lil_missing:
            st.error("Please complete: " + ", ".join(lil_missing))
        elif not api_key.strip():
            st.error(f"Add your {cfg['key_label']} in the sidebar.")
        else:
            try:
                with st.spinner("Reading the Lesson Exemplar and creating your Lesson Implementation Log..."):
                    lil_exemplar_text = st.session_state.get("lil_exemplar_raw") or read_document_cached(lil_file.name, lil_file.getvalue())
                    lil_details = {
                        "area": lil_area, "grade": lil_grade, "teacher": lil_teacher,
                        "termweek": f"{lil_term} · {lil_week}",
                        "strategy": lil_strategy, "sessions": lil_sessions, "note": lil_note.strip(),
                        "exemplar": lil_exemplar_text,
                        "exemplar_filename": lil_file.name,
                    }
                    st.session_state.lil_plan, st.session_state.lil_details = generate_lil(api_key, lil_details), lil_details
            except Exception as exc:
                st.error(f"Could not generate the implementation log: {exc}")

    if lil_plan := st.session_state.get("lil_plan"):
        st.subheader(first_option(lil_plan.get("log_title"), "Lesson Implementation Log"))
        st.info(first_option(lil_plan.get("overview")))
        st.write(f"**Learning Competency:** {first_option(lil_plan.get('learning_competency'))}")
        st.caption(f"Teaching Strategy Model: {st.session_state.lil_details.get('strategy', '')}")
        for l_index, l_item in enumerate(lil_plan.get("sessions", [])):
            with st.expander(f"🧩 {l_item.get('session', f'Session {l_index + 1}')}: {first_option(l_item.get('topic'))}", expanded=True):
                for l_field, l_label in LIL_SESSION_FIELDS:
                    st.markdown(f"**{l_label}**")
                    l_body = first_option(l_item.get(l_field))
                    if l_field == "flow":
                        st.markdown(flow_html(l_body), unsafe_allow_html=True)
                    elif l_field == "learning_experience":
                        import html as _lhtml
                        st.markdown("<br>".join(_lhtml.escape(line) for line in format_references_text(l_body).split("\n")), unsafe_allow_html=True)
                    else:
                        st.markdown(l_body.replace("\n", "  \n"))
        st.warning("AI-generated draft only. Review every part against your Lesson Exemplar and your learners before use.")
        st.caption("📊 The Excel export fills ALL sessions — one column (C–G) per session, matching the DepEd weekly log slots.")
        try:
            st.download_button("Download Lesson Implementation Log (Excel)",
                               lil_export(lil_plan, st.session_state.lil_details),
                               "lesson-implementation-log.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        except Exception as exc:
            st.error(f"Could not prepare the Excel file: {exc}")

with test_tab:
    st.caption("Create a HOTS-SOLO multiple-choice test paper with answer key and Table of Specifications. Works as an examination, summative test, or quiz. Use a topic, or upload an ILAW lesson plan Excel file as the basis.")
    basis_choice = st.radio("Test basis", [BASIS_TOPIC, BASIS_ILAW], horizontal=True, help="Choose whether the test is based on a typed topic/competency or an uploaded ILAW lesson plan.")
    with st.form("test_form"):
        t_left, t_right = st.columns(2)
        with t_left:
            t_subject = st.text_input("Subject / learning area *", placeholder="e.g., Science")
            t_grade = st.text_input("Grade level and section *", placeholder="e.g., Grade 9 – Hydrogen")
            t_term = st.selectbox("Term", ["Term 1", "Term 2", "Term 3"])
            t_items = st.selectbox("Number of items", [10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100], index=2, help="Larger tests take noticeably longer to generate.")
            t_type = st.selectbox("Test paper type", ["Examination", "Summative Test", "Quiz"], index=0, help="Shown on the printed paper header and used to guide the AI.")
        with t_right:
            t_topic = st.text_area("Topic / competency", placeholder="e.g., Photosynthesis — Grade 9, Quarter 1", disabled=basis_choice != BASIS_TOPIC, help="Used when the basis is a topic or competency.")
            t_bow = st.file_uploader("Upload ILAW lesson plan (PDF, Word, or Excel)", type=["xlsx", "xlsm", "pdf", "docx", "xls"], disabled=basis_choice != BASIS_ILAW, help="Used when the basis is an uploaded ILAW lesson plan. PDF, Word, and Excel are all read into the AI.")
            t_mix = st.selectbox("LOTS / MOTS / HOTS mix", list(TEST_MIXES), index=0)
        t_note = st.text_area("Additional instructions (optional) — your own prompt to improve the output", placeholder="e.g., Add 5 easy items at the start; make scenarios about farming; avoid computation-heavy items; use Filipino contexts.", help="Anything you add here is sent to the AI as extra instructions for your test paper.", key="t_note")
        test_submitted = st.form_submit_button("Generate Test Paper", type="primary", use_container_width=True)

    if test_submitted:
        missing = [label for label, value in {"Subject / learning area": t_subject, "Grade level and section": t_grade}.items() if not value or not value.strip()]
        if basis_choice == BASIS_TOPIC and not t_topic.strip():
            missing.append("Topic / competency")
        if basis_choice == BASIS_ILAW and t_bow is None:
            missing.append("ILAW lesson plan upload")
        if missing:
            st.error("Please complete: " + ", ".join(missing))
        elif not api_key.strip():
            st.error(f"Add your {cfg['key_label']} in the sidebar.")
        else:
            try:
                with st.spinner("Researching official teaching-day pacing, then writing your test paper..."):
                    basis = read_any_document(t_bow) if basis_choice == BASIS_ILAW else t_topic
                    if basis_choice == BASIS_ILAW:
                        basis = "Uploaded ILAW lesson plan (teacher-reviewed):\n" + basis
                    mix = TEST_MIXES[t_mix]
                    test_details = {"area": t_subject, "grade": t_grade, "term": t_term, "items": t_items, "test_type": t_type, "mix": mix, "note": t_note.strip(), "hots_min": max(1, math.ceil(t_items * mix["hots"] / 100))}
                    st.session_state.test, st.session_state.test_details = generate_test(api_key, basis, test_details), test_details
            except Exception as exc:
                st.error(f"Could not generate the test paper: {exc}")

if test := st.session_state.get("test"):
    with test_tab:
        show_test(test, st.session_state.test_details)
        st.warning("AI-generated draft only. Review every item, the answer key, and the Table of Specifications before using this test with learners.")
        try:
            st.download_button("Download Test Paper, Answer Key, and TOS (Word files)", export_test_docx(picked_test(test), st.session_state.test_details), "test-paper-package.zip", "application/zip", type="primary")
        except Exception as exc:
            st.error(f"Could not prepare the test paper files: {exc}")

with ppt_tab:
    st.caption("Turn an uploaded ILAW lesson plan into lightweight classroom PowerPoints — **one session per generation**, "
               "each deck following the canonical 16-part lesson flow (Title → Objectives → Motivation → Prior Knowledge → "
               "Introduction → Content → Example → Guided Activity → Application → Higher-Order Question → Assessment → "
               "Generalization → Assignment → Closing). Pick one session at a time to keep the AI fast and reliable.")
    if Presentation is None:
        st.error("The python-pptx package is missing. Run ILAW_TeacherTools_Setup.bat to repair the installation, then reload this page.")
    p_left, p_right = st.columns(2)
    with p_left:
        p_file = st.file_uploader("Upload ILAW lesson plan (PDF, Word, or Excel)", type=["xlsx", "xlsm", "pdf", "docx", "xls"], key="ppt_upload")
        p_teacher = st.text_input("Name of the teacher", placeholder="Shown on the title slide", key="p_teacher")
    with p_right:
        p_slides = st.selectbox("Slides per session", [16, 15, 20, 30], index=0,
                                help="16 = the exact lesson flow above (recommended). Other sizes keep every stage but merge or split the Lesson Content slides.", key="p_slides")
        p_style = st.selectbox("Design style", PPT_DESIGN_STYLES, index=0,
                               help="The AI turns this style into the deck's colors, shapes and decorations. Same file + different style = a fresh look.", key="p_style")
        p_note = st.text_area("Additional instructions (optional) — your own prompt to improve the output", placeholder="e.g., More visual activities; emphasize the group experiment; use Cebuano keywords.", key="p_note")
    p_template = st.file_uploader("Upload your own PPT template (optional) — .pptx or .potx. The AI designs the CONTENT, your template provides the DESIGN.",
                                  type=["pptx", "potx"], key="p_template",
                                  help="Your template's theme, fonts, colors, masters, and slide size are used for the deck. Leave empty for the AI's auto design.")

    # Detect sessions from the uploaded file so the user can pick ONE at a time.
    detected_sessions = st.session_state.get("ppt_sessions") or []
    detected_meta = st.session_state.get("ppt_meta") or {}
    if st.button("1️⃣ Detect sessions in this file", disabled=Presentation is None, use_container_width=True):
        if p_file is None:
            st.error("Please upload the ILAW lesson plan file first.")
        elif not api_key.strip():
            st.error(f"Add your {cfg['key_label']} in the sidebar.")
        else:
            try:
                st.session_state.ppt_basis = read_any_document(p_file)
                with st.spinner("Reading the sessions from your lesson plan..."):
                    meta, sessions = generate_session_topic(st.session_state.ppt_basis)
                st.session_state.ppt_meta = meta
                st.session_state.ppt_sessions = sessions
                st.session_state.pop("ppt_deck", None)
                st.session_state.pop("ppt_progress", None)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not read the sessions: {exc}")

    if detected_sessions:
        subject_line = detected_meta.get("subject") or ""
        base_title = detected_meta.get("deck_base_title") or ""
        st.success(f"Found {len(detected_sessions)} session(s)" + (f" — {subject_line}" if subject_line else "") + ". Pick the session to build.")
        session_labels = [f"Session {s['session']} — {s['topic']}" for s in detected_sessions]
        p_session = st.selectbox("Which session should get a PowerPoint? (one at a time)",
                                 range(len(detected_sessions)), format_func=lambda i: session_labels[i], key="p_session")
        if st.button("🎨 Generate PowerPoint for this session", type="primary", use_container_width=True, disabled=Presentation is None):
            if not api_key.strip():
                st.error(f"Add your {cfg['key_label']} in the sidebar.")
            else:
                session = detected_sessions[p_session]
                try:
                    basis = st.session_state.get("ppt_basis") or read_any_document(p_file)
                    with st.spinner(f"Designing slides for Session {session['session']}: {session['topic']}..."):
                        ppt_details = {"slides": p_slides, "teacher": p_teacher.strip(), "note": p_note.strip(), "style": p_style,
                                       "deck_subject": subject_line, "deck_base_title": base_title,
                                       "session_number": session["session"], "session_topic": session["topic"]}
                        deck_plan = generate_ppt_plan(basis, ppt_details)
                        deck_bytes = build_presentation(deck_plan, p_teacher.strip(), p_style,
                                                        p_template.getvalue() if p_template else None)
                    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", str(deck_plan.get("deck_title") or f"Session_{session['session']}")).strip("_")[:60] or f"Session_{session['session']}"
                    st.session_state.ppt_deck = {"filename": f"{safe_title}.pptx", "bytes": deck_bytes,
                                                 "session": session["session"], "topic": session["topic"], "style": p_style}
                except Exception as exc:
                    st.error(f"Could not generate the PowerPoint: {exc}")

    deck = st.session_state.get("ppt_deck")
    if deck:
        deck_cols = st.columns([3, 1])
        with deck_cols[0]:
            st.markdown(f"**Session {deck['session']}** — {deck['topic']} · _{deck['style'].split(' — ')[0]} style_")
        with deck_cols[1]:
            st.download_button("Download", deck["bytes"], deck["filename"],
                               "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                               key="ppt_dl_deck", use_container_width=True, type="primary")
        st.caption("Generate again with a different Design style (or another session) for a fresh look — same lesson, new design. "
                   "Lightweight by design: flat color shapes and AI-suggested illustrations, so each deck stays a few dozen KB.")
