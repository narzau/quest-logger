from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.repositories.base_repository import BaseRepository
from app.models import Note
from app.schemas.note import NoteCreate, NoteUpdate, VoiceNoteCreate


class NoteRepository(BaseRepository[Note]):
    """Repository for Note operations."""

    def __init__(self, db: Session):
        super().__init__(Note, db)

    def create_note(self, owner_id: int, obj_in: NoteCreate) -> Note:
        """Create a regular text note"""
        note = Note(
            owner_id=owner_id,
            title=obj_in.title,
            content=obj_in.content,
            tags=obj_in.tags,
            folder=obj_in.folder,
            note_style=obj_in.note_style,
            quest_id=obj_in.quest_id,
            ai_summary=obj_in.ai_summary,
            extracted_action_items=obj_in.extracted_action_items,
            ai_processed=bool(obj_in.ai_summary or obj_in.extracted_action_items),
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def create_voice_note(
        self,
        owner_id: int,
        obj_in: VoiceNoteCreate,
        audio_duration: float,
        language: str,
    ) -> Note:
        """Create a voice note with audio information but without storing the audio file"""
        note = Note(
            owner_id=owner_id,
            title=obj_in.title,
            audio_duration=audio_duration,
            language=language,
            folder=obj_in.folder,
            note_style=obj_in.note_style,
            tags=obj_in.tags,
            quest_id=obj_in.quest_id,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def create_voice_note_with_content(
        self,
        owner_id: int,
        obj_in: VoiceNoteCreate,
        raw_transcript: str,
        content: str,
        ai_summary: Optional[str] = None,
        action_items: Optional[str] = None,
        audio_duration: float = 0.0,
        language: str = "en",
    ) -> Note:
        """Create a voice note with all processed content"""
        note = Note(
            owner_id=owner_id,
            title=obj_in.title,
            raw_transcript=raw_transcript,
            content=content,
            ai_summary=ai_summary,
            extracted_action_items=action_items,
            audio_duration=audio_duration,
            language=language,
            folder=obj_in.folder,
            note_style=obj_in.note_style,
            tags=obj_in.tags,
            quest_id=obj_in.quest_id,
            ai_processed=True,  # Mark as AI processed since we've done all the processing
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_user_note(self, user_id: int, note_id: int) -> Optional[Note]:
        """Get a specific note for a user"""
        return (
            self.db.query(Note)
            .filter(Note.id == note_id, Note.owner_id == user_id)
            .first()
        )

    def get_by_share_id(self, share_id: str) -> Optional[Note]:
        """Get a note by public share ID"""
        return (
            self.db.query(Note)
            .filter(Note.public_share_id == share_id, Note.is_public == True)
            .first()
        )

    def get_user_notes(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        folder: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Get paginated list of notes with filtering options"""
        query = self.db.query(Note).filter(Note.owner_id == user_id)

        # Apply folder filter
        if folder:
            query = query.filter(Note.folder == folder)

        # Apply tag filter
        if tag:
            query = query.filter(Note.tags.contains(tag))

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Note.title.ilike(search_term)) | (Note.content.ilike(search_term))
            )

        # Count total before pagination
        total = query.count()

        # Apply sorting
        if sort_order == "desc":
            query = query.order_by(desc(getattr(Note, sort_by)))
        else:
            query = query.order_by(getattr(Note, sort_by))

        # Apply pagination
        items = query.offset(skip).limit(limit).all()

        # Calculate total pages
        pages = (total + limit - 1) // limit if limit > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": pages,
        }

    def update_note(self, note: Note, obj_in: NoteUpdate) -> Note:
        """Update a note"""
        update_data = obj_in.dict(exclude_unset=True)

        # Update fields based on the provided data
        for field, value in update_data.items():
            setattr(note, field, value)

        # Update the updated_at timestamp
        note.updated_at = datetime.utcnow()

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note: Note) -> bool:
        """Delete a note"""
        self.db.delete(note)
        self.db.commit()
        return True

    def generate_share_link(self, note: Note) -> Note:
        """Generate a public shareable link for a note"""
        note.is_public = True
        note.public_share_id = str(uuid4())
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def disable_share_link(self, note: Note) -> Note:
        """Disable public sharing for a note"""
        note.is_public = False
        note.public_share_id = None
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def update_with_transcription(
        self,
        note: Note,
        raw_transcript: str,
        processed_content: Optional[str] = None,
        ai_summary: Optional[str] = None,
        extracted_action_items: Optional[str] = None,
    ) -> Note:
        """Update a note with transcription and AI processing results"""
        note.raw_transcript = raw_transcript

        if processed_content:
            note.content = processed_content

        if ai_summary:
            note.ai_summary = ai_summary
            note.ai_processed = True

        if extracted_action_items:
            note.extracted_action_items = extracted_action_items

        note.updated_at = datetime.utcnow()

        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def get_folders(self, user_id: int) -> List[str]:
        """Get a list of unique folder names used by the user"""
        folders = (
            self.db.query(Note.folder)
            .filter(Note.owner_id == user_id, Note.folder.isnot(None))
            .distinct()
            .all()
        )
        return [folder[0] for folder in folders if folder[0]]

    def get_tags(self, user_id: int) -> List[str]:
        """Get a list of unique tags used by the user"""
        notes_with_tags = (
            self.db.query(Note.tags)
            .filter(Note.owner_id == user_id, Note.tags.isnot(None))
            .distinct()
            .all()
        )

        # Process comma-separated tags and create a unique set
        all_tags = set()
        for note_tags in notes_with_tags:
            if note_tags[0]:
                tags = [tag.strip() for tag in note_tags[0].split(",")]
                all_tags.update(tags)

        return sorted(list(all_tags))
