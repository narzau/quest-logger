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
    ) -> Dict[str, Any]:
        """
        Get just the transcription without creating a quest

        Useful for debugging or providing a preview
        """
        stt_service = STTServiceFactory.create()  # uses default provider from

        # Transcribe the audio (no translation yet)
        transcription = await stt_service.transcribe(
            audio_file=audio_file, language=language
        )

        return {
            "text": transcription.text,
            "language": language,
            "confidence": transcription.confidence,
        }


def get_voice_quest_service() -> VoiceQuestService:
    """
    Provides a VoiceQuestService instance for dependency injection.
    """
    return VoiceQuestService()
