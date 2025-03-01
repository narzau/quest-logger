# app/services/voice_quest_service.py
from typing import Optional, Dict, Any
from fastapi import UploadFile
import logging

from app.services.speech_to_text.factory import STTServiceFactory
from app.services.llm_service import LLMService
from app.schemas.quest import QuestCreate
from app.core.config import settings


logger = logging.getLogger(__name__)


class VoiceQuestService:
    """
    Service to process voice recordings into quests
    """

    def __init__(self):
        self.llm_service = LLMService()

    async def get_transcription(
        self,
        audio_file: UploadFile,
        language: Optional[str] = None,
        provider: Optional[str] = None,
        translate_to_english: bool = False,
    ) -> Dict[str, Any]:
        """
        Get just the transcription without creating a quest

        Useful for debugging or providing a preview
        """
        # Create the appropriate STT service
        stt_service = STTServiceFactory.create(provider)

        # Transcribe the audio (no translation yet)
        transcription = await stt_service.transcribe(
            audio_file=audio_file,
            language=language,
            translate_to_english=False,  # We'll handle translation separately if needed
        )

        # Get the detected language
        detected_language = transcription.language_detected or language or "en"

        # Handle translation if requested
        translated_text = None
        if (
            translate_to_english
            and detected_language
            and detected_language.lower() not in ["en", "eng", "en-us", "english"]
        ):
            translated_text = await self.llm_service.translate_to_english(
                transcription.text, detected_language
            )

        # Return formatted result
        return {
            "text": transcription.text,
            "language_detected": detected_language,
            "confidence": transcription.confidence,
            "translation": translated_text,
        }


def get_voice_quest_service() -> VoiceQuestService:
    """
    Provides a VoiceQuestService instance for dependency injection.
    """
    return VoiceQuestService()
