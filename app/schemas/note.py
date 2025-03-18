import enum
from datetime import datetime
from typing import Optional, List

from fastapi import UploadFile
from pydantic import BaseModel
from app.models.note import NoteStyle
from app.integrations.speech.deepgram_stt_client import DeepgramLanguageEnum
from enum import StrEnum

class NoteLanguage(StrEnum):
    EN = "en"
    DE = "de"
    ES = "es"
    FR = "fr"
    IT = "it"
    JA = "ja"
    
class NoteProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


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
    ai_processed: Optional[bool] = None


# DB Schema for response
class Note(NoteBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    is_public: bool
    audio_duration: Optional[float] = None
    language: Optional[NoteLanguage] = None
    ai_processed: bool
    ai_summary: Optional[str] = None
    extracted_action_items: Optional[str] = None
    public_share_id: Optional[str] = None
    processing_status: Optional[NoteProcessingStatus] = None
    processing_error: Optional[str] = None

    class Config:
        from_attributes = True


# Voice Note Schema
class VoiceNoteCreate(BaseModel):
    audio_file: UploadFile
    folder: Optional[str] = None
    tags: Optional[str] = None
    note_style: NoteStyle = NoteStyle.STANDARD
    language: Optional[NoteLanguage] = None

    def map_to_deepgram_language(self, language: NoteLanguage) -> Optional[DeepgramLanguageEnum]:
        try: 
            return DeepgramLanguageEnum(language)
        except ValueError:
            return None

class ProcessedVoiceNoteCreate(VoiceNoteCreate):
    title: str
    content: str
    raw_transcript: str
    ai_processed: bool
    processing_status: Optional[NoteProcessingStatus] = None
    language: Optional[NoteLanguage] = None
    audio_duration: float
# Voice Note Processing Result
class VoiceNoteResult(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    raw_transcript: Optional[str] = None
    audio_duration: float
    language: NoteLanguage
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


# Response for share link operations
class ShareLinkResponse(BaseModel):
    share_id: Optional[str] = None
    share_url: Optional[str] = None
    already_shared: bool = False


# Response for unshare operations
class UnshareResponse(BaseModel):
    success: bool
    already_unshared: bool = False


# Response for folders list
class FolderListResponse(BaseModel):
    folders: List[str]


# Response for tags list
class TagListResponse(BaseModel):
    tags: List[str]


# Response for export operations
class ExportResponse(BaseModel):
    content: bytes
    content_type: str
    filename: str


# Response for audio processing
class AudioProcessingResponse(BaseModel):
    success: bool
    note_id: int
    title: str
    transcript_length: int
    audio_duration: float
