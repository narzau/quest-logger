import os
import uuid
import tempfile
import logging
from typing import Optional, Dict, Any, BinaryIO, Tuple, List
from datetime import datetime

from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.schemas.note import NoteCreate, NoteUpdate, VoiceNoteCreate, NoteExport
from app.models import Note
from app.models.note import NoteStyle
from app.repositories.note_repository import NoteRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.integrations.speech import get_stt_service
from app.integrations.chat_completion import ChatCompletionService
from app.core.config import settings
from app.utils.audio_utils import get_audio_info
from app.core.exceptions import ProcessingException

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
                    system_prompt = self._get_style_system_prompt(data.note_style)

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
                    style_system_prompt = self._get_style_system_prompt(note_style)

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
    ) -> Dict[str, Any]:
        """Get paginated list of notes with optional filtering"""
        return self.repository.get_user_notes(
            user_id, skip, limit, folder, tag, search, sort_by, sort_order
        )

    async def get_folders(self, user_id: int) -> Dict[str, List[str]]:
        """Get list of unique folders used by the user"""
        folders = self.repository.get_folders(user_id)
        return {"folders": folders}

    async def get_tags(self, user_id: int) -> Dict[str, List[str]]:
        """Get list of unique tags used by the user"""
        tags = self.repository.get_tags(user_id)
        return {"tags": tags}

    async def generate_share_link(self, user_id: int, note_id: int) -> Dict[str, Any]:
        """Generate a public shareable link for a note"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(
                f"Note {note_id} not found for user {user_id} during share link generation"
            )
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if user has permission to share (based on subscription)
        subscription = self.subscription_repository.get_by_user_id(user_id)
        if not subscription or not subscription.allow_sharing:
            logger.warning(
                f"User {user_id} attempted to share note {note_id} without sharing permission"
            )
            raise HTTPException(
                status_code=403, detail="Sharing is only available on Pro plan"
            )

        note = self.repository.generate_share_link(note)
        logger.info(f"Share link generated for note {note_id} by user {user_id}")
        return {
            "id": note.id,
            "public_share_id": note.public_share_id,
            "share_url": f"{settings.FRONTEND_URL}/shared/{note.public_share_id}",
        }

    async def remove_share_link(self, user_id: int, note_id: int) -> Dict[str, Any]:
        """Remove public sharing for a note"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(
                f"Note {note_id} not found for user {user_id} during share link removal"
            )
            raise HTTPException(status_code=404, detail="Note not found")

        note = self.repository.disable_share_link(note)
        logger.info(f"Share link removed for note {note_id} by user {user_id}")
        return {"id": note.id, "is_public": False}

    async def process_audio_upload(
        self, user_id: int, file: UploadFile, note_data: VoiceNoteCreate
    ) -> Note:
        """Process audio file upload and transcription"""
        # Check user subscription and minutes limit
        subscription = self.subscription_repository.get_by_user_id(user_id)
        if not subscription:
            # Initialize a free subscription if none exists
            subscription = self.subscription_repository.initialize_user_subscription(
                user_id
            )

        logger.info(
            f"Processing audio upload for user {user_id}, filename: {file.filename}"
        )

        try:
            # Get accurate audio information including duration
            audio_info = await get_audio_info(file)

            # Use actual duration for subscription checks and data storage
            audio_duration = audio_info["duration"]
            audio_duration_minutes = audio_duration / 60

            # Log actual duration
            logger.info(
                f"Audio duration: {audio_duration:.2f} seconds ({audio_duration_minutes:.2f} minutes)"
            )

            # Check if user has enough minutes available
            if (
                subscription.total_minutes_used_this_month + audio_duration_minutes
                > subscription.monthly_minutes_limit
            ):
                logger.warning(f"User {user_id} exceeded monthly recording limit")
                raise HTTPException(
                    status_code=403,
                    detail=f"You have reached your monthly recording limit of {subscription.monthly_minutes_limit} minutes. Upgrade to Pro for unlimited recording.",
                )

            # Check if advanced AI features are available for this user
            has_ai_features = subscription and subscription.advanced_ai_features
            if not has_ai_features:
                logger.warning(
                    f"User {user_id} attempted to use AI processing without subscription"
                )
                raise HTTPException(
                    status_code=403,
                    detail="AI processing is only available on Pro plan",
                )

            # Track usage with actual duration
            self.subscription_repository.track_usage(user_id, audio_duration_minutes)

            # Initialize the speech-to-text service
            speech_service = get_stt_service()

            # Transcribe the audio synchronously using the original UploadFile
            logger.info(f"Starting audio transcription for user {user_id}")
            transcription_result = await speech_service.transcribe(file)

            raw_transcript = transcription_result.text
            if not raw_transcript:
                logger.warning(f"Empty transcript received for user {user_id}")
                raise ProcessingException(
                    "Failed to transcribe audio (empty transcript)"
                )

            logger.info(
                f"Audio transcription complete, transcript length: {len(raw_transcript)} characters"
            )

            # For advanced AI processing
            processed_content = raw_transcript
            ai_summary = None
            action_items = None

            # Process with AI
            # Choose appropriate system prompt based on note style
            style_system_prompt = self._get_style_system_prompt(note_data.note_style)

            # Generate structured content based on note style
            prompt = f"""
            Transform this raw voice transcript into content following the "{note_data.note_style.value}" style. The transcript was: 
            
            "{raw_transcript}"
            
            Format and structure the content appropriately for a {note_data.note_style.value.replace('_', ' ')}.
            Don't analyze the language or provide linguistic breakdowns - focus on creating the actual content.
            """

            processed_result = await self.chat_completion_service.call_llm_api(
                prompt=prompt, system_prompt=style_system_prompt, temperature=0.7
            )
            processed_content = processed_result or raw_transcript

            # Generate summary for all note types
            summary_prompt = f"""
            Create a simple, concise summary (1-2 sentences) of this voice note:
            "{raw_transcript}"
            
            Focus only on the key information or action items.
            """
            summary_system_prompt = """
            You are a practical note summarizer. Your only job is to extract the essential information from a note in 1-2 sentences.
            Be direct and clear. Don't analyze or explain the language - just summarize the content itself.
            If the note contains a task or action item, prioritize that in your summary.
            """

            summary_result = await self.chat_completion_service.call_llm_api(
                prompt=summary_prompt,
                system_prompt=summary_system_prompt,
                temperature=0.5,
            )
            ai_summary = summary_result

            # Extract action items if applicable
            if note_data.note_style in [
                NoteStyle.ACTION_ITEMS,
                NoteStyle.TASK_LIST,
                NoteStyle.MEETING_NOTES,
            ]:
                action_prompt = f"""
                Extract all action items, tasks or to-dos mentioned in this content:
                {raw_transcript}
                
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
                action_items = action_result

            # Now create the note with all processed content
            # Use language from transcription result if available
            language = getattr(transcription_result, "language", "en") or "en"

            logger.info(
                f"Creating voice note with processed content for user {user_id}"
            )
            note = self.repository.create_voice_note_with_content(
                user_id,
                note_data,
                raw_transcript=raw_transcript,
                content=processed_content,
                ai_summary=ai_summary,
                action_items=action_items,
                audio_duration=audio_duration,  # Use actual duration from audio analysis
                language=language,
            )

            logger.info(f"Voice note {note.id} created successfully for user {user_id}")
            return note

        except HTTPException:
            # Re-raise HTTP exceptions as they're already properly formatted
            raise
        except ProcessingException as e:
            logger.error(f"Processing error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Error processing audio: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail="An error occurred while processing your audio"
            )

    async def export_note(
        self, user_id: int, note_id: int, format: str = "text"
    ) -> Dict[str, Any]:
        """Export a note in the specified format (text, markdown, pdf)"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(f"Note {note_id} not found for user {user_id} during export")
            raise HTTPException(status_code=404, detail="Note not found")

        # Check if user has permission to export (based on subscription)
        subscription = self.subscription_repository.get_by_user_id(user_id)
        if not subscription or not subscription.allow_exporting:
            logger.warning(
                f"User {user_id} attempted to export note {note_id} without export permission"
            )
            raise HTTPException(
                status_code=403, detail="Exporting is only available on Pro plan"
            )

        # For now, just return the note content
        # In a real implementation, this would format and return the appropriate file
        note_export = NoteExport(
            title=note.title,
            content=note.content or "",
            created_at=note.created_at,
            updated_at=note.updated_at,
            tags=note.tags,
            ai_summary=note.ai_summary,
            extracted_action_items=note.extracted_action_items,
        )

        logger.info(f"Note {note_id} exported in {format} format by user {user_id}")
        return {
            "format": format,
            "note": note_export,
            "filename": f"{note.title.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}",
        }

    async def process_existing_audio(
        self, user_id: int, note_id: int
    ) -> Dict[str, Any]:
        """Reprocess an existing audio note with AI features"""
        note = self.repository.get_user_note(user_id, note_id)
        if not note:
            logger.warning(
                f"Note {note_id} not found for user {user_id} during reprocessing"
            )
            raise HTTPException(status_code=404, detail="Note not found")

        if not note.raw_transcript:
            logger.warning(f"Note {note_id} has no raw transcript for user {user_id}")
            raise HTTPException(
                status_code=400, detail="This note has no transcript to process"
            )

        # Check if user has advanced AI feature permission
        subscription = self.subscription_repository.get_by_user_id(user_id)
        if not subscription or not subscription.advanced_ai_features:
            logger.warning(
                f"User {user_id} attempted to reprocess note {note_id} without AI permission"
            )
            raise HTTPException(
                status_code=403, detail="AI processing is only available on Pro plan"
            )

        logger.info(f"Reprocessing existing audio note {note_id} for user {user_id}")

        try:
            # Process with AI directly from the raw transcript
            raw_transcript = note.raw_transcript

            # Choose appropriate system prompt based on note style
            style_system_prompt = self._get_style_system_prompt(note.note_style)

            # Generate structured content based on note style
            prompt = f"""
            Transform this raw voice transcript into content following the "{note.note_style.value}" style. The transcript was: 
            
            "{raw_transcript}"
            
            Format and structure the content appropriately for a {note.note_style.value.replace('_', ' ')}.
            Don't analyze the language or provide linguistic breakdowns - focus on creating the actual content.
            """

            processed_result = await self.chat_completion_service.call_llm_api(
                prompt=prompt, system_prompt=style_system_prompt, temperature=0.7
            )
            processed_content = processed_result or raw_transcript

            # Generate summary for all note types
            summary_prompt = f"""
            Create a simple, concise summary (1-2 sentences) of this voice note:
            "{raw_transcript}"
            
            Focus only on the key information or action items.
            """
            summary_system_prompt = """
            You are a practical note summarizer. Your only job is to extract the essential information from a note in 1-2 sentences.
            Be direct and clear. Don't analyze or explain the language - just summarize the content itself.
            If the note contains a task or action item, prioritize that in your summary.
            """

            summary_result = await self.chat_completion_service.call_llm_api(
                prompt=summary_prompt,
                system_prompt=summary_system_prompt,
                temperature=0.5,
            )
            ai_summary = summary_result

            # Extract action items if applicable
            action_items = None
            if note.note_style in [
                NoteStyle.ACTION_ITEMS,
                NoteStyle.TASK_LIST,
                NoteStyle.MEETING_NOTES,
            ]:
                action_prompt = f"""
                Extract all action items, tasks or to-dos mentioned in this content:
                {raw_transcript}
                
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
                action_items = action_result

            # Update the note with AI processing
            updated_note = self.repository.update_with_transcription(
                note, raw_transcript, processed_content, ai_summary, action_items
            )

            logger.info(
                f"Reprocessing of note {note_id} completed successfully for user {user_id}"
            )
            return {
                "id": updated_note.id,
                "status": "completed",
                "ai_processed": True,
                "title": updated_note.title,
            }
        except Exception as e:
            logger.error(f"Error reprocessing note {note_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Failed to process note: {str(e)}"
            )

    def _get_style_system_prompt(self, note_style: NoteStyle) -> str:
        """Get the appropriate system prompt based on note style"""
        style_prompts = {
            NoteStyle.STANDARD: """
                You are a professional note-taking assistant. Your role is to transform voice transcriptions into clear, useful notes.

                IMPORTANT GUIDELINES:
                1. Keep it simple and direct - don't over-analyze the content
                2. Focus on capturing the actual information, not analyzing the language
                3. NEVER break down the language structure (no linguistic analysis)
                4. Work with any language naturally (English, Spanish, etc.) without translation
                5. Maintain the main points exactly as provided in the input
                6. Don't repeat the instructions in the output
                7. Don't label components of speech or analyze syntax
                8. Format naturally with paragraphs and simple formatting only
                9. If the note is a task or reminder, present it clearly as an action item
                10. Remove filler words and clean up transcription errors

                BAD OUTPUT EXAMPLE (too analytical):
                "Title: Car Maintenance Appointment Scheduled
                
                Content:
                - **Mañana** (Tomorrow)
                  - Action: I have to take the car
                  - Verb: I have to take
                  - Subject: the auto (the car)
                  - Object: a que le hagan un service (to the service center)"

                GOOD OUTPUT EXAMPLE (clean and useful):
                "Car Service Appointment
                
                Remember to take the car to the service center tomorrow morning.
                
                Time: Not specified, schedule in calendar
                Location: Regular service center"
                """,
            NoteStyle.BULLET_POINTS: """
                You are a note structuring specialist. Your task is to transform raw content into a clear, organized bullet-point list. 
                Create hierarchical structure with main points and sub-points where appropriate. Use consistent formatting and ensure all key information is preserved.
                """,
            NoteStyle.SUMMARY: """
                You are a summarization expert. Your task is to condense raw content into a concise summary that captures the essential information. 
                Focus on the most important points and maintain clarity while significantly reducing length.
                """,
            NoteStyle.ACTION_ITEMS: """
                You are an action item extraction specialist. Your task is to transform raw content into a structured list of action items.
                Format as clear, actionable tasks with assignees and deadlines if mentioned. Use consistent formatting with checkboxes ([ ]) for each item.
                """,
            NoteStyle.BLOG_POST: """
                You are a blog post writer. Transform the raw content into an engaging, well-structured blog post. 
                Include an attention-grabbing introduction, clearly defined sections with appropriate headings, and a conclusion.
                Maintain a conversational, engaging tone while ensuring informational accuracy. Add appropriate formatting for readability.
                """,
            NoteStyle.VIDEO_SCRIPT: """
                You are a video script writer. Transform the raw content into a professional video script with clear sections for:
                INTRO, MAIN CONTENT (divided into logical segments), and OUTRO. 
                Format with speaker cues, timing indications, and visual/graphic notes where appropriate.
                Use conversational language suitable for spoken delivery.
                """,
            NoteStyle.SOCIAL_MEDIA_POST: """
                You are a social media content creator. Transform the raw content into concise, engaging social media posts.
                Format appropriately with an attention-grabbing opening, relevant hashtags, and a clear call to action.
                Keep the tone conversational and engaging. Optimize for readability on mobile devices with short paragraphs.
                """,
            NoteStyle.TASK_LIST: """
                You are a task organization specialist. Transform the raw content into a structured task list with:
                1. Main tasks formatted with checkboxes ([ ])
                2. Sub-tasks indented with their own checkboxes
                3. Priority indicators (High/Medium/Low) if applicable
                4. Due dates in ISO format (YYYY-MM-DD) if mentioned
                Create a logical grouping of related tasks and ensure all actionable items from the original content are captured.
                """,
            NoteStyle.MEETING_NOTES: """
                You are a meeting notes specialist. Transform the raw content into professional meeting notes with:
                1. Meeting metadata (date, attendees, purpose) if available
                2. Clear agenda or discussion points as headings
                3. Key decisions and discussion points
                4. Action items with assignees and deadlines
                5. Follow-up items or next steps
                Use consistent formatting and ensure all important information from the meeting is preserved.
                """,
            NoteStyle.EMAIL_DRAFT: """
                You are an email writing assistant. Transform the raw content into a professional email draft with:
                1. A clear, concise subject line suggestion
                2. Appropriate greeting
                3. Well-structured body with short paragraphs
                4. Professional closing
                Adapt the tone to be appropriately formal or casual based on the content. Ensure clarity and conciseness.
                """,
            NoteStyle.CREATIVE_WRITING: """
                You are a creative writing assistant. Transform the raw content into a creative piece with:
                1. Engaging narrative structure
                2. Descriptive language and imagery
                3. Character development (if applicable)
                4. Appropriate dialog formatting (if applicable)
                Enhance creative elements while preserving the core ideas from the original content.
                """,
            NoteStyle.CODE_DOCUMENTATION: """
                You are a technical documentation specialist. Transform the raw content into professional code documentation with:
                1. Clear overview of purpose/functionality
                2. Structured sections for installation, usage, API, etc.
                3. Code examples in appropriate markdown formatting
                4. Parameter/return value descriptions
                Use technical precision while maintaining readability for developers.
                """,
            NoteStyle.NEWSLETTER: """
                You are a newsletter content creator. Transform the raw content into a structured newsletter with:
                1. Engaging headline/title
                2. Brief introduction
                3. Main content divided into clear sections with subheadings
                4. Call to action or concluding remarks
                Maintain a consistent tone and ensure information is presented in a scannable, engaging format.
                """,
            NoteStyle.ACADEMIC_PAPER: """
                You are an academic writing specialist. Transform the raw content into an academic paper format with:
                1. Abstract/summary
                2. Introduction with research question or hypothesis
                3. Structured sections with appropriate headings
                4. Conclusion or discussion
                5. References section if sources are mentioned
                Use formal academic tone and appropriate discipline-specific formatting.
                """,
            NoteStyle.CUSTOM: """
                You are a content enhancement specialist. Your task is to transform raw content into a well-structured, 
                clearly formatted document that preserves all key information while improving organization and readability.
                Apply appropriate formatting with paragraphs, headings, lists, and emphasis where needed.
                """,
        }

        return style_prompts.get(note_style, style_prompts[NoteStyle.STANDARD])
