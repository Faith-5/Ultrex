# 🎬 Ultrex - AI Shorts Engine

Ultrex is an enterprise-grade, fully automated AI video production pipeline. It takes a raw text script and autonomously breaks it into scenes, generates cinematic images, synthesizes highly emotive TTS audio, and leverages C-level FFmpeg hardware acceleration to compile a publish-ready 9:16 vertical short (with TikTok-style subtitles, Ken Burns motion, and audio ducking) in under 30 seconds.

Built for zero-budget scalability, it uses entirely free, unthrottled endpoints and local CPU rendering.

---

## 🚀 Features

- **LLM Scene Breakdown (Llama 3.3 70B):**  
  Intelligently splits scripts into 8-beat psychological arcs with specific camera angles, lighting, and color palettes.

- **Visual Coherence Engine:**  
  Injects a strict "Style Bible" and locks generation seeds so every scene looks like it was shot on the same camera, by the same director.

- **Hardware-Accelerated Compilation (FFmpeg):**  
  Bypasses slow Python wrappers (like MoviePy). Uses native FFmpeg filtergraphs to render dynamic Ken Burns motion, color grading, and smooth cuts instantly.

- **Advanced `.ASS` Subtitles:**  
  Natively burns TikTok/Reels-style captions with dark semi-transparent bounding boxes directly into the video stream.

- **Crash-Proof State (Turso SQLite):**  
  Uses an edge database to track job states. If the server restarts, no video generation history is lost.

- **Tiered Janitor System:**  
  Automatically sweeps and deletes heavy `.mp4`, `.png`, and `.mp3` assets in the background using APScheduler to prevent disk failure.

---

## 🛠️ Architecture & Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python) |
| Database | Turso (libSQL) |
| LLM Engine | Groq API (Llama-3.3-70b-versatile) |
| Image Generation | Pollinations AI (Flux Model) |
| Audio Generation | Edge-TTS (Microsoft Azure Neural Voices) |
| Video Compiler | Native FFmpeg (Subprocess) |
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

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Faith-5/Ultrex.git
cd ultrex
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

Once running, open:

```text
http://localhost:8000
```

---

## 📁 Project Structure

```text
ULTREX/
├── app/
│   ├── database/
│   │   └── db_jobs.py          # Turso database operations
│   ├── models/
│   │   └── scene.py            # Pydantic schemas
│   ├── prompts/
│   │   ├── finance.py
│   │   ├── history.py
│   │   └── motivation.py
│   ├── services/
│   │   ├── audio_llm.py        # Edge-TTS integration
│   │   ├── cleanup.py          # Background janitor
│   │   ├── client.py           # API clients
│   │   ├── image_llm.py        # Pollinations integration
│   │   ├── scene_llm.py        # Groq scene generation
│   │   └── video_compiler.py   # FFmpeg pipeline
│   ├── static/
│   │   ├── index.html
│   │   └── bg_music.mp3
│   ├── logging_config.py
│   └── main.py
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

---