# DepEd Teacher Tools Generator

A Streamlit app for Philippine DepEd teachers with four tools (ILAW Lesson Plan, ILAW-LIL Implementation Log, Test Paper, and PowerPoint) powered by any of four AI providers: **Google Gemini, OpenRouter, Groq, and Mistral**. Developed by **Jose Dennis Plaza Chua**.

## AI Provider Hub

The sidebar lets each teacher pick their AI provider, paste that provider's API key, and optionally pin a model (fast or quality). All four providers produce identical app output, and each has a free tier — so when one key's quota runs out, the teacher just switches provider in the dropdown and continues with another key.

- **Provider**: Google Gemini (aistudio.google.com/apikey), OpenRouter (openrouter.ai/keys), Groq (console.groq.com/keys), or Mistral (console.mistral.ai/api-keys).
- **Model picker**: per provider — *Auto pick* (recommended; skips busy/exhausted models automatically), *Fast* models, and *Quality* models. Model names change over time; the lists are maintained in `app.py` (`PROVIDERS`).
- **Automatic fallback**: when the chosen model is unavailable (404) or its quota is spent (429/402/403), the app silently retries the provider's other models with the same request. Auth errors (401 = wrong key) fail fast with the real message.
- **Note**: Google Gemini keeps its live web-search grounding for competency/teaching-days research; the other providers answer from their training knowledge and are prompted to say "days not stated" rather than invent pacing.
- Keys live only in the browser session — nothing is saved to disk.

## Tabs

### 📘 ILAW Lesson Plan
Creates a teacher-reviewed ILAW lesson-plan draft from a DepEd Budget of Work (BOW) extract.

- **I — Intentions**: competency, objectives, and success criteria.
- **L — Learning Experiences**: learner-centered activities and resources.
- **A — Assessing Learning**: aligned formative checks and assessment tasks.
- **W — Ways Forward**: feedback, intervention, enrichment, and next steps.

The BOW is optional and can be a **PDF, Word, or Excel** file. With a text-based BOW, the app extracts its text and uses it as the competency source. Without a BOW, the AI searches public sources for a candidate competency using the selected subject, grade, term, and week. The latter is a provisional draft: the teacher must verify the competency against the official BOW before using it. Either path exports the draft to the supplied weekly ILAW Excel format.

**3 options per cell (v1.1.0):** the AI returns three alternatives for every ILAW cell (topic, objectives, pre-lesson, flow, resources, integration, formative assessment, extended learning, reflection). The result is shown as a grid with a **Select** button per option; whatever the teacher does not pick defaults to Option 1 in the exported Excel. Session count supports 1–5.

### 📗 ILAW-LIL — Lesson Implementation Log (v1.4.0)
Turns an uploaded **Lesson Exemplar (PDF, Word, or Excel)** into a DepEd **Lesson Implementation Log** filled in the official LIL Excel format:

- Inputs: Learning Area, Teachers Name (also used as **Prepared by**), Grade, Term + Week (joined automatically into one Term/Week cell), 1–5 sessions, and the same **Teaching Strategy Model** dropdown as the ILAW tab.
- **Dates/Time stay blank** — the teacher fills them in after each actual session.
- The AI copies the competency, objectives, activities, and assessment items from the exemplar (never invents content or learner names) and drafts all LIL rows: Component, Learning Competency, Objectives, Learning Resources, Weekly Implementation Log (Learning Experience, Assessing Learning, Ways Forward), and Reflection (worked well, remediation, enrichment, adjustments).
- **3 options per cell** with a select grid like the ILAW tab; Option 1 is the default on export. The Flow is exported as bold-label bullets per strategy-model phase (5Ps, 7Es, 4As, and all other models).

### 📝 Test Paper (HOTS–SOLO)
Creates a multiple-choice test paper — usable as an examination, summative test, or quiz — with an answer key and a Table of Specifications (TOS).

- Basis: a topic/competency you type, **or** an uploaded ILAW lesson plan file (**PDF, Word, or Excel**).
- Every item is generated in **3 alternative versions** (v1.1.0); the teacher picks one version per question in a side-by-side grid — Version A is used wherever no choice is made.
- Every item is tagged with a SOLO taxonomy level (Unistructural → Extended Abstract) and a Bloom's cognitive level, with selectable LOTS/MOTS/HOTS mixes.
- The TOS lists learning competencies in teaching order — the earliest-taught lesson first (top of the TOS) down to the most recent — whether the basis is an uploaded BOW or typed competencies.
- Exports one ZIP containing three DepEd-formatted Word files: **Examination** (Letter, Bookman Old Style), **Answer Key** (No./Ans. grid in tens), and **TOS** (A4 landscape with competency rows, teaching days, %, and item ranges per cognitive strand: Remembering/Understanding, Applying/Analyzing, Evaluating/Creating).

All outputs are AI drafts: the teacher reviews every item and key before classroom use.

### 🖥️ PowerPoint Generator (v1.1.0)
Uploads an ILAW lesson plan (**PDF, Word, or Excel**) and builds **one deck per session** — a 5-session plan produces 5 separate .pptx files (with a ZIP download of them all):

- The AI detects every session and its topic from the file, then designs each deck around that session only.
- Every deck follows the canonical **16-part lesson flow**: Title → Learning Objectives → Motivation/Engage → Prior Knowledge → Lesson Introduction → Lesson Content (×3) → Example/Demonstration → Guided Activity → Application → Higher-Order Question → Assessment → Generalization → Assignment/Extension → Closing.
- Slide count of **16 (exact flow), 15, 20, or 30**; other sizes keep every stage and merge/split only the Lesson Content slides.
- Teacher name on the title slide; optional extra instructions to steer the deck (emphasis, activities, language keywords).
- **Illustrated decks, still light**: every slide gets a real drawn picture (style-aware flat art rendered from the AI's `image_idea`) — whole decks stay around 0.5–1 MB, always under the 3 MB cap.

## Teacher feedback (v1.1.0)
The sidebar has a **💬 Feedback & suggestions** form (Name, Rating, Feedback, Suggestions). Every submission is **appended as a new row** to `feedback.xlsx` next to the app — existing rows are never edited. When the one-time Google Sheets webhook has been configured, the same row is **also inserted automatically into the owner's Google Sheet** — teachers enter nothing and need no URL of their own.

### How the Google sync works (zero setup for everyone)
Google blocks direct writes to a Sheet from a share link (a Google security rule), so the app posts each feedback row to the owner's **Google Form** (`forms.gle/TuTsZyb4n4AUvai57`), which accepts anonymous submissions and feeds the linked Google Sheet. The form ID and question entry IDs are baked into `app.py` (`_FEEDBACK_FORM_ID`, `_FEEDBACK_FORM_ENTRIES`). If the owner ever adds an Apps Script Web App URL (in `feedback_webhook.txt`, the `_FEEDBACK_WEBHOOK_URL` constant, or the `FEEDBACK_WEBHOOK_URL` environment variable), that webhook takes priority over the Form. Every submission is still saved locally to `feedback.xlsx` first, so nothing is lost when offline; the form message reports whether the Google send went through.

## Install on another computer (one file)

Copy **`ILAW_TeacherTools_Setup.bat`** to any folder on the other computer (USB drive, email, chat download — anything) and double-click it. That single file contains the whole system, and the installer will:

1. Extract `app.py`, `requirements.txt`, the ILAW Excel template, icons, and launchers into that folder.
2. Find or set up Python automatically. If Python is missing — or only the fake Microsoft Store "python" shortcut is present — the installer downloads a small helper and installs a private Python itself. No manual Python installation is required.
3. Install all required Python packages (skipped when they are already present).
4. Create an **"ILAW Teacher Tools"** desktop shortcut and offer to start the app.

After that, opening the app is just the shortcut or `launch_ilaw.bat` — no other setup needed. Internet is required the first time (package install) and whenever generating plans or tests. An API key from any of the four providers (Gemini, OpenRouter, Groq, Mistral) is entered in the app's sidebar.

## Run it locally (developer setup)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GOOGLE_API_KEY = "your-google-ai-studio-key"
streamlit run app.py
```

You can also paste the key into the app's sidebar for the current browser session (any of the four providers). For deployment, set `GOOGLE_API_KEY` as a secret/environment variable to pre-fill the Gemini key; do not place keys in source files.
