"""FastAPI application entry point."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import interviews, job_descriptions, matches, resumes
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="AI Interviewer API",
    description=(
        "Resume-aware adaptive interview platform. "
        "Uses Ollama (qwen2.5:7b-instruct) for LLM, "
        "Deepgram for TTS, and Supabase for persistence."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(resumes.router)
app.include_router(job_descriptions.router)
app.include_router(matches.router)
app.include_router(interviews.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


@app.on_event("startup")
async def startup():
    logger.info("AI Interviewer API starting up.")
    logger.info(f"LLM: {settings.LLM_PROVIDER}/{settings.LLM_MODEL}")
    logger.info(f"DB: {settings.DATABASE_URL[:40]}...")
    if not settings.DEEPGRAM_API_KEY:
        logger.warning("DEEPGRAM_API_KEY not set — TTS will be disabled. Questions shown as text only.")
