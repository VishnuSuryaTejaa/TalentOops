"""Speech Engine (STT & TTS) with low-latency non-blocking async execution.

Providers:
  STT: "deepgram" — Deepgram Nova-2 REST API (requires DEEPGRAM_API_KEY in .env)

  TTS: "google"   — Google Cloud TTS (requires GOOGLE_APPLICATION_CREDENTIALS or GEMINI_API_KEY)
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

logger = logging.getLogger("talentops.speech_engine")


def _detect_audio_content_type(audio_bytes: bytes) -> str:
    """Detect audio container format from binary header bytes or default to application/octet-stream."""
    if audio_bytes.startswith(b"RIFF"):
        return "audio/wav"
    if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if audio_bytes.startswith(b"OggS"):
        return "audio/ogg"
    if audio_bytes.startswith(b"ID3") or audio_bytes.startswith(b"\xff\xfb") or audio_bytes.startswith(b"\xff\xf3"):
        return "audio/mp3"
    if audio_bytes.startswith(b"fLaC"):
        return "audio/flac"
    return "application/octet-stream"


class STTService:
    """Async Speech-to-Text service for candidate audio transcription."""

    def __init__(self, provider: str = "deepgram"):
        self.provider = provider

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text string (non-blocking async)."""
        if not audio_bytes:
            return ""

        try:
            return await asyncio.to_thread(self._transcribe_sync, audio_bytes)
        except Exception as e:
            logger.error("STT transcription error (provider=%s): %s", self.provider, e)
            raise RuntimeError(f"STT transcription failed (provider={self.provider}): {e}") from e

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        if self.provider == "deepgram":
            from app.config import get_settings
            settings = get_settings()
            if getattr(settings, "DEEPGRAM_API_KEY", ""):
                return self._transcribe_deepgram(audio_bytes)
            else:
                return self._transcribe_whisper(audio_bytes)
        raise ValueError(f"Unknown STT provider: {self.provider}")

    def _transcribe_deepgram(self, audio_bytes: bytes) -> str:
        """Call Deepgram Nova-2 REST API for speech-to-text transcription."""
        import httpx
        from app.config import get_settings
        settings = get_settings()

        api_key = getattr(settings, "DEEPGRAM_API_KEY", "") or ""
        if not api_key:
            raise ValueError("[deepgram-stt] DEEPGRAM_API_KEY is not set. Real API execution is enforced.")

        content_type = _detect_audio_content_type(audio_bytes)
        url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&filler_words=true&endpointing=500"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        }
        try:
            response = httpx.post(url, content=audio_bytes, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            transcript = (
                data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )
            logger.info("[deepgram-stt] Transcribed %d bytes -> %d chars", len(audio_bytes), len(transcript))
            return transcript or ""
        except Exception as exc:
            logger.warning("[deepgram-stt] Deepgram API call failed: %s", exc)
            return ""

    def _transcribe_whisper(self, audio_bytes: bytes) -> str:
        """Call Groq Whisper for speech-to-text transcription as fallback."""
        import httpx
        from app.config import get_settings
        settings = get_settings()

        api_key = settings.groq_api_keys[0] if settings.groq_api_keys else ""
        if not api_key:
            logger.warning("[whisper-stt] Groq API key is not set for Whisper fallback.")
            return ""

        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "model": "whisper-large-v3"
        }
        try:
            response = httpx.post(url, headers=headers, files=files, data=data, timeout=30.0)
            response.raise_for_status()
            transcript = response.json().get("text", "")
            logger.info("[whisper-stt] Transcribed %d bytes -> %d chars", len(audio_bytes), len(transcript))
            return transcript
        except Exception as exc:
            logger.warning("[whisper-stt] Whisper API call failed: %s", exc)
            return ""


class TTSService:
    """Async Text-to-Speech service for generating spoken audio questions."""

    def __init__(self, provider: str = "openai"):
        self.provider = provider

    async def synthesize_speech(self, text: str) -> bytes:
        """Synthesize text string into spoken audio frame bytes (non-blocking async)."""
        if not text:
            return b""

        try:
            return await asyncio.to_thread(self._synthesize_sync, text)
        except Exception as e:
            logger.error("TTS synthesis error (provider=%s): %s", self.provider, e)
            raise RuntimeError(f"TTS synthesis failed (provider={self.provider}): {e}") from e

    def _synthesize_sync(self, text: str) -> bytes:
        if self.provider == "openai":
            try:
                return self._synthesize_openai(text)
            except Exception as e:
                logger.warning("[openai-tts] Failed, falling back to google: %s", e)
                return self._synthesize_google(text)
        if self.provider == "google":
            return self._synthesize_google(text)
        raise ValueError(f"Unknown TTS provider: {self.provider}")

    def _synthesize_openai(self, text: str) -> bytes:
        """Call OpenAI TTS API for natural speech synthesis."""
        import httpx
        from app.config import get_settings
        settings = get_settings()

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("[openai-tts] OPENAI_API_KEY is not set.")

        import re
        clean_text = re.sub(r'[*_#`]', '', text).strip()

        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "tts-1",
            "input": clean_text,
            "voice": "shimmer",
            "response_format": "mp3"
        }
        
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            audio_bytes = response.content
            logger.info("[openai-tts] Synthesized %d chars -> %d bytes audio", len(text), len(audio_bytes))
            return audio_bytes
        except Exception as exc:
            logger.warning("[openai-tts] OpenAI API call failed: %s", exc)
            raise

    def _synthesize_google(self, text: str) -> bytes:
        """Call Google Cloud Text-to-Speech API for real audio synthesis."""
        import httpx
        from app.config import get_settings
        settings = get_settings()

        api_key = (
            getattr(settings, "GOOGLE_TTS_API_KEY", "")
            or getattr(settings, "GOOGLE_CLOUD_API_KEY", "")
            or getattr(settings, "GEMINI_API_KEY", "")
            or ""
        )
        if not api_key:
            raise ValueError("[google-tts] No Google Cloud TTS API key configured. Real API execution is enforced.")

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
        import re
        # Strip markdown (asterisks, underscores, hashes) which can cause TTS to glitch or fallback
        clean_text = re.sub(r'[*_#`]', '', text).strip()
        
        payload = {
            "input": {"ssml": f"<speak><prosody rate='90%'>{clean_text}</prosody></speak>"},
            "voice": {"languageCode": "en-US", "name": "en-US-Journey-F"},
            "audioConfig": {"audioEncoding": "MP3"},
        }
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            audio_content = response.json().get("audioContent", "")
            audio_bytes = base64.b64decode(audio_content)
            logger.info("[google-tts] Synthesized %d chars -> %d bytes audio", len(text), len(audio_bytes))
            return audio_bytes
        except Exception as exc:
            logger.warning("[google-tts] Google Cloud TTS API call failed: %s", exc)
            return b""

    async def synthesize_speech_b64(self, text: str) -> str | None:
        audio_bytes = await self.synthesize_speech(text)
        if not audio_bytes:
            return None
        return base64.b64encode(audio_bytes).decode("utf-8")


def handle_barge_in(session_id: str) -> dict[str, Any]:
    """Handle candidate interruption (barge-in) during active agent speech playback."""
    logger.info("Barge-in / interruption detected for session: %s", session_id)
    return {"session_id": session_id, "interrupted": True, "action": "stop_tts_playback"}
