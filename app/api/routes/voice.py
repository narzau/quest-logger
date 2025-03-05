# app/api/routes/voice.py
import logging

from typing import Any, Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import deps
from app.services.llm_service import LLMService, get_llm_service
from app.services.voice_quest_service import VoiceQuestService, get_voice_quest_service
from app.services.speech_to_text.factory import STTServiceFactory
from app.services import gamification_service
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/providers", response_model=Dict[str, bool])
async def get_available_stt_providers(
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get list of available speech-to-text providers.

    Returns a dictionary mapping provider names to whether they are configured.
    """
    if not settings.ENABLE_VOICE_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="Voice features are not enabled on this server.",
        )

    # Get available providers from factory
    return STTServiceFactory.get_available_providers()


@router.get("/languages", response_model=List[Dict[str, str]])
async def get_supported_languages(
    provider: Optional[str] = Query(None),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get list of supported languages for the specified provider or default provider.

    Returns a list of language objects with code and name.
    """
    if not settings.ENABLE_VOICE_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="Voice features are not enabled on this server.",
        )

    # Use specified provider or default
    provider_name = provider or settings.DEFAULT_STT_PROVIDER

    # Deepgram supported languages
    if provider_name.lower() == "deepgram":
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "zh", "name": "Chinese"},
            {"code": "nl", "name": "Dutch"},
            {"code": "hi", "name": "Hindi"},
            {"code": "ar", "name": "Arabic"},
            {"code": "id", "name": "Indonesian"},
            {"code": "pl", "name": "Polish"},
            {"code": "tr", "name": "Turkish"},
            {"code": "uk", "name": "Ukrainian"},
            {"code": "cs", "name": "Czech"},
            {"code": "da", "name": "Danish"},
            {"code": "fi", "name": "Finnish"},
            {"code": "no", "name": "Norwegian"},
            {"code": "sv", "name": "Swedish"},
            {"code": "el", "name": "Greek"},
            {"code": "th", "name": "Thai"},
            {"code": "vi", "name": "Vietnamese"},
        ]
    # Whisper supported languages (partial list)
    elif provider_name.lower() == "whisper":
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "zh", "name": "Chinese"},
            # Add more based on Whisper's supported languages
        ]
    else:
        # Default list for other providers
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
        ]

