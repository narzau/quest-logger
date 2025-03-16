import enum
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class NoteStyle(str, enum.Enum):
    STANDARD = "standard"
    BULLET_POINTS = "bullet_points"
    SUMMARY = "summary"
    ACTION_ITEMS = "action_items"
    CUSTOM = "custom"
    BLOG_POST = "blog_post"
    VIDEO_SCRIPT = "video_script"
    SOCIAL_MEDIA_POST = "social_media_post"
    TASK_LIST = "task_list"
    MEETING_NOTES = "meeting_notes"
    EMAIL_DRAFT = "email_draft"
    CREATIVE_WRITING = "creative_writing"
    CODE_DOCUMENTATION = "code_documentation"
    NEWSLETTER = "newsletter"
    ACADEMIC_PAPER = "academic_paper"


class NoteExportFormat(str, enum.Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text, nullable=True)
    raw_transcript = Column(
        Text, nullable=True
    )  # Original transcription before AI processing
    audio_url = Column(String, nullable=True)  # URL to stored audio file
    audio_duration = Column(Float, nullable=True)  # Duration in seconds
    language = Column(String, nullable=True)  # Detected language
    note_style = Column(Enum(NoteStyle), default=NoteStyle.STANDARD)

    # Metadata
    is_public = Column(Boolean, default=False)
    public_share_id = Column(String, nullable=True, unique=True)  # For shareable links
    tags = Column(Text, nullable=True)  # Comma-separated tags
    folder = Column(String, nullable=True)  # For organization
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # References
    owner_id = Column(Integer, ForeignKey("users.id"))
    quest_id = Column(
        Integer, ForeignKey("quests.id"), nullable=True
    )  # Optional link to quest

    # Relationships
    owner = relationship("User", back_populates="notes")
    quest = relationship("Quest", back_populates="notes")

    # Subscription-related flags
    ai_processed = Column(Boolean, default=False)  # Whether AI processing was applied
    ai_summary = Column(Text, nullable=True)  # AI-generated summary
    extracted_action_items = Column(Text, nullable=True)  # AI-extracted action items
    
    # Usage tracking fields
    minutes_tracked = Column(Float, nullable=True)  # Minutes tracked for this note
    minutes_refunded = Column(Boolean, nullable=True)  # Whether minutes were refunded
    
    # Processing status fields
    processing_status = Column(String, default="pending")  # pending, processing, completed, error
    processing_error = Column(String, nullable=True)  # Error message if processing failed
