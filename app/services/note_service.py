import logging
from typing import Optional
import asyncio

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.schemas.note import (
    NoteCreate, NoteUpdate, VoiceNoteCreate, NoteExport, 
    Note, NoteList, ExportResponse, ShareLinkResponse, 
    UnshareResponse, FolderListResponse, TagListResponse, 
)
from app.models import Note
from app.models.note import NoteStyle, NoteExportFormat
from app.repositories.note_repository import NoteRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.integrations.speech import get_stt_service
from app.integrations.chat_completion import ChatCompletionService
from app.core.config import settings
from app.core.exceptions import ProcessingException
from app.core.constants import get_style_system_prompt
# Set up module logger
logger = logging.getLogger(__name__)


class NoteService:
    """Service for note operations."""

    def __init__(self, db: Session):
        self.repository = NoteRepository(db)
        self.subscription_repository = SubscriptionRepository(db)
        self.speech_service = get_stt_service()
        self.chat_completion_service = ChatCompletionService()

    async def create_note(self, user_id: int, data: NoteCreate) -> Note:
        """Create a regular text note"""
        # Check if AI processing is requested
        if data.ai_process and data.content:
            # Check if user has permission for AI processing
            subscription = self.subscription_repository.get_by_user_id(user_id)
            has_ai_features = subscription and subscription.advanced_ai_features

            if has_ai_features:
                logger.info(f"Processing note with AI for user {user_id}")
                try:
                    # Get system prompt based on note style
                    system_prompt = get_style_system_prompt(data.note_style)

                    # Process content with AI
                    prompt = f"""
                    Process this content according to the {data.note_style.value} style:
                    {data.content}
                    """

                    processed_content = await self.chat_completion_service.call_llm_api(
                        prompt=prompt, system_prompt=system_prompt, temperature=0.7
                    )

                    if processed_content:
                        data.content = processed_content

                    # Generate summary if needed
                    if data.note_style not in [
                        NoteStyle.SUMMARY
                    ]:  # Don't summarize a summary
                        summary_prompt = f"""
                        Create a concise summary (3-5 sentences) of the main points in this content:
                        {data.content}
                        """
                        summary_system_prompt = """
                        You are a summarization expert. Your task is to extract the key points from a piece of content 
                        and present them in a concise, clear manner. Focus on the most important information.
                        """

                        summary_result = (
                            await self.chat_completion_service.call_llm_api(
                                prompt=summary_prompt,
                                system_prompt=summary_system_prompt,
                                temperature=0.5,
                            )
                        )

                        if summary_result:
                            data.ai_summary = summary_result

                    # Extract action items if applicable
                    if data.note_style in [
                        NoteStyle.ACTION_ITEMS,
                        NoteStyle.TASK_LIST,
                        NoteStyle.MEETING_NOTES,
                    ]:
                        action_prompt = f"""
                        Extract all action items, tasks or to-dos mentioned in this content:
                        {data.content}
                        
                        Format as a bulleted list. If no specific actions are mentioned, respond with "No action items identified."
                        """
                        action_system_prompt = """
                        You are an action item extraction specialist. Your task is to identify all tasks, 
                        to-dos, and action items mentioned in the content. Format them as a clear, actionable list.
                        """

                        action_result = await self.chat_completion_service.call_llm_api(
                            prompt=action_prompt,
                            system_prompt=action_system_prompt,
                            temperature=0.3,
                        )

                        if action_result:
                            data.extracted_action_items = action_result
                except Exception as e:
                    logger.error(
                        f"Error processing note with AI: {str(e)}", exc_info=True
                    )
                    # Continue with the original content if AI processing fails

        # Create the note with processed content and AI attributes
        return self.repository.create_note(user_id, data)

    async def get_note(self, user_id: int, note_id: int) -> Note:
        """Get a note by ID, ensuring the user is the owner"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Note not found")
        return note

    async def get_public_note(self, share_id: str) -> Note:
        """Get a note by public share ID"""
        note = self.repository.get_by_share_id(share_id)
        if not note:
            logger.warning(f"Public note with share ID {share_id} not found")
            raise HTTPException(status_code=404, detail="Note not found or not public")
        return note

    async def update_note(self, user_id: int, note_id: int, data: NoteUpdate) -> Note:
        """Update a note"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id} during update")
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if note style is changing and AI processing is needed
        style_changed = (
            data.note_style is not None and data.note_style != note.note_style
        )
        content_changed = data.content is not None and data.content != note.content

        # Check if AI processing should be applied
        should_process_with_ai = False

        if (style_changed or content_changed) and note.content:
            # Check if user has permission for AI processing
            subscription = self.subscription_repository.get_by_user_id(user_id)
            should_process_with_ai = subscription and subscription.advanced_ai_features

        if should_process_with_ai:
            logger.info(f"Processing updated note {note_id} with AI for user {user_id}")
            try:
                # Get note style (use new style if provided, otherwise existing style)
                note_style = data.note_style or note.note_style

                # Get content (use new content if provided, otherwise existing content)
                content = data.content if data.content is not None else note.content

                if content:  # Only process if there's content
                    # Get system prompt based on note style
                    style_system_prompt = get_style_system_prompt(note_style)

                    # Process content with AI
                    prompt = f"""
                    Process this content according to the {note_style.value} style:
                    {content}
                    """

                    processed_content = await self.chat_completion_service.call_llm_api(
                        prompt=prompt,
                        system_prompt=style_system_prompt,
                        temperature=0.7,
                    )

                    if processed_content:
                        data.content = processed_content

                    # Generate summary
                    if note_style not in [
                        NoteStyle.SUMMARY
                    ]:  # Don't summarize a summary
                        summary_prompt = f"""
                        Create a concise summary (3-5 sentences) of the main points in this content:
                        {content}
                        """
                        summary_system_prompt = """
                        You are a summarization expert. Your task is to extract the key points from a piece of content 
                        and present them in a concise, clear manner. Focus on the most important information.
                        """

                        summary_result = (
                            await self.chat_completion_service.call_llm_api(
                                prompt=summary_prompt,
                                system_prompt=summary_system_prompt,
                                temperature=0.5,
                            )
                        )

                        if summary_result:
                            data.ai_summary = summary_result

                    # Extract action items if applicable
                    if note_style in [
                        NoteStyle.ACTION_ITEMS,
                        NoteStyle.TASK_LIST,
                        NoteStyle.MEETING_NOTES,
                    ]:
                        action_prompt = f"""
                        Extract all action items, tasks or to-dos mentioned in this content:
                        {content}
                        
                        Format as a bulleted list. If no specific actions are mentioned, respond with "No action items identified."
                        """
                        action_system_prompt = """
                        You are an action item extraction specialist. Your task is to identify all tasks, 
                        to-dos, and action items mentioned in the content. Format them as a clear, actionable list.
                        """

                        action_result = await self.chat_completion_service.call_llm_api(
                            prompt=action_prompt,
                            system_prompt=action_system_prompt,
                            temperature=0.3,
                        )

                        if action_result:
                            data.extracted_action_items = action_result
            except Exception as e:
                logger.error(
                    f"Error processing note update with AI: {str(e)}", exc_info=True
                )
                # Continue with the update using the original data if AI processing fails

        return self.repository.update_note(note, data)

    async def delete_note(self, user_id: int, note_id: int) -> None:
        """Delete a note"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(
                f"Note {note_id} not found for user {user_id} during deletion"
            )
            raise HTTPException(status_code=404, detail="Note not found")

        self.repository.delete_note(note)

    async def get_notes(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 10,
        folder: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> NoteList:
        """Get a list of notes with pagination and filtering"""
        notes_data = self.repository.get_user_notes(
            user_id, skip, limit, folder, tag, search, sort_by, sort_order
        )
        return NoteList(**notes_data)

    async def get_folders(self, user_id: int) -> FolderListResponse:
        """Get a list of unique folders used by the user"""
        folders = self.repository.get_folders(user_id)
        return FolderListResponse(folders=folders)

    async def get_tags(self, user_id: int) -> TagListResponse:
        """Get a list of unique tags used by the user"""
        tags = self.repository.get_tags(user_id)
        return TagListResponse(tags=tags)

    async def generate_share_link(self, user_id: int, note_id: int) -> ShareLinkResponse:
        """Generate a public share link for a note"""
        # Get the note and verify ownership
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if the note already has a share link
        if note.public_share_id:
            # Return existing share info
            return ShareLinkResponse(
                share_id=note.public_share_id,
                share_url=f"{settings.FRONTEND_URL}/notes/shared/{note.public_share_id}",
                already_shared=True,
            )

        # Generate a new share ID
        note = self.repository.generate_share_link(note)

        # Return share info
        return ShareLinkResponse(
            share_id=note.public_share_id,
            share_url=f"{settings.FRONTEND_URL}/notes/shared/{note.public_share_id}",
            already_shared=False,
        )

    async def share_note(self, user_id: int, note_id: int) -> ShareLinkResponse:
        """Generate a public share link for a note (alias for generate_share_link)"""
        return await self.generate_share_link(user_id, note_id)

    async def remove_share_link(self, user_id: int, note_id: int) -> UnshareResponse:
        """Remove public sharing for a note"""
        # Get the note and verify ownership
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if the note has a share link
        if not note.public_share_id:
            return UnshareResponse(success=True, already_unshared=True)

        # Remove share ID
        note.public_share_id = None
        self.repository.save(note)

        return UnshareResponse(success=True, already_unshared=False)
    
    async def unshare_note(self, user_id: int, note_id: int) -> UnshareResponse:
        """Remove public share link for a note (alias for remove_share_link)"""
        return await self.remove_share_link(user_id, note_id)

    async def export_note(
        self, user_id: int, note_id: int, format: NoteExportFormat = NoteExportFormat.TEXT
    ) -> ExportResponse:
        """Export a note in the specified format"""
        # Get the note and verify ownership
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id} during export")
            raise HTTPException(status_code=404, detail="Note not found")

        # Prepare export data
        note_export = NoteExport(
            title=note.title,
            content=note.content or "",
            created_at=note.created_at,
            updated_at=note.updated_at,
            tags=note.tags,
            ai_summary=note.ai_summary,
            extracted_action_items=note.extracted_action_items,
        )

        # Generate content based on format
        if format == NoteExportFormat.TEXT:
            content = self._format_note_as_text(note_export).encode("utf-8")
            content_type = "text/plain"
            filename = f"{note.title.replace(' ', '_')}.txt"
        elif format == NoteExportFormat.MARKDOWN:
            content = self._format_note_as_markdown(note_export).encode("utf-8")
            content_type = "text/markdown"
            filename = f"{note.title.replace(' ', '_')}.md"
        elif format == NoteExportFormat.PDF:
            content = self._generate_pdf(note_export)
            content_type = "application/pdf"
            filename = f"{note.title.replace(' ', '_')}.pdf"
        else:
            # Default to text
            content = self._format_note_as_text(note_export).encode("utf-8")
            content_type = "text/plain"
            filename = f"{note.title.replace(' ', '_')}.txt"

        return ExportResponse(
            content=content,
            content_type=content_type,
            filename=filename
        )

    def _format_note_as_text(self, note_export: NoteExport) -> str:
        """Format note as plain text"""
        lines = []
        lines.append(f"Title: {note_export.title}")
        lines.append(f"Created: {note_export.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Updated: {note_export.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if note_export.tags:
            lines.append(f"Tags: {note_export.tags}")
        
        lines.append("\n" + "=" * 40 + "\n")
        
        if note_export.ai_summary:
            lines.append("SUMMARY")
            lines.append("-" * 40)
            lines.append(note_export.ai_summary)
            lines.append("\n" + "=" * 40 + "\n")
        
        lines.append("CONTENT")
        lines.append("-" * 40)
        lines.append(note_export.content)
        
        if note_export.extracted_action_items:
            lines.append("\n" + "=" * 40 + "\n")
            lines.append("ACTION ITEMS")
            lines.append("-" * 40)
            lines.append(note_export.extracted_action_items)
        
        return "\n".join(lines)

    def _format_note_as_markdown(self, note_export: NoteExport) -> str:
        """Format note as markdown"""
        lines = []
        lines.append(f"# {note_export.title}")
        lines.append(f"*Created: {note_export.created_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append(f"*Updated: {note_export.updated_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        
        if note_export.tags:
            lines.append(f"\n**Tags**: {note_export.tags}")
        
        lines.append("\n---\n")
        
        if note_export.ai_summary:
            lines.append("## Summary")
            lines.append(note_export.ai_summary)
            lines.append("\n---\n")
        
        lines.append("## Content")
        lines.append(note_export.content)
        
        if note_export.extracted_action_items:
            lines.append("\n---\n")
            lines.append("## Action Items")
            lines.append(note_export.extracted_action_items)
        
        return "\n".join(lines)
    
    async def create_voice_note(
        self, user_id: int, audio_file: UploadFile, note_data: VoiceNoteCreate, audio_duration_minutes: float
    ) -> Note:
        """Create a new note from voice recording"""
        logger.info(f"Creating voice note for user {user_id}")
        try:
            # Check if we should process synchronously (less than 1 minute)
            is_processing_sync = audio_duration_minutes < 1
            logger.info(f"Audio duration: {audio_duration_minutes:.2f} minutes, processing {'synchronously' if is_processing_sync else 'asynchronously'}")
            
            if is_processing_sync:
                # For short audio, process synchronously and create with processed content
                logger.info(f"Processing short audio synchronously for user {user_id}")
                processed_result = await self.process_audio_upload_sync(user_id, audio_file, note_data)
                
                # Track usage AFTER successful processing for sync processing
                self.subscription_repository.track_usage(user_id, audio_duration_minutes)
                
                # Create note with processed data
                note = self.repository.create_voice_note_with_content(
                    user_id,
                    note_data,
                    raw_transcript=processed_result["raw_transcript"],
                    content=processed_result["content"],
                    audio_duration=audio_duration_minutes * 60,
                    language=processed_result["language"],
                )
                note.processing_status = "completed"
            else:
                # For longer audio, first track usage, then create note, then process asynchronously
                # We'll need to potentially refund minutes if processing fails
                
                # Create note first with pending status
                note = self.repository.create_voice_note(
                    user_id,
                    note_data,
                    audio_duration_minutes=audio_duration_minutes,
                )
                note.processing_status = "processing"
                self.repository.save(note)
                
                # Track usage for async processing, but store the tracking info on the note
                # so we can potentially refund it if processing fails
                self.subscription_repository.track_usage(user_id, audio_duration_minutes)
                note.minutes_tracked = float(audio_duration_minutes)
                self.repository.save(note)
                
                # Make a copy of the file for async processing
                await audio_file.seek(0)
                
                # Process audio asynchronously
                asyncio.create_task(
                    self.process_audio_upload_async(user_id, note.id, audio_file, note_data)
                )
            
            return note
            
        except Exception as e:
            logger.error(f"Error creating voice note: {str(e)}", exc_info=True)
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=500, detail="Failed to create voice note. Please try again."
            )

    async def process_audio_upload_sync(
        self, user_id: int, audio_file: UploadFile, note_data: VoiceNoteCreate
    ) -> dict:
        """
        Process audio synchronously for short voice recordings (<1 minute).
        
        Args:
            user_id: The ID of the user who created the recording
            audio_file: The uploaded audio file
            note_data: The voice note creation data (title, note_style, etc.)
            
        Returns:
            A dictionary containing all processed data needed to create a note:
            - raw_transcript: The original transcript text
            - content: The AI-processed content
            - ai_summary: A short summary of the content
            - action_items: Extracted action items (if applicable)
            - language: The detected language
            
        Raises:
            ProcessingException: If the transcription fails or returns empty
            Exception: Any other processing errors
        """
        try:
            # Reset file pointer to the beginning
            await audio_file.seek(0)
            # Transcribe the audio
            logger.info(f"Starting synchronous audio transcription for user {user_id}")
            transcription_result = await self.speech_service.transcribe(audio_file)

            raw_transcript = transcription_result.text
            if not raw_transcript:
                logger.warning(f"Empty transcript received for user {user_id}")
                raise ProcessingException(
                    "Failed to transcribe audio (empty transcript)"
                )

            logger.info(
                f"Audio transcription complete, transcript length: {len(raw_transcript)} characters"
            )

            # Process with AI to generate structured content
            processed_content = await self._process_transcript_with_ai(
                raw_transcript, note_data.note_style
            )

            # Return data for note creation
            return {
                "raw_transcript": raw_transcript,
                "content": processed_content,
                "language": transcription_result.language or "en"
            }
            
        except Exception as e:
            logger.error(f"Error in synchronous audio processing for user {user_id}: {str(e)}", exc_info=True)
            # Re-raise the exception for the caller to handle
            raise

    async def process_audio_upload_async(
        self, user_id: int, note_id: int, audio_file: UploadFile, note_data: VoiceNoteCreate
    ) -> None:
        """
        Process audio asynchronously for longer voice recordings (>= 1 minute).
        Updates an existing note with the processed content and handles error management.
        
        Args:
            user_id: The ID of the user who created the recording
            note_id: The ID of the note to update with processing results
            audio_file: The uploaded audio file
            note_data: The voice note creation data (title, note_style, etc.)
            
        Note:
            This method doesn't return any value as it's designed to be run as a background task.
            If processing fails, it will:
            1. Update the note with error status
            2. Store the error message
            3. Attempt to refund usage minutes for fairness
        """
        try:
            # Reset file pointer to the beginning
            await audio_file.seek(0)
            # Transcribe the audio
            logger.info(f"Starting asynchronous audio transcription for user {user_id}, note {note_id}")
            transcription_result = await self.speech_service.transcribe(audio_file)

            raw_transcript = transcription_result.text
            if not raw_transcript:
                logger.warning(f"Empty transcript received for user {user_id}")
                raise ProcessingException(
                    "Failed to transcribe audio (empty transcript)"
                )

            logger.info(
                f"Audio transcription complete, transcript length: {len(raw_transcript)} characters"
            )

            # Process with AI to generate structured content
            processed_content = await self._process_transcript_with_ai(
                raw_transcript, note_data.note_style
            )
            
            # Get the note and update with processed content
            note = self.repository.get_user_note(user_id, note_id)
            if not note:
                logger.error(f"Note {note_id} not found when updating with processed content")
                return
            
            # Update the note with the processed content
            note.content = processed_content
            note.raw_transcript = raw_transcript
            note.language = transcription_result.language or "en"
            note.ai_processed = True
            note.processing_status = "completed"
            
            self.repository.save(note)
            
            logger.info(f"Voice note {note_id} processed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in asynchronous audio processing for note {note_id}: {str(e)}", exc_info=True)
            
            # Update note with error status and refund minutes
            try:
                note = self.repository.get_user_note(user_id, note_id)
                if note:
                    note.processing_status = "error"
                    note.processing_error = str(e)[:255]  # Limit error message length
                    
                    # Refund the minutes if they were tracked for this note
                    if note.minutes_tracked:
                        try:
                            # Attempt to refund the minutes to the user
                            self.subscription_repository.refund_usage(user_id, note.minutes_tracked)
                            note.minutes_refunded = True
                            logger.info(f"Refunded {note.minutes_tracked} minutes to user {user_id} due to processing error")
                        except Exception as refund_error:
                            logger.error(f"Failed to refund minutes: {str(refund_error)}")
                            note.minutes_refunded = False
                    
                    self.repository.save(note)
            except Exception as update_error:
                logger.error(f"Failed to update note with error status: {str(update_error)}")

    async def _process_transcript_with_ai(self, transcript: str, note_style: NoteStyle) -> tuple:
        """
        Process a transcript with AI to generate structured content, summary, and action items.
        
        Args:
            transcript: The raw transcript text from the STT service
            note_style: The user-selected note style
            
        Returns:
            - processed_content: The AI-enhanced formatted content
        """

        # Choose appropriate system prompt based on note style
        style_system_prompt = get_style_system_prompt(note_style)

        # Generate structured content based on note style
        prompt = f"""
        Transform this raw voice transcript into content following the "{note_style.value}" style. The transcript was: 
        
        "{transcript}"
        
        Format and structure the content appropriately for a {note_style.value.replace('_', ' ')}.
        Don't analyze the language or provide linguistic breakdowns - focus on creating the actual content.
        """

        processed_result = await self.chat_completion_service.call_llm_api(
            prompt=prompt, system_prompt=style_system_prompt, temperature=0.7
        )
        return processed_result or transcript

    def _generate_pdf(self, note_export: NoteExport) -> bytes:
        """Generate PDF from note data"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            import io
            
            # Create in-memory PDF
            buffer = io.BytesIO()
            
            # Set up PDF document
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Heading1'],
                fontSize=14,
                spaceAfter=12
            )
            
            subtitle_style = ParagraphStyle(
                'SubtitleStyle',
                parent=styles['Heading2'],
                fontSize=12,
                spaceAfter=6
            )
            
            normal_style = styles["Normal"]
            
            # Build PDF content
            content = []
            
            # Add title
            content.append(Paragraph(note_export.title, title_style))
            content.append(Spacer(1, 12))
            
            # Add metadata
            metadata = [
                f"Created: {note_export.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Updated: {note_export.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            if note_export.tags:
                metadata.append(f"Tags: {note_export.tags}")
                
            for line in metadata:
                content.append(Paragraph(line, normal_style))
            
            content.append(Spacer(1, 12))
            
            # Add summary if available
            if note_export.ai_summary:
                content.append(Paragraph("Summary", subtitle_style))
                content.append(Paragraph(note_export.ai_summary, normal_style))
                content.append(Spacer(1, 12))
            
            # Add main content
            content.append(Paragraph("Content", subtitle_style))
            
            # Split content by paragraphs for better formatting
            paragraphs = note_export.content.split('\n')
            for p in paragraphs:
                if p.strip():  # Skip empty lines
                    content.append(Paragraph(p, normal_style))
            
            content.append(Spacer(1, 12))
            
            # Add action items if available
            if note_export.extracted_action_items:
                content.append(Paragraph("Action Items", subtitle_style))
                
                # Split action items by lines
                items = note_export.extracted_action_items.split('\n')
                for item in items:
                    if item.strip():
                        content.append(Paragraph(item, normal_style))
            
            # Build and return the PDF
            doc.build(content)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            return pdf_bytes
            
        except ImportError:
            # If ReportLab is not installed
            logger.error("ReportLab library not available for PDF generation")
            raise ImportError("ReportLab is required for PDF generation")
