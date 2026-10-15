"""
Deepgram TTS service: converts AI interviewer text to speech.
Returns audio bytes (MP3/WAV) which the frontend plays directly.
Falls back to a clear error if API key is missing.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"


async def text_to_speech(
    text: str,
    model: str = "aura-asteria-en",  # Deepgram Aura model
    encoding: str = "mp3",
) -> Optional[bytes]:
    """
    Convert text to speech using Deepgram Aura TTS.
    Returns MP3 audio bytes, or None if TTS is unavailable.

    Models available: aura-asteria-en, aura-luna-en, aura-stella-en, aura-zeus-en
    """
    if not settings.DEEPGRAM_API_KEY:
        logger.warning("DEEPGRAM_API_KEY not set. TTS unavailable.")
        return None

    if not text or not text.strip():
        return None

    # Limit text length to avoid excessive API usage
    text = text[:2000]

    headers = {
        "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
    }

    params = {
        "model": model,
        "encoding": encoding,
        "container": "mp3" if encoding == "mp3" else "wav",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DEEPGRAM_TTS_URL,
                json=payload,
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.content

    except httpx.HTTPStatusError as e:
        logger.error(f"Deepgram TTS HTTP error: {e.response.status_code} — {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Deepgram TTS request error: {e}")
        return None
