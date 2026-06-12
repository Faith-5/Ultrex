# 🎬 Ultrex - AI Shorts Engine

Ultrex is an enterprise-grade, fully automated AI video production pipeline. Paste a script—or generate one with **Script Forge**—and the engine autonomously breaks it into scenes, generates cinematic images, synthesizes highly emotive TTS audio, and leverages native FFmpeg hardware acceleration to compile a publish-ready 9:16 vertical short (TikTok-style subtitles, Ken Burns motion, and audio ducking) in under 30 seconds.

**Ultrex Studio** is the built-in web UI: script writing, render progress, job history, metadata editing, and optional one-click YouTube upload.

Built for zero-budget scalability, it uses free-tier APIs and local CPU rendering.

---

## 🚀 Features

- **Script Forge (LangGraph writer agent):**  
  Multi-step Groq pipeline (Architect → Auditor → Surgeon) drafts finance-style shorts with strict word count, loop endings, and publish metadata (title, description, tags, Instagram caption). Refines until the auditor passes or iteration cap is hit.

- **LLM Scene Breakdown (Llama 3.3 70B):**  
  Splits scripts into 8-beat psychological arcs with camera angles, lighting, and color palettes. Niche-specific prompts for Finance, History, and Motivation.

- **Visual Coherence Engine:**  
  Injects a strict "Style Bible" and locks generation seeds so every scene looks like the same shoot.

- **Selectable narrator voices (Edge-TTS):**  
  Auto voice per niche, or pick Arnold, Brian, or Fable for authoritative, energetic, or storyteller delivery.

- **Hardware-Accelerated Compilation (FFmpeg):**  
  Native filtergraphs for Ken Burns motion, color grading, genre-aware caption styles, and smooth cuts—no slow Python video wrappers.

- **Advanced `.ASS` Subtitles:**  
  Burns TikTok/Reels-style captions with semi-transparent boxes into the video stream.

- **Crash-Proof State (Turso SQLite):**  
  Edge database tracks job status and per-scene progress. Server restarts do not lose render history.

- **Tiered Janitor System:**  
  APScheduler sweeps stale `.mp4`, `.png`, and `.mp3` assets every 12 hours; per-job cleanup runs after successful compiles.

- **YouTube publishing (optional):**  
  OAuth upload via YouTube Data API v3. Videos upload as **private** by default for safe testing.

- **Ultrex Studio UI:**  
  Single-page studio with Script Forge drawer, live pipeline progress, scene storyboard, recent jobs, localStorage workspace restore, and publish flow.

---

## 🛠️ Architecture & Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python) |
| Frontend | Vanilla HTML / CSS / JS (`app/static/`) |
| Writer Agent | LangGraph + Groq (Llama 3.3 70B / 3.1 8B) |
| Database | Turso (libSQL) |
| LLM Engine | Groq API |
| Image Generation | Pollinations AI (Flux) |
| Audio Generation | Edge-TTS (Microsoft Azure Neural Voices) |
| Video Compiler | Native FFmpeg (subprocess) |
| YouTube | Google API Python Client + OAuth |
| Task Scheduling | APScheduler |

---

## ⚙️ Prerequisites

### 1. Python
- Python **3.10+**

### 2. FFmpeg
You must have the full FFmpeg binary installed globally.

#### Windows
Download the full build from:  
https://www.gyan.dev/ffmpeg/builds/

Extract it and add the `bin` folder to your system PATH.

#### macOS
```bash
brew install ffmpeg
```

#### Linux
```bash
sudo apt update && sudo apt install ffmpeg
```

### 3. YouTube upload (optional)
- A Google Cloud project with **YouTube Data API v3** enabled
- OAuth 2.0 **Desktop** client credentials saved as `client_secrets.json` in the project root
- On first upload, the server opens a browser for consent and writes `token.pickle` locally

**Do not commit** `client_secrets.json` or `token.pickle`.

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Faith-5/Ultrex.git
cd Ultrex
```

### 2. Create a virtual environment

#### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### macOS / Linux
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY="your_groq_api_key"

POLLINATION_API_KEY="your_pollinations_api_key"
POLLINATIONS_BASE="https://image.pollinations.ai/prompt"

APP_BASE_URL="http://localhost:8000"

# Turso Database Credentials
TURSO_DATABASE_URL="libsql://your-db-url.turso.io"
TURSO_AUTH_TOKEN="your_turso_token"
```

---

## 🎵 Optional Background Music

Drop a royalty-free track named:

```text
bg_music.mp3
```

Into:

```text
app/static/
```

Ultrex will automatically:

- Detect the file
- Loop it seamlessly
- Apply sidechain ducking when narration begins

---

## 🏃 Running the Engine

Always run with **one worker** to prevent scheduler collisions:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Open **Ultrex Studio**:

```text
http://localhost:8000
```

### Typical workflow

1. **Script Forge** — Enter a topic; the writer agent returns script + metadata.
2. **Studio** — Paste or use the generated script, pick niche and voice, click **Render Video**.
3. **Progress** — UI polls `/get_status/{job_id}` for image/audio/compile progress and scene storyboard.
4. **Publish** — After render, edit title/description/tags and call **Publish to YouTube** (requires OAuth files).

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves Ultrex Studio (`index.html`) |
| `POST` | `/writer/generate` | Script Forge — body: `{ "title": "topic" }` |
| `POST` | `/process_scene` | Start render pipeline — script, niche, optional voice |
| `GET` | `/get_status/{job_id}` | Job status, scenes, video URL, errors |
| `GET` | `/jobs` | List all jobs from Turso |
| `POST` | `/upload_to_youtube/{job_id}` | Upload finished MP4 — body: title, description, tags |

Static assets (generated media, CSS, JS) are served under `/static/`.

---

## 📁 Project Structure

```text
ULTREX/
├── app/
│   ├── database/
│   │   └── db_jobs.py          # Turso job CRUD & progress sync
│   ├── models/
│   │   └── scene.py            # Pydantic schemas
│   ├── prompts/
│   │   ├── agent.py            # Script Forge system prompts
│   │   ├── finance.py
│   │   ├── history.py
│   │   ├── motivation.py
│   │   └── script.py
│   ├── services/
│   │   ├── audio_llm.py        # Edge-TTS + voice map
│   │   ├── cleanup.py          # Janitor & per-job cleanup
│   │   ├── client.py           # Groq / env clients
│   │   ├── image_llm.py        # Pollinations integration
│   │   ├── scene_llm.py        # Scene breakdown
│   │   ├── video_compiler.py   # FFmpeg pipeline
│   │   ├── writer_agent.py     # LangGraph Script Forge
│   │   └── youtube_uploader.py # YouTube OAuth upload
│   ├── static/
│   │   ├── index.html          # Ultrex Studio shell
│   │   ├── app.js              # Studio logic & API client
│   │   ├── style.css
│   │   └── bg_music.mp3        # optional
│   ├── logging_config.py
│   └── main.py                 # FastAPI app & routes
├── client_secrets.json         # optional — YouTube OAuth (local only)
├── token.pickle                # optional — cached YouTube token (local only)
├── logs/
├── .env
├── .gitignore
├── render-build.sh
└── requirements.txt
```

---

## 📝 License

This project is intended for personal and educational use.

Before deploying commercially, ensure compliance with the terms of service of:

- Groq
- Pollinations AI
- Microsoft Edge TTS
- Google / YouTube APIs

---
