from typing import Dict, Any, List, Optional
import logging

from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, Query
from fastapi.responses import Response

from app.api.deps import get_current_user, get_db, get_note_service
from app.models import User
from app.models.note import NoteStyle, NoteExportFormat
from app.services.note_service import NoteService
from app.schemas.note import NoteCreate, NoteUpdate, Note, VoiceNoteCreate, NoteList
from app.core.logging import log_context
from app.core.exceptions import ValidationException

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=Note)
async def create_note(
    data: NoteCreate,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Create a new text note"""
    # Add user info to logging context
    with log_context(user_id=current_user.id, action="create_note"):
        logger.info(f"Creating note: {data.title}")
        return await note_service.create_note(current_user.id, data)


@router.get("/{note_id}", response_model=Note)
async def get_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Get a note by ID"""
    with log_context(user_id=current_user.id, note_id=note_id, action="get_note"):
        return await note_service.get_note(current_user.id, note_id)


@router.get("/shared/{share_id}", response_model=Note)
async def get_shared_note(
    share_id: str, note_service: NoteService = Depends(get_note_service())
):
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
):
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
):
    """Update a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="update_note"):
        logger.info(f"Updating note {note_id}")
        return await note_service.update_note(current_user.id, note_id, data)


@router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Delete a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="delete_note"):
        logger.info(f"Deleting note {note_id}")
        await note_service.delete_note(current_user.id, note_id)
        return {"status": "success"}


@router.get("/folders/list", response_model=Dict[str, List[str]])
async def list_folders(
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Get a list of unique folders used by the user"""
    with log_context(user_id=current_user.id, action="list_folders"):
        return await note_service.get_folders(current_user.id)


@router.get("/tags/list", response_model=Dict[str, List[str]])
async def list_tags(
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Get a list of unique tags used by the user"""
    with log_context(user_id=current_user.id, action="list_tags"):
        return await note_service.get_tags(current_user.id)


@router.post("/{note_id}/share", response_model=Dict[str, Any])
async def share_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Generate a public shareable link for a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="share_note"):
        logger.info(f"Generating share link for note {note_id}")
        return await note_service.generate_share_link(current_user.id, note_id)


@router.delete("/{note_id}/share")
async def unshare_note(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Remove public sharing for a note"""
    with log_context(user_id=current_user.id, note_id=note_id, action="unshare_note"):
        logger.info(f"Removing share link for note {note_id}")
        return await note_service.remove_share_link(current_user.id, note_id)


@router.post("/voice", response_model=Note)
async def create_voice_note(
    file: UploadFile = File(...),
    title: str = Form(...),
    folder: Optional[str] = Form(None),
    note_style: Optional[str] = Form("standard"),
    tags: Optional[str] = Form(None),
    quest_id: Optional[int] = Form(None),
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Create a new voice note with audio upload and transcription"""
    # Validate note_style using the enum
    try:
        note_style_enum = NoteStyle(note_style)
    except ValueError:
        # If invalid style provided, use the default
        note_style_enum = NoteStyle.STANDARD
        logger.warning(f"Invalid note style '{note_style}', using default 'standard' instead")

    # Create voice note data
    voice_note_data = VoiceNoteCreate(
        title=title, folder=folder, note_style=note_style_enum, tags=tags, quest_id=quest_id
    )

    with log_context(
        user_id=current_user.id,
        action="create_voice_note",
        filename=file.filename,
        note_style=note_style_enum,
    ):
        logger.info(f"Processing voice note: {title}, file: {file.filename}")
        return await note_service.process_audio_upload(
            current_user.id, file, voice_note_data
        )


@router.post("/{note_id}/process", response_model=Dict[str, Any])
async def process_note_audio(
    note_id: int,
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Process an existing audio note with AI features"""
    with log_context(user_id=current_user.id, note_id=note_id, action="process_audio"):
        logger.info(f"Processing existing audio for note {note_id}")
        return await note_service.process_existing_audio(current_user.id, note_id)


@router.get("/{note_id}/export")
async def export_note(
    note_id: int,
    format: str = Query("text"),
    note_service: NoteService = Depends(get_note_service()),
    current_user: User = Depends(get_current_user),
):
    """Export a note in the specified format (text, markdown, pdf)"""
    # Validate format using the enum
    try:
        format_enum = NoteExportFormat(format)
    except ValueError:
        # If invalid format provided, use the default
        format_enum = NoteExportFormat.TEXT
        logger.warning(f"Invalid export format '{format}', using default 'text' instead")
    
    with log_context(
        user_id=current_user.id, note_id=note_id, format=format_enum, action="export_note"
    ):
        logger.info(f"Exporting note {note_id} in {format_enum} format")
        
        # Get the exported note content and metadata
        result = await note_service.export_note(current_user.id, note_id, format_enum)
        
        # Return the file as a downloadable response
        return Response(
            content=result["content"],
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            },
        )
