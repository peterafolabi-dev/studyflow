# 📚 StudyFlow

**A full-stack student productivity web app built for university students — built with Django, deployed on Render.**

StudyFlow is an all-in-one study companion that combines smart planning, AI assistance, resource sharing, and focus tools in a single clean, responsive interface. Built for the students of FUT Minna (and any student who wants to study smarter).

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🤖 AI Study Coach | Groq-powered chatbot (Llama 3.1) with full conversation memory, math rendering, and flashcard generation |
| 📋 Dashboard | Bento-style overview of tasks, courses, recent resources, and quick links |
| 📚 Catalogue | Global library of books students can browse, save, and read online |
| 🏛️ IBB Library | Reserve physical books at FUT Minna's IBB Library — track loans in real time |
| 📁 Resources | Upload and download Past Questions, Notes, Theses, and Lecture Slides |
| ⏱️ Pomodoro Timer | Study Room with a focus timer, Deep Focus + Lo-Fi Spotify playlists, and session logging |
| 🃏 Flashcards | Create, flip, and quiz yourself on your own flashcard decks |
| 📊 GPA Calculator | Calculate your semester and cumulative GPA by course |
| 🗓️ Timetable | Build and manage your weekly class timetable |
| 👥 Study Groups | Join or create groups for specific courses |
| 🎮 Break Room | Mini-games for mental breaks between study sessions |
| 🔔 Notifications | In-app notification system |
| 👤 User Profiles | Public profiles, edit profile, find study buddies |
| 🔐 Google OAuth | Sign in with Google via django-allauth |
| 🌙 Dark Mode | Toggle between light and dark themes, persisted in localStorage |
| 📱 PWA | Installable as a Progressive Web App on mobile devices |

---

## 🤖 AI Study Coach (Details)

The AI assistant is powered by **Groq API** (ultra-fast LLM inference) running **Llama 3.1**.

It is trained to:
- Answer questions on any academic subject (math, science, engineering, coding)
- Render **LaTeX math equations** using **KaTeX** directly in the chat
- Generate flashcards in a clean structured format
- Create personalized study plans and Pomodoro schedules
- Summarize readings and explain concepts step by step
- Know every feature inside StudyFlow and guide students to the right tool

**Security:**
- Endpoint protected with `@login_required` — no unauthenticated access
- Conversation history stored client-side and sent per-turn for full multi-turn memory
- HTML output sanitized with **DOMPurify** to prevent XSS

---

## 🔒 File Upload Security

Resource uploads are validated at **two layers**:

**Frontend (immediate feedback):**
- File extension and MIME type checked in JavaScript before submission
- Max file size enforced (default 10 MB) with a friendly error message
- Drag-and-drop zone with visual feedback

**Backend (authoritative):**
- Extension and MIME type validated against configurable allowlist
- **Magic bytes** checked (e.g. `%PDF-` for PDFs) — renamed `.exe` files are rejected
- A **random UUID filename** is generated server-side — original client filename is never used for storage
- Returns HTTP 400 with a clear error message on rejection

Allowed types are configured in one place (`.env`):
```
ALLOWED_TYPES=PDF
# or: ALLOWED_TYPES=PDF, PNG, JPG, JPEG
MAX_UPLOAD_SIZE_MB=10
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 6.1.1 |
| AI / LLM | Groq API (llama-3.1-8b) |
| Frontend | Tailwind CSS (CDN), Vanilla JS |
| Auth | django-allauth (Google OAuth + Email) |
| Database | SQLite (dev) / PostgreSQL (production) |
| Deployment | Render (Web Service + PostgreSQL) |
| Static Files | WhiteNoise |
| PDF Generation | ReportLab |
| Math Rendering | KaTeX |
| Markdown | marked.js + DOMPurify |
| PWA | Django PWA manifest + service worker |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- A [Groq API key](https://console.groq.com/) (free tier available)
- (Optional) Google OAuth credentials for Google sign-in

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/studyflow.git
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
MODEL_NAME=openai/gpt-oss-20b    # or any active Groq model

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

---

## 📁 Project Structure

```
studyflow/
├── accounts/          # User auth, profiles, notifications
├── community/         # Study groups, thread discussions, find buddies
├── library/           # Digital catalogue and book reading
├── planner/           # Dashboard, tasks, courses, flashcards, GPA, study room
├── resources/         # File uploads (past questions, notes, etc.), IBB Library
├── studyflow/         # Django project settings and upload config
├── templates/         # All Django HTML templates
├── static/            # CSS and PWA icons
├── screenshots/       # App screenshots for the README
├── requirements.txt
├── build.sh
└── manage.py
```

---

## 📸 Screenshots

| Dashboard | Courses |
|---|---|
| ![Dashboard](screenshots/02-dashboard.png) | ![Courses](screenshots/03-courses.png) |

| Course Detail | Mobile |
|---|---|
| ![Course Detail](screenshots/04-course-detail.png) | ![Mobile](screenshots/05-dashboard-mobile.png) |

---

## 🛡️ Security Highlights

- **AI endpoint:** Protected by `@login_required` + `@require_POST` — no anonymous access
- **CSRF:** Django CSRF tokens enforced on all state-changing requests
- **XSS:** AI chat output sanitized with DOMPurify before DOM insertion
- **Upload security:** Magic-byte file content validation + UUID safe filenames
- **OAuth:** Handled via django-allauth with PyJWT
- **HTTPS:** Enforced in production via Render + Django secure settings (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Built by

A FUT Minna Computer Science student building tools that actually help students win. ⚔️

> *"Every student who opens this app is an athlete in training, and their studies are the arena."*