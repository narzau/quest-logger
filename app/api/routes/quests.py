# app/api/routes/quests.py
from typing import Any, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from app import models, schemas
from app.api import deps
from app.core.exceptions import ProcessingException, BusinessException
from app.core.config import settings
from app.services.quest_service import QuestService

router = APIRouter()


@router.get("/", response_model=List[schemas.Quest])
def read_quests(
    skip: int = 0,
    limit: int = 100,
    quest_type: Optional[str] = Query(None),
    is_completed: Optional[bool] = Query(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Retrieve quests.
    """
    quests = quest_service.get_quests(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        quest_type=quest_type,
        is_completed=is_completed,
    )
    return quests


@router.post("/", response_model=schemas.Quest)
def create_quest(
    *,
    quest_in: schemas.QuestCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Create new quest.
    """
    quest = quest_service.create_quest(user_id=current_user.id, quest_data=quest_in)
    return quest


@router.put("/{quest_id}", response_model=schemas.Quest)
def update_quest(
    *,
    quest_id: int,
    quest_in: schemas.QuestUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Update a quest.
    """
    quest = quest_service.update_quest(
        user_id=current_user.id, quest_id=quest_id, update_data=quest_in
    )
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    return quest


@router.get("/{quest_id}", response_model=schemas.Quest)
def read_quest(
    *,
    quest_id: int,
    current_user=Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Get quest by ID.
    """
    quest = quest_service.get_quest(current_user.id, quest_id)

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    return quest


@router.delete("/{quest_id}", response_model=schemas.Quest)
def delete_quest(
    *,
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Delete a quest.
    """
    # First get the quest to return it
    quest = quest_service.get_quest(current_user.id, quest_id)

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    # Then delete it
    success = quest_service.delete_quest(current_user.id, quest_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete quest")

    return quest


@router.get("/{quest_id}/calendar-link")
def get_quest_calendar_link(
    *,
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Get a direct link to the Google Calendar event for a quest.
    """
    # Get the quest
    quest = quest_service.get_quest(current_user.id, quest_id)

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    if not quest.google_calendar_event_id:
        raise HTTPException(status_code=404, detail="No calendar event for this quest")

    # TODO: Implement a method to get direct calendar event link
    # This would be added to the GoogleCalendarService

    # For now, just return the event ID as a placeholder
    return {
        "calendar_event_id": quest.google_calendar_event_id,
        "message": "Calendar link functionality coming soon",
    }


@router.post("/voice-generation/auto", response_model=schemas.Quest)
async def create_quest_from_voice(
    *,
    audio_file: UploadFile = File(...),
    google_calendar: Optional[bool] = Form(False),
    language: Optional[str] = Form(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service),
) -> Any:
    """
    Create a new quest from voice input.

    - **audio_file**: Audio recording (supported formats: wav, mp3, webm, ogg)
    - **google_calendar**: Create a Google Calendar event
    - **language**: Optional language hint (ISO code like 'en', 'es', 'fr')
    """

    # Validate audio file
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
        return await quest_service.create_quest_from_audio(
            user_id=current_user.id,
            audio_file=audio_file,
            language=language,
            google_calendar=google_calendar,
        )
    except ProcessingException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BusinessException as e:
        raise HTTPException(status_code=400, detail=str(e))


# @router.post("/voice-generation/suggest", response_model=schemas.QuestCreate)
# async def suggest_quest_from_voice(
#     *,
#     audio_file: UploadFile = File(...),
#     language: Optional[str] = Form(None),
#     current_user: models.User = Depends(deps.get_current_active_user),
#     quest_service: QuestService = Depends(deps.get_quest_service()),
# ) -> Any:
#     """
#     Create a new quest from voice input.

#     - **audio_file**: Audio recording (supported formats: wav, mp3, webm, ogg)
#     - **language**: Optional language hint (ISO code like 'en', 'es', 'fr')
#     """
#     quest = quest_service.suggest_quest_from_voice(
#         user_id=current_user.id,
#         audio_file=audio_file,
#         language=language,
#     )
#     return quest
