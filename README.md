# AI Interviewer — Resume-Aware Adaptive Interview Platform

A full-stack AI-powered interview practice platform built as a serious portfolio project. Upload your resume, paste a job description, and conduct a realistic video-style interview with an AI interviewer that evaluates your answers in real-time.

---

## ✨ Features

| Feature | Implementation |
|---------|---------------|
| Resume parsing (PDF/DOCX) | PyMuPDF + python-docx → LLM structured extraction |
| JD analysis | Qwen2.5 7B (Ollama) → Pydantic structured output |
| Hybrid skill matching | RapidFuzz fuzzy + SentenceTransformers semantic |
| Adaptive interview | LangGraph state machine with rule-based adaptive selection |
| AI voice | Deepgram Aura TTS (MP3 streamed) |
| Your camera + mic | Browser WebRTC + Web Speech API STT |
| Whiteboard | Miro embed (opens as overlay for system design) |
| Answer evaluation | LLM rubric (0–4 scale, 5 criteria) |
| Final report | Competency radar + bar charts, gap analysis |
| Persistence | Supabase (PostgreSQL + JSONB) |

---

## 🏗 Architecture

```
Frontend (React + Vite + Tailwind)
         │  HTTP /api/*
Backend (FastAPI + Python)
    ├── Document Processor (PyMuPDF / python-docx)
    ├── Resume Analyst → Ollama (qwen2.5:7b-instruct)
    ├── JD Analyst → Ollama
    ├── Hybrid Match Engine
    │     ├── RapidFuzz skill matching
    │     └── SentenceTransformers (bge-small-en-v1.5)
    ├── Interview Planner → Ollama
    ├── LangGraph state machine
    │     ├── select_question (rule-based adaptive)
    │     ├── evaluate_answer → Ollama
    │     └── decide_next (rule-based)
    ├── Deepgram TTS (AI voice)
    └── Supabase (PostgreSQL)
```

---

## 🚀 Setup (WSL)

### Prerequisites
- WSL (Ubuntu) with Python 3.11
- Ollama running on Windows with `qwen2.5:7b-instruct-q4_0`
- A [Supabase](https://supabase.com) project (free tier works)
- A [Deepgram](https://console.deepgram.com) API key (free tier: 12,000 min/year)
- Node.js 20+ in WSL

### 1. Clone and setup
```bash
# In WSL terminal, navigate to the project
cd /mnt/c/Keertha/javaProjects/interview-ai

# Run the one-shot setup script
bash setup_wsl.sh
```

### 2. Configure environment
```bash
cd backend
cp .env.example .env
nano .env   # Fill in DATABASE_URL, DEEPGRAM_API_KEY
```

Required `.env` values:
```env
DATABASE_URL=postgresql://postgres.xxxx:password@aws-0-us-east-1.pooler.supabase.com:6543/postgres
DEEPGRAM_API_KEY=your-key-here

# Already set — uses your local Ollama
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b-instruct-q4_0
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Run database migrations
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### 4. Start backend
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start frontend
```bash
cd frontend
npm install
npm run dev
```

### 6. Open the app
- **Frontend**: http://localhost:5173
- **API docs**: http://localhost:8000/docs

---

## 📡 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/resumes` | Upload + parse resume |
| POST | `/api/job-descriptions/analyze` | Analyze JD |
| POST | `/api/matches` | Run hybrid matching |
| GET  | `/api/matches/{id}` | Get match report |
| POST | `/api/interviews` | Create session + plan |
| GET  | `/api/interviews/{id}` | Get session state |
| GET  | `/api/interviews/{id}/question` | Get current question |
| GET  | `/api/interviews/{id}/question/audio` | Deepgram TTS audio |
| POST | `/api/interviews/{id}/answers` | Submit answer |
| POST | `/api/interviews/{id}/pause` | Pause session |
| POST | `/api/interviews/{id}/resume` | Resume session |
| POST | `/api/interviews/{id}/end` | End early |
| GET  | `/api/interviews/{id}/report` | Final report |
| DELETE | `/api/interviews/{id}` | Delete session |
| GET  | `/api/interviews` | List sessions |

---

## 🧪 Run Tests
```bash
cd backend
source .venv/bin/activate
pytest tests/unit/ -v
```

---

## 🎯 Matching Algorithm

Weights (configurable in `.env`):
- **45%** Required skill coverage (RapidFuzz fuzzy matching)
- **25%** Evidence strength (LLM confidence scores)
- **20%** Semantic relevance (cosine similarity, bge-small-en-v1.5)
- **10%** Experience alignment (years of experience heuristic)

Scores are **NOT** validated hiring predictions — they reflect textual overlap only.

---

## ⚠️ Known Limitations

1. **Ollama latency**: Qwen 7B is slower than cloud APIs (~5–15s per question). Consider `qwen2.5-coder:7b` for coding-heavy interviews.
2. **Scanned PDFs**: OCR not included. Text-based PDFs only.
3. **STT browser support**: Web Speech API works in Chrome/Edge. Firefox needs a polyfill.
4. **Miro whiteboard**: Requires a Miro account. Opens as iframe overlay.
5. **Single-user**: No authentication. Suitable for local practice only.
6. **LangGraph resume**: Graph state is serialized to Supabase JSONB — large states may approach column limits.

---

## 🔮 Future Improvements

- [ ] Voice-first mode (Deepgram STT instead of Web Speech API)
- [ ] Resume OCR for scanned documents (Tesseract)
- [ ] User authentication (Supabase Auth)
- [ ] Export report as PDF
- [ ] Interview recording playback
- [ ] Custom question bank
- [ ] Multi-language support
