from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.note import NoteStyle


# Base Schema
class NoteBase(BaseModel):
    title: str
    content: Optional[str] = None
    tags: Optional[str] = None
    folder: Optional[str] = None
    note_style: NoteStyle = NoteStyle.STANDARD
    quest_id: Optional[int] = None


# Create Schema
class NoteCreate(NoteBase):
    # AI processing fields
    ai_process: bool = True  # Should note be processed by AI
    ai_enhanced_content: Optional[str] = None  # AI-enhanced version of the content
    ai_summary: Optional[str] = None  # AI-generated summary
    extracted_action_items: Optional[str] = None  # AI-extracted action items


# Update Schema
class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    folder: Optional[str] = None
    note_style: Optional[NoteStyle] = None
    is_public: Optional[bool] = None
    quest_id: Optional[int] = None
    # AI fields
    ai_summary: Optional[str] = None
    extracted_action_items: Optional[str] = None
    ai_processed: Optional[bool] = None


# DB Schema for response
class Note(NoteBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    is_public: bool
    audio_duration: Optional[float] = None
    language: Optional[str] = None
    ai_processed: bool
    ai_summary: Optional[str] = None
    extracted_action_items: Optional[str] = None
    public_share_id: Optional[str] = None

    class Config:
        from_attributes = True


# Voice Note Schema
class VoiceNoteCreate(BaseModel):
    title: str
    folder: Optional[str] = None
    note_style: NoteStyle = NoteStyle.STANDARD
    tags: Optional[str] = None
    quest_id: Optional[int] = None


# Voice Note Processing Result
class VoiceNoteResult(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    raw_transcript: Optional[str] = None
    audio_duration: float
    language: str
    ai_processed: bool
    ai_summary: Optional[str] = None

    class Config:
        from_attributes = True


# Note Export
class NoteExport(BaseModel):
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    tags: Optional[str] = None
    ai_summary: Optional[str] = None
    extracted_action_items: Optional[str] = None


# Note List with pagination
class NoteList(BaseModel):
    items: List[Note]
    total: int
    page: int
    size: int
    pages: int
