# app/api/routes/quests.py
from typing import Any, List, Optional
import logging

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
from app.core.logging import log_context
from app.schemas.subscription import SubscriptionStatus

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[schemas.Quest])
def read_quests(
    skip: int = 0,
    limit: int = 100,
    quest_type: Optional[str] = Query(None),
    is_completed: Optional[bool] = Query(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Retrieve quests.
    """
    with log_context(
        user_id=current_user.id,
        action="list_quests",
        quest_type=quest_type,
        is_completed=is_completed,
    ):
        logger.info(f"User {current_user.id} retrieving quests")
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
    quest_service: QuestService = Depends(deps.get_quest_service()),
    subscription_status: SubscriptionStatus = Depends(deps.validate_active_subscription),
) -> Any:
    """
    Create new quest - requires active subscription.
    """
    with log_context(
        user_id=current_user.id, action="create_quest", quest_title=quest_in.title
    ):
        logger.info(f"User {current_user.id} creating quest: {quest_in.title}")
        try:
            return quest_service.create_quest(
                user_id=current_user.id, quest_data=quest_in
            )
        except BusinessException as e:
            logger.warning(f"Error creating quest: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.put("/{quest_id}", response_model=schemas.Quest)
def update_quest(
    *,
    quest_id: int,
    quest_in: schemas.QuestUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Update a quest.
    """
    with log_context(user_id=current_user.id, action="update_quest", quest_id=quest_id):
        logger.info(f"User {current_user.id} updating quest {quest_id}")
        try:
            return quest_service.update_quest(
                user_id=current_user.id, quest_id=quest_id, update_data=quest_in
            )
        except BusinessException as e:
            logger.warning(f"Error updating quest {quest_id}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/{quest_id}", response_model=schemas.Quest)
def read_quest(
    *,
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Get quest by ID.
    """
    with log_context(user_id=current_user.id, action="get_quest", quest_id=quest_id):
        logger.info(f"User {current_user.id} retrieving quest {quest_id}")
        try:
            return quest_service.get_quest(user_id=current_user.id, quest_id=quest_id)
        except BusinessException as e:
            logger.warning(f"Error retrieving quest {quest_id}: {str(e)}")
            raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{quest_id}", response_model=schemas.Quest)
def delete_quest(
    *,
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Delete a quest.
    """
    with log_context(user_id=current_user.id, action="delete_quest", quest_id=quest_id):
        logger.info(f"User {current_user.id} deleting quest {quest_id}")
        try:
            return quest_service.delete_quest(
                user_id=current_user.id, quest_id=quest_id
            )
        except BusinessException as e:
            logger.warning(f"Error deleting quest {quest_id}: {str(e)}")
            raise HTTPException(status_code=404, detail=str(e))


@router.get("/{quest_id}/calendar-link")
def get_quest_calendar_link(
    *,
    quest_id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Get a direct link to the Google Calendar event for a quest.
    """
    with log_context(
        user_id=current_user.id, action="get_calendar_link", quest_id=quest_id
    ):
        logger.info(
            f"User {current_user.id} retrieving calendar link for quest {quest_id}"
        )
        try:
            # Get the quest
            quest = quest_service.get_quest(user_id=current_user.id, quest_id=quest_id)

            if not quest.google_calendar_event_id:
                logger.info(f"No calendar event exists for quest {quest_id}")
                raise HTTPException(
                    status_code=404, detail="No calendar event for this quest"
                )

            # TODO: Implement a method to get direct calendar event link
            # This would be added to the GoogleCalendarService

            # For now, just return the event ID as a placeholder
            return {
                "calendar_event_id": quest.google_calendar_event_id,
                "message": "Calendar link functionality coming soon",
            }
        except BusinessException as e:
            logger.warning(
                f"Error retrieving calendar link for quest {quest_id}: {str(e)}"
            )
            raise HTTPException(status_code=404, detail=str(e))


@router.post("/voice-generation/auto", response_model=schemas.Quest)
async def create_quest_from_voice(
    *,
    audio_file: UploadFile = File(...),
    google_calendar: Optional[bool] = Form(False),
    language: Optional[str] = Form(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    gen_access: tuple[SubscriptionStatus, float] = Depends(deps.validate_audio_gen_access),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Create a new quest from voice input using AI processing.

    Automatically creates quest with details extracted from the voice recording.
    """
    with log_context(
        user_id=current_user.id,
        action="create_quest_from_voice",
        filename=audio_file.filename,
        google_calendar=google_calendar,
    ):
        logger.info(
            f"User {current_user.id} creating quest from voice file: {audio_file.filename}"
        )
        try:
            _subscription_status, audio_duration_minutes = gen_access
            return await quest_service.create_quest_from_voice(
                user_id=current_user.id,
                audio_file=audio_file,
                google_calendar=google_calendar,
                language=language,
                audio_duration_minutes=audio_duration_minutes,
            )
        except ProcessingException as e:
            logger.error(f"Error processing voice for quest creation: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio processing failed: {str(e)}",
            )
        except BusinessException as e:
            logger.warning(f"Business rule violation in voice quest creation: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error in voice quest creation: {str(e)}")
            if settings.DEBUG:
                raise HTTPException(status_code=500, detail=str(e))
            else:
                raise HTTPException(
                    status_code=500,
                    detail="An unexpected error occurred during voice processing",
                )


@router.post("/voice-generation/suggest", response_model=schemas.QuestCreate)
async def suggest_quest_from_voice(
    *,
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    current_user: models.User = Depends(deps.get_current_active_user),
    gen_access: tuple[SubscriptionStatus, float] = Depends(deps.validate_audio_gen_access),
    quest_service: QuestService = Depends(deps.get_quest_service()),
) -> Any:
    """
    Generate a quest suggestion from voice input.

    Returns a suggestion without actually creating the quest. The user can then
    review and modify the suggestion before creating the quest.
    """
    with log_context(
        user_id=current_user.id,
        action="suggest_quest_from_voice",
        filename=audio_file.filename,
    ):
        logger.info(
            f"User {current_user.id} requesting quest suggestion from voice: {audio_file.filename}"
        )

        try:
            _subscription_status, audio_duration_minutes = gen_access
            return await quest_service.suggest_quest_from_voice(
                audio_file=audio_file,
                language=language,
                user_id=current_user.id,
                audio_duration_minutes=audio_duration_minutes,
            )
        except ProcessingException as e:
            logger.error(f"Error processing voice for quest suggestion: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio processing failed: {str(e)}",
            )
        except BusinessException as e:
            logger.warning(
                f"Business rule violation in voice quest suggestion: {str(e)}"
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception(f"Unexpected error in voice quest suggestion: {str(e)}")
            if settings.DEBUG:
                raise HTTPException(status_code=500, detail=str(e))
            else:
                raise HTTPException(
                    status_code=500,
                    detail="An unexpected error occurred during voice processing",
                )
