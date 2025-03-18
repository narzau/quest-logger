from typing import Dict, Optional
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import Response

from app.api.deps import (
    get_current_user,
    get_note_service,
    validate_audio_gen_access,
    validate_active_subscription
)
from app.models import User
from app.models.note import NoteStyle, NoteExportFormat
from app.services.note_service import NoteService
from app.schemas.note import (
    NoteCreate, NoteUpdate, Note, VoiceNoteCreate, NoteList,
    ShareLinkResponse, UnshareResponse, 
    ExportResponse,
    FolderListResponse, TagListResponse
)
from app.core.logging import log_context
from app.schemas.subscription import SubscriptionStatus

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=Note)
async def create_note(
    data: NoteCreate,
    subscription_status: SubscriptionStatus = Depends(validate_active_subscription),
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> Note:
    """Create a new text note - requires active subscription"""
    # Add user info to logging context
    with log_context(user_id=current_user.id, action="create_note"):
        logger.info(f"Creating note: {data.title}")
        return await note_service.create_note(current_user.id, data)


@router.get("/{note_id}", response_model=Note)
async def get_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> Note:
    """Get a note by ID"""
    with log_context(user_id=current_user.id, note_id=note_id, action="get_note"):
        return await note_service.get_note(current_user.id, note_id)


@router.get("/shared/{share_id}", response_model=Note)
async def get_shared_note(
    share_id: str, note_service: NoteService = Depends(get_note_service())
) -> Note:
    """Get a note by public share ID (no authentication required)"""
    with log_context(share_id=share_id, action="get_shared_note"):
        return await note_service.get_public_note(share_id)


@router.get("/", response_model=NoteList)
async def list_notes(
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10,
    folder: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> NoteList:
    """Get a list of notes with pagination and filtering"""
    with log_context(
        user_id=current_user.id,
        action="list_notes",
        folder=folder,
        tag=tag,
        search=search,
    ):
        return await note_service.get_notes(
            current_user.id, skip, limit, folder, tag, search, sort_by, sort_order
        )


@router.put("/{note_id}", response_model=Note)
async def update_note(
    note_id: int,
    data: NoteUpdate,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> Note:
    """Update a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="update_note"):
        logger.info(f"Updating note {note_id}")
        return await note_service.update_note(current_user.id, note_id, data)


@router.delete("/{note_id}", response_model=Dict[str, str])
async def delete_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """Delete a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="delete_note"):
        logger.info(f"Deleting note {note_id}")
        await note_service.delete_note(current_user.id, note_id)
        return {"status": "success"}


@router.get("/folders/list", response_model=FolderListResponse)
async def list_folders(
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> FolderListResponse:
    """Get a list of unique folders used by the user"""
    with log_context(user_id=current_user.id, action="list_folders"):
        return await note_service.get_folders(current_user.id)


@router.get("/tags/list", response_model=TagListResponse)
async def list_tags(
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> TagListResponse:
    """Get a list of unique tags used by the user"""
    with log_context(user_id=current_user.id, action="list_tags"):
        return await note_service.get_tags(current_user.id)


@router.post("/voice", response_model=Note)
async def create_voice_note(
    audio_file: UploadFile = File(...),
    note_style: NoteStyle = Form(NoteStyle.STANDARD),
    folder: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    gen_access: tuple[SubscriptionStatus, float] = Depends(validate_audio_gen_access),
    note_service: NoteService = Depends(get_note_service()),
) -> Note:
    """Create a new note from voice recording - requires active subscription"""
    with log_context(
        user_id=current_user.id, action="create_voice_note", note_style=note_style
    ):
        _subscription_status, audio_duration_minutes = gen_access
        logger.info(f"Audio duration: {audio_duration_minutes:.2f} minutes")
        # Return the audio duration for the service to use
        note_data = VoiceNoteCreate(
            audio_file=audio_file,
            note_style=note_style,
            folder=folder,
            tags=tags
        )
        return await note_service.create_voice_note(current_user.id, note_data, audio_duration_minutes)



@router.post("/{note_id}/share", response_model=ShareLinkResponse)
async def share_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> ShareLinkResponse:
    """Generate a public share link for a note - no subscription required"""
    with log_context(user_id=current_user.id, note_id=note_id, action="share_note"):
        logger.info(f"Generating share link for note {note_id}")
        return await note_service.share_note(current_user.id, note_id)


@router.delete("/share/{note_id}", response_model=UnshareResponse)
async def unshare_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> UnshareResponse:
    """Remove public share link for a note - no subscription required"""
    with log_context(user_id=current_user.id, note_id=note_id, action="unshare_note"):
        logger.info(f"Removing share link for note {note_id}")
        return await note_service.unshare_note(current_user.id, note_id)


@router.post("/{note_id}/export", response_model=ExportResponse)
async def export_note(
    note_id: int,
    format: NoteExportFormat,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
) -> ExportResponse:
    """Export a note to a different format - no subscription required"""
    with log_context(
        user_id=current_user.id,
        note_id=note_id,
        action="export_note",
        format=format
    ):
        logger.info(f"Exporting note {note_id} to {format}")
        result = await note_service.export_note(current_user.id, note_id, format)
        return Response(
            content=result.content,
            media_type=result.content_type,
            headers={"Content-Disposition": f"attachment; filename={result.filename}"},
        )
