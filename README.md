# 📚 StudyFlow

[![Tests](https://github.com/peterafolabi-dev/studyflow/actions/workflows/tests.yml/badge.svg)](https://github.com/peterafolabi-dev/studyflow/actions/workflows/tests.yml)
![Django tests](https://img.shields.io/badge/django%20tests-154%20passing-1F8A4C)
![Python](https://img.shields.io/badge/python-3.12-3776AB)
![AI](https://img.shields.io/badge/AI-Groq%20LLM-F55036)

**A study platform for university students, with a 24/7 AI study coach that renders maths properly. Built with Django, deployed on Render.**

**Live:** [studyflow-xt1x.onrender.com](https://studyflow-xt1x.onrender.com) (free tier, so the first load can take ~30 seconds to wake up)

StudyFlow combines planning, AI help, resource sharing and focus tools in one responsive app. Built for students at FUT Minna, and any student who wants to study smarter.

<p><img src="screenshots/01-landing-mobile.png" width="260" alt="StudyFlow on a phone"> <img src="screenshots/03-research.png" width="520" alt="StudyFlow research page"></p>

---

## Engineering decisions

- **Uploads are judged by their bytes, not their names.** A file renamed from `.exe` to `.pdf` is rejected because the server checks its magic bytes (`%PDF-`), not just the extension or the browser's MIME type. Files are stored under a random UUID, so a crafted filename can never reach the filesystem.
- **AI output is treated as untrusted.** Model replies can contain HTML, so they're sanitised with DOMPurify before they touch the page. LaTeX is rendered with KaTeX instead of being trusted as markup.
- **AI cost and abuse are capped.** Expensive AI features (like asking questions about a PDF) have a per-user rate limit, so one user or script can't run up the API bill.
- **Two layers of validation.** The browser gives instant feedback on file type and size, and the server repeats every check, because client-side checks are a convenience, not security.
- **Deploys only after green tests.** GitHub Actions runs `manage.py check`, a missing-migrations check and all 154 tests on every push, and Render can wait for CI before going live.

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🤖 AI Study Coach | Knows each student's courses, deadlines and weak topics; quizzes, plans exams, checks working, cites the app's own past questions, and can add tasks or save flashcards with one tap |
| 📋 Dashboard | Bento-style overview of tasks, courses, recent resources, and quick tools |
| 📚 Catalogue | Global library of books students can browse, save, and read online |
| 🏛️ IBB Library | Reserve physical books at FUT Minna's IBB Library — track loans in real time |
| 📁 Resources | Upload and download Past Questions, Notes, Theses, and Lecture Slides |
| ⏱️ Pomodoro Timer | Study Room with a focus timer, Deep Focus + Lo-Fi Spotify playlists, and session logging |
| 🃏 Flashcards | Create custom decks, flip cards with 3D animation, and quiz yourself with active recall |
| 💬 Campus Chat & Groups | Live campus chat rooms and course-based study groups with 24/7 AI Coach answers |
| 📊 GPA Calculator | 5.0 scale calculator with localStorage persistence |
| 🗓️ Timetable | Build and manage your weekly class timetable |
| 🎮 Break Room | 2048 mini-game with persistent high score for 5-minute Pomodoro breaks |
| 🔐 Google OAuth | 1-tap sign in with Google via django-allauth |
| 🌙 Dark Mode | Instant light/dark theme toggle, persisted in localStorage |
| ✨ Framer Motion | Fluid spring physics animations and micro-interactions throughout |
| 📱 Mobile & Desktop | Fully responsive layout optimized for smartphones, tablets, and laptops |

---

## 🤖 24/7 AI Study Coach

Groq-hosted models can't be fine-tuned from here, so the coach is "trained" the way production AI tutors are: a teaching playbook, live knowledge of the student, the app's own content, worked examples to imitate, a feedback loop, and an exam it has to pass. Everything lives in [`planner/coach/`](planner/coach).

| Piece | What it does |
|---|---|
| **Playbook** (`prompt.py`) | How to teach: answer first, find the missing step, show working, one check question, proven study methods (active recall, spacing, past questions), academic integrity without lecturing, Nigerian 5-point CGPA context. Includes worked example replies the model imitates. Versioned (`PLAYBOOK_VERSION`). |
| **Student context** (`context.py`) | Each message includes the student's department, level, courses, overdue and upcoming tasks, flashcards due, study time this week and today's classes. Only their own data. |
| **Library retrieval** (`retrieval.py`) | Searches shared resources, public CBT past questions (with answers and explanations) and the student's own flashcards, so replies cite real items with links. Plain keyword scoring: works on SQLite and Postgres, no extra service. |
| **Memory** (`CoachMemory`) | The coach can note durable facts ("weak at recursion", "exam on the 14th"). Students see and delete them from the 🧠 Memory panel. Passwords, phone numbers and similar are filtered out. |
| **Modes** | Chat, Explain, Quiz me (one question at a time with a score), Exam plan, Check my work, Summarise. |
| **Actions** (`actions.py`) | The coach proposes tasks and flashcards; the student taps to add them. Nothing is created without a tap. |
| **Feedback loop** (`CoachFeedback`) | 👍/👎 on every reply, stored with the playbook version and model. Review in the admin; `python manage.py export_coach_feedback` writes chat-format JSONL of good and bad replies. |
| **The exam** (`evals.py`) | One click in GitHub: **Actions → Coach exam → Run workflow** (needs a `GROQ_API_KEY` repo secret), or locally `python manage.py coach_eval`. It runs 12 realistic student situations against the live model and marks them automatically (correct arithmetic, LaTeX, dated plan tasks, honesty about unknowns, integrity, care for a stressed student...). Run it after any prompt or model change. |
| **Model fallback** (`engine.py`) | Uses `MODEL_NAME` (default `openai/gpt-oss-120b`) and falls back to other Groq models if one is missing or overloaded. |

---

## 🔒 File Upload Security

Resource uploads are strictly validated at **two layers**:

**Frontend (immediate feedback):**
- File extension and MIME type checked in JavaScript before submission
- Max file size enforced (default 10 MB) with clear validation errors
- Drag-and-drop zone with instant visual feedback

**Backend (authoritative):**
- Extension and MIME type validated against configurable allowlist
- **Magic bytes** inspected (e.g. `%PDF-` for PDFs) — renamed `.exe` files are blocked immediately
- A **random UUID filename** is generated server-side — client filenames are never used for storage
- Returns HTTP 400 with a clear error message on invalid files

Allowed types are configured in `.env`:
```env
ALLOWED_TYPES=PDF
# or: ALLOWED_TYPES=PDF, PNG, JPG, JPEG
MAX_UPLOAD_SIZE_MB=10
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 6.1.1 |
| AI / LLM | Groq API (`openai/gpt-oss-20b`) |
| Frontend | Tailwind CSS, Framer Motion (Motion engine), Vanilla JS |
| Auth | django-allauth (Google OAuth + Email) |
| Database | SQLite (dev) / PostgreSQL (production) |
| Deployment | Render (Web Service + Managed PostgreSQL) |
| Static Files | WhiteNoise |
| PDF Generation | ReportLab |
| Math Rendering | KaTeX |
| Markdown | marked.js + DOMPurify |
| PWA | Web App Manifest + Service Worker |

### Styling assets

Tailwind utilities are compiled into `static/css/tailwind.css` and served locally. When changing utility classes in templates or app code, rebuild and commit the stylesheet with `npm ci` followed by `npm run build:css`. Render serves the committed file as part of its Python build, so it does not need Node.js.

---

## 📸 Screenshots

| Landing & Mobile Experience | Courses Hub |
|:---:|:---:|
| ![Landing & Mobile](screenshots/01-landing-mobile.png) | ![Courses](screenshots/02-courses-mobile.png) |

| Academic Research Hub | Lecture Slides Hub |
|:---:|:---:|
| ![Research Papers](screenshots/03-research.png) | ![Lecture Slides](screenshots/04-lecture-slides.png) |

| Theses & Papers Repository |
|:---:|
| ![Theses & Papers](screenshots/05-theses-papers.png) |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- A [Groq API key](https://console.groq.com/) (free tier available)
- (Optional) Google OAuth credentials for Google sign-in

### 1. Clone the repository

```bash
git clone https://github.com/peterafolabi-dev/studyflow.git
cd studyflow
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# or: source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
```

### 3. Set up environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# AI
GROQ_API_KEY=your_groq_api_key_here
MODEL_NAME=openai/gpt-oss-20b

# Upload restrictions
ALLOWED_TYPES=PDF
MAX_UPLOAD_SIZE_MB=10

# Google OAuth (optional)
GOOGLE_OAUTH_CLIENT_ID=your-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-oauth-secret
```

### 4. Run migrations and start the development server

```bash
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## ☁️ Deploying to Render

1. Push your code to GitHub.
2. Create a new **Web Service** on [Render](https://render.com) and connect your repository.
3. Set the **Build Command** to: `./build.sh`
4. Set the **Start Command** to: `gunicorn studyflow.wsgi:application`
5. Add your environment variables in the Render Dashboard:
   - `GROQ_API_KEY`
   - `SECRET_KEY`
   - `DATABASE_URL` (Render provides this automatically for PostgreSQL)
   - `ALLOWED_TYPES`, `MAX_UPLOAD_SIZE_MB`
   - Google OAuth keys (if using)
   - `EMAIL_HOST_USER` and `DEFAULT_FROM_EMAIL` (your Gmail address)
   - `EMAIL_HOST_PASSWORD` (a Google App Password, not your Gmail login password)

The Render blueprint sets Gmail SMTP to `smtp.gmail.com:587` with TLS. Set the three email values above in the Render Dashboard, then redeploy. Without a configured sender, Django may use its console backend: the reset form can report success while the email is only printed to the server logs.

---

## 📁 Project Structure

```
studyflow/
├── accounts/          # User auth, profiles, notifications
├── community/         # Study groups, thread discussions, find buddies, campus chat
├── library/           # Digital catalogue and book reading
├── planner/           # Dashboard, tasks, courses, flashcards, GPA, study room, break room
├── resources/         # File uploads (past questions, notes, etc.), IBB Library
├── studyflow/         # Django project settings and upload config
├── templates/         # All Django HTML templates
├── static/            # CSS, custom scrollbars, and PWA icons
├── screenshots/       # App screenshots for the README
├── requirements.txt
├── build.sh
└── manage.py
```

---

## 🛡️ Security Highlights

- **CSRF:** Django CSRF tokens enforced on all state-changing requests
- **XSS Prevention:** AI chat output sanitized with DOMPurify before DOM insertion
- **Upload Security:** Magic-byte file content validation + UUID safe filenames
- **OAuth 2.0:** Handled securely via django-allauth with PyJWT
- **HTTPS:** Enforced in production via Render + Django secure settings (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Built by

A FUT Minna **Engineering** student building tools that actually help students win. ⚔️

> *"Every student who opens this app is an athlete in training, and their studies are the arena."*
