# -*- coding: utf-8 -*-
"""Build bow_library_seed.json — the BOW library bundled for Streamlit Cloud.

Streamlit Cloud has no Desktop, so the Desktop BOW scan finds nothing there. This
script takes the prebuilt bow_library_cache.json (produced by a real scan on the
owner's machine) and enriches it with each subject's compressed raw BOW text
(library_bow_text reads PDFs on Desktop; the cloud needs the text in the seed).

Structure: {"source_stamp": <cache stamp>, "library": {grade: {subject: {
    "terms": [...], "area": ..., "grade": ..., "text": <gzip+base64 UTF-8>}}}}
"""
import base64
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

osless = sys.modules.setdefault("os", __import__("os"))
osless.environ.setdefault("DEPED_BOW_LIBRARY", str(ROOT / "unused-bow-library-dir"))

from pypdf import PdfReader  # noqa: E402

CACHE = ROOT / "bow_library_cache.json"
SEED = ROOT / "bow_library_seed.json"
BOW_DIR = Path(osless.environ.get("DEPED_BOW_REAL_LIBRARY", r"C:\Users\Administrator\Desktop\DepEd BOW Files"))

if not CACHE.exists():
    sys.exit("bow_library_cache.json not found — build it first (scan the Desktop library).")
if not BOW_DIR.is_dir():
    sys.exit(f"BOW library folder not found: {BOW_DIR}")

payload = json.loads(CACHE.read_text(encoding="utf-8"))
library = payload["library"]
print(f"Cache stamp {payload.get('stamp')} — {sum(len(s) for s in library.values())} subjects")

total = 0
texts = 0
for grade, subjects in sorted(library.items()):
    folder = BOW_DIR / grade
    if not folder.is_dir():
        print(f"  ! no folder for {grade}")
        continue
    for subject in sorted(subjects):
        raw = ""
        for path in folder.glob("*.pdf"):
            stem = re.sub(r"^\[[^\]]+\]\s*", "", path.stem)
            stem = re.sub(r"^Updated as of [\d.]+_", "", stem)
            if re.sub(r"\s+", " ", stem).strip() == subject:
                try:
                    raw = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
                except Exception as exc:
                    print(f"  ! {grade}/{subject}: {exc}")
                break
        packed = base64.b64encode(gzip.compress(raw.encode("utf-8"), 9)).decode("ascii") if raw.strip() else ""
        subjects[subject]["text"] = packed
        total += len(packed)
        texts += bool(packed)
    print(f"  {grade}: {len(subjects)} subjects")

SEED.write_text(json.dumps({"source_stamp": payload.get("stamp"), "library": library}, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {SEED.name}: {SEED.stat().st_size / 1024:.0f} KB, {texts} embedded texts, {total / 1024:.0f} KB compressed")
