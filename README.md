# 📚 DepEd Teacher Tools Generator

A Streamlit app for Philippine DepEd teachers: **ILAW Lesson Plans, ILAW-LIL Implementation Logs, Test Papers (with TOS + Answer Key), and PowerPoint generators** — all grounded on your own **Budget of Work (BOW)** and powered by any of four AI providers.

**Developed by: Jose Dennis Plaza Chua** · Current version: **v1.7.0**

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

## 📘 Tab 1 — ILAW Lesson Plan (built-in BOW library)

1. **Pick your Grade level and Subject** from the dropdowns — the app reads the official DepEd BOW library (Kindergarten, Grades 1–12, ~240 subjects). On your computer it uses the `DepEd BOW Files` folder on your Desktop (parsed once and cached); **online (Streamlit Cloud) the same library is built into the app itself** — no Desktop folder needed.
2. **Pick your lesson/topic** from the dropdown — every entry shows its **Term and Week** straight from the BOW (e.g., *"Term 2 · Week 5 to 6 — Origin of the Solar System"*). Grade 11/12 BOWs have no terms, so entries show *"Week 1 — topic"*; Senior High units and Kindergarten themes show the topic title.
3. Learning Area, Term, and Lesson name **auto-fill and lock** from your pick.
4. **The app decides the number of sessions for you** — the AI reads the topic's competencies and weekly time allotment and creates exactly the sessions the topic needs (1–5). You no longer choose it.
5. Choose duration, medium, and strategy model; optionally add your own extra instructions.
6. **Generate** → the AI builds the plan **strictly from your BOW topic**, then a **second AI review pass** verifies every competency, objective, activity, assessment, and strategy and removes anything unsupported.
7. **Download the Excel** in the official weekly ILAW format — term/week filled in, every cell auto-sized so all text is visible.

Can't find your subject or topic in the library? Expand **"Upload a BOW manually"** — an uploaded BOW drives the same flow.

Without any BOW, the AI searches official DepEd sources instead — and if it cannot verify the lesson for your Grade + Subject + Term + Week, it **tells you instead of inventing one**.

## 📗 Tab 2 — ILAW-LIL (Lesson Implementation Log)

Upload a **Lesson Exemplar** (PDF/Word/Excel) → the AI reads it **thoroughly** and drafts the LIL in the official Excel format:

- All sessions in **one file** — one column per session (C–G, up to 5).
- **Yellow label cells and the reminder are never touched** — only the blank detail cells are filled.
- Activity names, sequence, and content come **only from your exemplar**.
- Dates/Time stay blank for you to fill in after each actual session.
- Exports the exact `LESSON IMPLEMENTATION LOG TEMPLATE.xlsx` format.

## 📝 Tab 3 — Test Paper (HOTS–SOLO)

- Basis: a topic you type, **or** an uploaded ILAW lesson plan / exemplar.
- Multiple choice with **HOTS–SOLO taxonomy levels**, adjustable **LOTS/MOTS/HOTS mix**, **up to 100 items**, **balanced option lengths** (no "longest answer is correct" giveaways), and a **shuffled answer key**.
- Outputs **three documents**: the test paper, the **answer key**, and the **Table of Specifications (TOS)** — as Word/Excel downloads.
- Each question comes with alternatives so you can review before exporting.

## 🖥️ Tab 4 — PowerPoint Generator

- Upload your ILAW/exemplar → the app detects the sessions; pick **one session** and a **slide count** (10/15/20/30) and **design theme** (Floral, Business, Education, Research, …).
- The AI writes the content and picks fitting **images**; decks stay under ~3 MB.
- Follows the DepEd flow: Title → Objectives → Motivation → Prior Knowledge → Content (with real paragraph meanings) → Example → Guided Activity → Application → HOTS question → Assessment → Generalization → Assignment → Closing.
- **Optional: upload your own .pptx/.potx template** — the AI fills YOUR design with its content (slide size, colors, and layout are preserved).

## 💬 Feedback

The sidebar has a short feedback form (Name, Rating, Feedback, Suggestions) that submits straight to the developer's Google Form.

---

## 🧰 For developers

- `app.py` — the whole app (single file, ~3,100 lines).
- `work/test_*.py` — **17 offline test suites** (300+ checks). Run: `python work/test_bow.py` etc. (no server needed).
- `work/rebuild_installer.py` — rebuilds `ILAW_TeacherTools_Setup.bat` after editing `app.py`: `py work/rebuild_installer.py`.
- Version lives in `_APP_VERSION` at the top of `app.py` — bump it on every change; the sidebar, title, and installer all show it.
