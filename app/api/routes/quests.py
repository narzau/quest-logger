import datetime
import logging

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.api import deps
from app.services import gamification_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.speech_to_text.factory import STTServiceFactory, get_stt_factory
from app.services.voice_quest_service import VoiceQuestService, get_voice_quest_service
from app.core.config import settings

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/", response_model=List[schemas.Quest])
def read_quests(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    quest_type: Optional[str] = Query(None),
    is_completed: Optional[bool] = Query(None),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve quests.
    """
    query = db.query(models.Quest).filter(models.Quest.owner_id == current_user.id)

    if quest_type:
        query = query.filter(models.Quest.quest_type == quest_type)
    if is_completed is not None:
        query = query.filter(models.Quest.is_completed == is_completed)

    quests = query.offset(skip).limit(limit).all()
    return quests


@router.post("/", response_model=schemas.Quest)
def create_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_in: schemas.QuestCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new quest.
    """
    # Calculate exp reward based on quest properties
    exp_reward = gamification_service.calculate_quest_exp_reward(
        rarity=quest_in.rarity,
        quest_type=quest_in.quest_type,
        priority=quest_in.priority,
    )
    quest = models.Quest(
        **quest_in.model_dump(exclude={"exp_reward"}),
        owner_id=current_user.id,
        exp_reward=exp_reward,
    )
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


@router.put("/{quest_id}", response_model=schemas.Quest)
def update_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    quest_in: schemas.QuestUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    was_completed_before = quest.is_completed
    completion_time = datetime.datetime.now(datetime.timezone.utc)

    # Update quest fields
    for field in quest_in.model_dump(exclude_unset=True):
        setattr(quest, field, getattr(quest_in, field))

    if not was_completed_before and quest.is_completed:
        quest.completed_at = completion_time
        current_user.experience += quest.exp_reward
        db.add(current_user)
        db.commit()  # Commit XP update first

        # Check for level-based achievements
        level_up = gamification_service.check_and_apply_level_up(db, current_user)

        # Update quest-specific achievements
        update_quest_achievements(db, current_user, quest, completion_time)

        # Explicit achievement check
        gamification_service.check_achievements(db, current_user)

    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


def update_quest_achievements(
    db: Session, user: models.User, quest: models.Quest, completion_time: datetime
):
    # General quest completion
    gamification_service.update_progress_and_check_achievements(
        db=db, user=user, criterion_type="quests_completed", amount=1
    )

    # Type-specific achievements
    if quest.quest_type == models.QuestType.BOSS:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="boss_quests_completed", amount=1
        )
    elif quest.quest_type == models.QuestType.EPIC:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="legendary_quests_completed", amount=1
        )

    # Time-based achievements
    completion_hour = completion_time.hour
    if completion_hour < 8:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="early_morning_completion", amount=1
        )
    elif completion_hour >= 22:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="late_night_completion", amount=1
        )

    # Rarity-based achievements
    if quest.rarity == models.QuestRarity.LEGENDARY:
        gamification_service.update_progress_and_check_achievements(
            db=db, user=user, criterion_type="legendary_quests_completed", amount=1
        )


@router.get("/{quest_id}", response_model=schemas.Quest)
def read_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get quest by ID.
    """
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    return quest


@router.delete("/{quest_id}", response_model=schemas.Quest)
def delete_quest(
    *,
    db: Session = Depends(deps.get_db),
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a quest.
    """
    quest = (
        db.query(models.Quest)
        .filter(models.Quest.id == quest_id, models.Quest.owner_id == current_user.id)
        .first()
    )

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    db.delete(quest)
    db.commit()
    return quest


@router.post("/voice-generation/auto", response_model=schemas.Quest)
async def create_quest_from_voice(
    *,
    db: Session = Depends(deps.get_db),
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stt_provider: Optional[str] = Form(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    voice_service: VoiceQuestService = Depends(get_voice_quest_service),
    llm_service: LLMService = Depends(get_llm_service),
    stt_factory: STTServiceFactory = Depends(get_stt_factory),
) -> Any:
    """
    Create a new quest from voice input.

    - **audio_file**: Audio recording (supported formats: wav, mp3, webm, ogg)
    - **language**: Optional language hint (ISO code like 'en', 'es', 'fr')
    - **stt_provider**: Optional STT provider override (whisper, google, assembly, deepgram)
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

    # Check if specified provider is available
    if stt_provider:
        available_providers = stt_factory.get_available_providers()
        if (
            stt_provider not in available_providers
            or not available_providers[stt_provider]
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Requested STT provider '{stt_provider}' is not configured. Available providers: {[p for p, available in available_providers.items() if available]}",
            )

    try:
        # Step 1: Transcribe the audio (now using injected service)
        logger.info(
            f"Transcribing audio with provider={stt_provider or 'default'}, language={language or 'auto-detect'}"
        )
        transcription_result = await voice_service.get_transcription(
            audio_file=audio_file,
            language=language,
            provider=stt_provider,
            translate_to_english=False,  # We'll handle translation separately
        )

        text = transcription_result["text"]
        detected_language = transcription_result["language_detected"]

        logger.info(
            f"Transcription completed: '{text[:100]}...' (language={detected_language or 'unknown'})"
        )

        # Step 2: Translate if not in English (now using injected service)
        translated_text = text
        if detected_language and detected_language.lower() not in [
            "en",
            "eng",
            "en-us",
            "english",
        ]:
            logger.info(f"Translating from {detected_language} to English")
            translated_text = await llm_service.translate_text(
                text, language or detected_language
            )
            logger.info(f"Translation completed: '{translated_text[:100]}...'")
        else:
            logger.info("No translation needed (already in English)")

        # Step 3: Parse the text into a quest (now using injected service)
        logger.info("Parsing text into quest structure")
        quest_in = await llm_service.parse_quest_from_text(translated_text)
        logger.info(
            f"Parsed quest: '{quest_in.title}' (type={quest_in.quest_type.value}, rarity={quest_in.rarity.value})"
        )

        # Step 4: Calculate exp reward based on quest properties
        exp_reward = gamification_service.calculate_quest_exp_reward(
            rarity=quest_in.rarity,
            quest_type=quest_in.quest_type,
            priority=quest_in.priority,
        )

        # Step 5: Create the quest
        quest = models.Quest(
            **quest_in.model_dump(exclude={"exp_reward"}),
            owner_id=current_user.id,
            exp_reward=exp_reward,
        )

        db.add(quest)
        db.commit()
        db.refresh(quest)

        logger.info(f"Quest created successfully with ID {quest.id}")
        return quest

    except Exception as e:
        logger.error(f"Error processing voice input: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing voice input: {str(e)}",
        )


@router.post("/voice-generation/suggest", response_model=schemas.QuestCreate)
async def suggest_quest_from_voice(
    *,
    db: Session = Depends(deps.get_db),
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    stt_provider: Optional[str] = Form(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    voice_service: VoiceQuestService = Depends(get_voice_quest_service),
    llm_service: LLMService = Depends(get_llm_service),
    stt_factory: STTServiceFactory = Depends(get_stt_factory),
) -> Any:
    """
    Create a new quest from voice input.

    - **audio_file**: Audio recording (supported formats: wav, mp3, webm, ogg)
    - **language**: Optional language hint (ISO code like 'en', 'es', 'fr')
    - **stt_provider**: Optional STT provider override (whisper, google, assembly, deepgram)
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

    # Check if specified provider is available
    if stt_provider:
        available_providers = stt_factory.get_available_providers()
        if (
            stt_provider not in available_providers
            or not available_providers[stt_provider]
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Requested STT provider '{stt_provider}' is not configured. Available providers: {[p for p, available in available_providers.items() if available]}",
            )

    try:
        # Step 1: Transcribe the audio (now using injected service)
        logger.info(
            f"Transcribing audio with provider={stt_provider or 'default'}, language={language or 'auto-detect'}"
        )
        transcription_result = await voice_service.get_transcription(
            audio_file=audio_file,
            language=language,
            provider=stt_provider,
            translate_to_english=False,  # We'll handle translation separately
        )

        text = transcription_result["text"]
        detected_language = transcription_result["language_detected"]

        logger.info(
            f"Transcription completed: '{text[:100]}...' (language={detected_language or 'unknown'})"
        )

        # Step 2: Translate if not in English (now using injected service)
        translated_text = text
        if detected_language and detected_language.lower() not in [
            "en",
            "eng",
            "en-us",
            "english",
        ]:
            logger.info(f"Translating from {detected_language} to English")
            translated_text = await llm_service.translate_text(
                text, language or detected_language
            )
            logger.info(f"Translation completed: '{translated_text[:100]}...'")
        else:
            logger.info("No translation needed (already in English)")

        # Step 3: Parse the text into a quest (now using injected service)
        logger.info("Parsing text into quest structure")
        quest_in = await llm_service.parse_quest_from_text(translated_text)
        logger.info(
            f"Parsed quest: '{quest_in.title}' (type={quest_in.quest_type.value}, rarity={quest_in.rarity.value})"
        )

        # Step 4: Calculate exp reward based on quest properties
        quest_in.exp_reward = gamification_service.calculate_quest_exp_reward(
            rarity=quest_in.rarity,
            quest_type=quest_in.quest_type,
            priority=quest_in.priority,
        )

        return quest_in

    except Exception as e:
        logger.error(f"Error processing voice input: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing voice input: {str(e)}",
        )
