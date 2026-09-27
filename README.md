# 📚 DepEd Teacher Tools Generator

A Streamlit app for Philippine DepEd teachers: **ILAW Lesson Plans, ILAW-LIL Implementation Logs, Test Papers (with TOS + Answer Key), and PowerPoint generators** — all grounded on your own **Budget of Work (BOW)** and powered by any of four AI providers.

**Developed by: Jose Dennis Plaza Chua** · Current version: **v2.6.0**

---

## 🚀 HOW TO USE THIS (for other teachers)

### Option A — One-click installer (recommended, Windows)

1. On this page, click the green **`< > Code`** button → **Download ZIP**.
2. Extract the ZIP anywhere (e.g., Desktop).
3. Double-click **`ILAW_TeacherTools_Setup.bat`**.
   - It sets up everything by itself: a private Python (if your PC has none), all packages, and folders.
   - **First run needs internet** (one-time, ~5–10 minutes). After that it starts instantly, even offline.
   - Your browser opens the app automatically.
4. Next time: just double-click **`Launch DepEd Teacher Tools`** on your Desktop (created by the installer).

> ⚠️ If you see *"Python was not found… Microsoft Store"* — that is just a Windows shortcut message. The installer handles Python for you; just keep it connected to the internet on first run.

### Option B — Already have Python 3.11+

```bash
git clone https://github.com/dodieko1991/deped-teacher-tools.git
cd deped-teacher-tools
pip install -r requirements.txt
streamlit run app.py
```

---

## 🔑 GET YOUR FREE AI KEY (one per provider — pick one to start)

The app works the same with any of the four providers. Each has a **free tier**; when one quota runs out, switch provider in the sidebar and paste another key.

| Provider | Get a key here | Free tier |
|---|---|---|
| **Google Gemini** (default) | https://aistudio.google.com/apikey | Daily quota, incl. web-search grounding |
| **OpenRouter** | https://openrouter.ai/keys | Free models available |
| **Groq** | https://console.groq.com/keys | Fast free tier |
| **Mistral** | https://console.mistral.ai/api-keys | Free tier ("Experiment" plan) |

**How to start:**
1. Open the app → look at the **sidebar (AI Provider Hub)**.
2. Pick your provider in the dropdown.
3. Click the **"Get a … API key"** button — it opens the provider's key page.
4. Sign in → **Create API key** → **Copy** it.
5. Paste the key into the sidebar box. Optionally pick a **model** (Auto / Fast / Quality).
6. Click **🔍 Test this key** to confirm it works.

Keys stay in your browser session only — nothing is saved to disk.

---

## 📘 Tab 1 — ILAW Lesson Plan (built-in BOW library + reference-style planner)

Built on the approach teachers know from the popular DepEd Tambayan ILAW LP planner: you confirm
**the week's own intentions** — competency, content and performance standards, general objectives,
learner context, lesson design pattern, and the materials you actually have — and the AI unpacks
them into the daily sessions.

**Nothing is filled in for you.** The BOW you pick (or upload) is a **guide**: the app shows you
that BOW row's term/week and numbered competencies in a panel beside the form so you can copy what
you need, and it sends that BOW's text to the AI as the reference behind your competency and
pacing. Every box stays yours.

1. **Optional — pick a BOW as your guide.** **Pick your Grade level and Subject** from the dropdowns — the app reads the official DepEd BOW library (Kindergarten, Grades 1–12, ~240 subjects). It looks for the **`BOW Library` folder next to app.py** first (everything travels with the app — put BOW PDFs in `BOW Library\Grade 9\Science.pdf` and they appear in the dropdowns), then falls back to the Desktop copy (`DepEd BOW Files`); **online (Streamlit Cloud) the same library is built into the app itself**.
2. **Pick your lesson/topic** from the dropdown (or the 2nd option, **upload your own BOW**) — every library entry shows its **Term and Week** (e.g., *"Term 2 · Week 5 to 6 — Origin of the Solar System"*). Grade 11/12 BOWs have no terms, so entries show *"Week 1 — topic"*; Senior High units and Kindergarten themes show the topic title. Pick one and a **📎 BOW guide** panel opens showing that row's term/week and competencies to copy from. **Skip it entirely** and the AI searches well-known public DepEd curriculum content instead.
3. **Step 2 — Weekly Lesson Details & Intentions** (the same form as the ILAW-LIL tab). Name of lesson, Learning area, Designed by teacher/s, Grade level and section, Term, Week, and Duration all start **empty** — type them. The Term box locks only when the BOW itself states the term for that topic (e.g. *"Term 2 · Week 5 to 6"*); otherwise you pick the term your class is in.
4. **Weekly Intentions** — type or paste the **Learning Competency** (leave it blank and the guide panel's BOW row supplies it), plus optional **Content Standards**, **Performance Standards**, and **General Learning Objectives** (leave blank and the AI writes per-session K.S.A. objectives).
5. **Learner Context** — pick the preset that describes your class (mixed readiness, needs scaffolding, social learners, inclusive/diverse needs, and more) and/or write your own observations. **Learning Resources Available** — tick the materials you actually have (laptop, projector, slides, visual aids, manipulatives, worksheets, board, art materials, audio, realia, or your own), so the AI builds the sessions around them.
6. **Lesson Design Pattern** — *Default (AI selects)* lets the AI choose the best-fit framework and name it at the top of each session's flow; or pin a specific model (5Es, 7Es, 4As, 5Ps, I Do–We Do–You Do, Inquiry, Problem/Project-Based, Experiential, and more) and every one of its phases is required.
7. **No. of sessions** — *Auto* is recommended (the AI reads the competencies and weekly time allotment and creates exactly the sessions the topic needs, 1–5); or fix it at 1–5 yourself, like the reference planner's "5 Sessions (1 Week)" choices.
8. **Medium of instruction** — English, Filipino, Cebuano, mother tongue, or mixed: every row of the plan is written strictly in that language. Add your own **Additional Instructions** for anything else (local examples, gamification, simpler language).
9. **Generate** → the AI unpacks your intentions into the daily sessions, then a **second AI review pass** verifies every competency, objective, activity, assessment, and strategy and removes anything unsupported.
10. **Download the Excel** in the official weekly ILAW format — term/week filled in, every cell auto-sized so all text is visible.

**The app never blocks you.** Each plan carries an alignment label:

- **✅ VERIFIED** — the topic and competency were found in the BOW/source you supplied.
- **⚠️ NOT verified** — the topic could not be matched inside that source (Senior High courses list units, not weeks; Kindergarten themes; or a topic you typed yourself). You still get the **complete plan**, with one sentence naming exactly what to double-check or upload, and the status is printed in the Excel **References** row.

A lesson plan is never refused and no row is ever left blank — a labelled draft you can teach today beats an error message.

Can't find your subject or topic in the library? Expand **"Upload a BOW manually"** — an uploaded BOW drives the same flow.

Without any BOW at all, the AI works from well-known public DepEd curriculum content instead, and the plan is labelled **not verified** so you know to check the competency wording before filing it.

## 📗 Tab 2 — ILAW-LIL (Lesson Implementation Log)

**The same form as Tab 1**, with a Lesson Exemplar as the guide instead of a BOW:

1. **Step 1 · Lesson Exemplar guide (optional)** — upload a Lesson Exemplar (PDF/Word/Excel) and the app shows what it detected (Learning Area, Grade, Term, Week) as a **guide only** — nothing is copied into your boxes. **No exemplar? Skip it:** the AI then searches well-known public DepEd curriculum content for your learning area and grade, and the log is labelled **not verified**.
2. **Step 2 · Weekly Lesson Details & Intentions** — the identical form from Tab 1: competency, content/performance standards, objectives, learner context presets, lesson design pattern, materials on hand, sessions (1–5), medium, and your own extra instructions.
3. **Generate** → the AI drafts the log and a second review pass corrects it. With an exemplar, activity names, sequence, and content come **only from your exemplar**; without one, the log is built from the public curriculum sources it names.

- All sessions in **one file** — one column per session (C–G, up to 5).
- **Yellow label cells and the reminder are never touched** — only the blank detail cells are filled.
- Dates/Time stay blank for you to fill in after each actual session.
- Exports the exact `LESSON IMPLEMENTATION LOG TEMPLATE.xlsx` format.
- Like Tab 1, the log is never refused: it is delivered complete with a ✅ VERIFIED / ⚠️ NOT verified label.

## 📝 Tab 3 — Test Paper (HOTS–SOLO)

- Basis: a topic you type, **or** an uploaded ILAW lesson plan / exemplar.
- Multiple choice with **HOTS–SOLO taxonomy levels**, adjustable **LOTS/MOTS/HOTS mix**, **up to 100 items**, **balanced option lengths** (no "longest answer is correct" giveaways), and a **shuffled answer key**.
- Outputs **three documents**: the test paper, the **answer key**, and the **Table of Specifications (TOS)** — as Word/Excel downloads.
- Each question comes with alternatives so you can review before exporting.

## 🖥️ Tab 4 — PowerPoint Generator

- Upload your ILAW/exemplar → the app detects the sessions; pick **one session** and a **slide count** (10/15/20/30) and **design theme** (Floral, Business, Education, Research, …).
- The AI writes the content and picks fitting **images**; decks stay under ~3 MB.
- **🖼️ AI picture engine (v2.6.0)** — the slides get *real AI-generated pictures*, the same way the DepEd Tambayan generator does. Under *Slide pictures* you pick:

  | Picture engine | API key needed | Cost |
  |---|---|---|
  | **Auto — best free engine available** (default) | none | free — Gemini image when a key is set, then Pollinations |
  | Google Gemini image (Nano Banana) | your **Gemini** key (sidebar) | free daily image quota |
  | Pollinations | **none at all** | free, keyless |
  | OpenRouter Image API | your **OpenRouter** key (sidebar) | paid per image |
  | Together AI — FLUX.1 schnell | a free **Together AI** key | free endpoint |
  | None — built-in offline drawings | none | free, works offline |

- **Only image-capable services appear in that list** — Groq and Mistral are text-only, so they stay available for lesson plans, tests and slide text but are never offered as picture engines.
- **8 picture styles** (Filipino school cartoon, flat vector, 3D clay, watercolor, realistic photo, line art, chalkboard, chibi) plus an *Ask for your own look* box for your own prompt, and a **🧪 Test the picture engine** button that shows one sample image before you build the deck.
- Choose how many slides get an AI picture (**0–16**); the rest keep the app's own drawn illustration. Every failed picture falls back automatically, so **a deck is never left without pictures**, and after building, the app tells you which engine served it.
- Follows the DepEd flow: Title → Objectives → Motivation → Prior Knowledge → Content (with real paragraph meanings) → Example → Guided Activity → Application → HOTS question → Assessment → Generalization → Assignment → Closing.
- **Optional: upload your own .pptx/.potx template** — the AI fills YOUR design with its content (slide size, colors, and layout are preserved).

## 💬 Feedback

The sidebar has a short feedback form (Name, Rating, Feedback, Suggestions) that submits straight to the developer's Google Form.

---

## 🧰 For developers

- `app.py` — the whole app (single file).
- `work/test_*.py` — **27 offline test suites** (600+ checks). Run: `python work/test_v260.py` etc. (no server needed).
- `work/rebuild_installer.py` — rebuilds `ILAW_TeacherTools_Setup.bat` after editing `app.py`: `py work/rebuild_installer.py`.
- Version lives in `_APP_VERSION` at the top of `app.py` — bump it on every change; the sidebar, title, and installer all show it.
