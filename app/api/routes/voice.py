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


@router.post("/transcribe", response_model=Dict[str, Any])
async def transcribe_audio(
    *,
    db: Session = Depends(deps.get_db),
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stt_provider: Optional[str] = Form(None),
    translate_to_english: bool = Form(False),
    current_user: models.User = Depends(deps.get_current_active_user),
    voice_service: VoiceQuestService = Depends(get_voice_quest_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> Any:
    """
    Transcribe audio without creating a quest.

    Useful for testing or troubleshooting the speech-to-text functionality.

    - **audio_file**: Audio recording (supported formats: wav, mp3, webm, ogg)
    - **language**: Optional language hint (ISO code like 'en', 'es', 'fr')
    - **stt_provider**: Optional STT provider override
    - **translate_to_english**: Whether to translate non-English results to English
    """
    if not settings.ENABLE_VOICE_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="Voice features are not enabled on this server.",
        )

    # Validate content type
    valid_content_types = [
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/mp3",
        "audio/mpeg",
        "audio/webm",
        "audio/ogg",
        "audio/x-m4a",
    ]

    if audio_file.content_type not in valid_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {audio_file.content_type}. Supported formats: WAV, MP3, WebM, OGG, M4A",
        )

    try:
        # Get just the transcription using injected service
        transcription_result = await voice_service.get_transcription(
            audio_file=audio_file,
            language=language,
            provider=stt_provider,
            translate_to_english=False,  # We'll handle translation separately if needed
        )

        # Get the detected language
        text = transcription_result["text"]
        detected_language = transcription_result["language_detected"]

        # Handle translation if requested
        translated_text = None
        if (
            translate_to_english
            and detected_language
            and detected_language.lower() not in ["en", "eng", "en-us", "english"]
        ):
            translated_text = await llm_service.translate_to_english(
                text, detected_language
            )
            transcription_result["translation"] = translated_text

        return transcription_result

    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error transcribing audio: {str(e)}",
        )
