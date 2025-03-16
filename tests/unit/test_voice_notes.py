import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import re
import io

from app.services.note_service import NoteService
from app.models.note import NoteStyle


class AsyncFileMock:
    """A class that mocks FastAPI's UploadFile for testing async methods"""
    
    def __init__(self, filename="test.mp3", content=b"test audio data"):
        self.filename = filename
        self._content = content
        self._stream = io.BytesIO(self._content)
    
    async def read(self, size=-1):
        return self._stream.read(size)
    
    async def seek(self, offset):
        self._stream.seek(offset)
        
    def __getattr__(self, name):
        """Handle any other attributes/methods that might be accessed"""
        return MagicMock()


class TestVoiceNoteProcessing:
    """
    Test cases for voice note processing functionality
    """
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def mock_repository(self):
        """Mock note repository"""
        repository = MagicMock()
        repository.create_voice_note_with_content.return_value = MagicMock(id=1, title="Test Voice Note")
        repository.update_with_transcription.return_value = MagicMock(id=1, title="Test Voice Note")
        return repository
    
    @pytest.fixture
    def mock_subscription_repository(self):
        """Mock subscription repository"""
        subscription_repo = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.advanced_ai_features = True
        mock_subscription.total_minutes_used_this_month = 5.0
        mock_subscription.monthly_minutes_limit = 100.0
        subscription_repo.get_by_user_id.return_value = mock_subscription
        return subscription_repo
    
    @pytest.fixture
    def mock_chat_completion_service(self):
        """Mock chat completion service"""
        chat_service = MagicMock()
        chat_service.call_llm_api = AsyncMock(return_value="Processed test content")
        return chat_service
    
    @pytest.fixture
    def mock_audio_file(self):
        """Create a mock audio file for testing"""
        return AsyncFileMock(filename="test.mp3", content=b"test audio data")
    
    @pytest.fixture
    def mock_audio_info(self):
        """Mock audio_info to avoid actual file processing"""
        async def mock_get_audio_info(*args, **kwargs):
            return {"duration": 60.0}  # 1 minute
        
        with patch("app.utils.audio_utils.get_audio_info", side_effect=mock_get_audio_info) as mock:
            yield mock
    
    @pytest.fixture
    def mock_stt_service(self):
        """Mock speech-to-text service"""
        mock_service = MagicMock()
        
        # Setup transcribe result
        transcription_result = MagicMock()
        transcription_result.text = "This is a test transcript"
        transcription_result.language = "en"
        
        mock_service.transcribe = AsyncMock(return_value=transcription_result)
        
        # Path the get_stt_service function to return our mock
        with patch("app.services.note_service.get_stt_service", return_value=mock_service) as mock_get_stt:
            yield mock_service
    
    @pytest.fixture
    def note_service(self, mock_db, mock_repository, mock_subscription_repository, mock_chat_completion_service):
        """Create a note service with mocked dependencies"""
        service = NoteService(mock_db)
        service.repository = mock_repository
        service.subscription_repository = mock_subscription_repository
        service.chat_completion_service = mock_chat_completion_service
        service.speech_service = MagicMock()
        
        # Setup the transcribe mock with a proper return value
        transcription_result = MagicMock()
        transcription_result.text = "This is a test transcript"
        transcription_result.language = "en"
        
        service.speech_service.transcribe = AsyncMock(return_value=transcription_result)
        return service
    
    @pytest.mark.asyncio
    async def test_style_system_prompts(self, note_service):
        """Test that different note styles use appropriate system prompts"""
        # Test standard style
        standard_prompt = note_service._get_style_system_prompt(NoteStyle.STANDARD)
        assert "professional note-taking assistant" in standard_prompt.lower()
        assert "important guidelines" in standard_prompt.lower()
        
        # Test blog post style
        blog_prompt = note_service._get_style_system_prompt(NoteStyle.BLOG_POST)
        assert "blog post writer" in blog_prompt.lower()
        assert "engaging" in blog_prompt.lower()
        
        # Test bullet points style
        bullet_prompt = note_service._get_style_system_prompt(NoteStyle.BULLET_POINTS)
        assert "note structuring specialist" in bullet_prompt.lower()
        assert "bullet-point list" in bullet_prompt.lower()
    
    @pytest.mark.asyncio
    async def test_voice_note_processing_prompt(self, note_service, mock_audio_file, mock_audio_info, mock_stt_service):
        """Test that the voice processing prompt is adapted to the selected style"""
        # Set up transcription return value
        transcription_result = MagicMock()
        transcription_result.text = "This is a test transcript"
        transcription_result.language = "en"
        mock_stt_service.transcribe.return_value = transcription_result
        
        # Create mock note data
        mock_note_data = MagicMock()
        mock_note_data.note_style = NoteStyle.STANDARD
        
        # Process the voice note with proper mocking 
        await note_service.process_audio_upload(1, mock_audio_file, mock_note_data)
            
        # Check the prompt
        call_args = note_service.chat_completion_service.call_llm_api.call_args_list[0][1]
        prompt = call_args.get("prompt", "")
            
        # Verify prompt contains expected elements
        assert f'following the "{NoteStyle.STANDARD.value}" style' in prompt
        assert "Don't analyze the language" in prompt
        assert 'Format and structure the content appropriately' in prompt
    

    @pytest.mark.asyncio
    async def test_summary_prompt(self, note_service, mock_audio_file, mock_audio_info, mock_stt_service):
        """Test the summary prompt for voice notes"""
        # Set up transcription return value
        transcription_result = MagicMock()
        transcription_result.text = "This is a test transcript"
        transcription_result.language = "en"
        mock_stt_service.transcribe.return_value = transcription_result
        
        # Create mock note data
        mock_note_data = MagicMock()
        mock_note_data.note_style = NoteStyle.STANDARD
        
        # Process the voice note
        await note_service.process_audio_upload(1, mock_audio_file, mock_note_data)
            
        # Check the summary prompt (second call to LLM API)
        call_args = note_service.chat_completion_service.call_llm_api.call_args_list[1][1]
        prompt = call_args.get("prompt", "")
        system_prompt = call_args.get("system_prompt", "")
            
        # Verify summary prompt contains expected elements
        assert "Create a simple, concise summary (1-2 sentences)" in prompt
        assert "Focus only on the key information or action items" in prompt
            
        # Verify system prompt
        assert "practical note summarizer" in system_prompt.lower()
        assert "1-2 sentences" in system_prompt
        assert "don't analyze or explain the language" in system_prompt.lower()
            
    @pytest.mark.asyncio
    async def test_action_items_prompt(self, note_service, mock_audio_file, mock_audio_info, mock_stt_service):
        """Test the action items prompt for appropriate note styles"""
        # Set up transcription return value
        transcription_result = MagicMock()
        transcription_result.text = "This is a test transcript with action items: 1. Do this 2. Do that"
        transcription_result.language = "en"
        mock_stt_service.transcribe.return_value = transcription_result
        
        # Create mock note data
        mock_note_data = MagicMock()
        mock_note_data.note_style = NoteStyle.ACTION_ITEMS
        
        # Process the voice note
        await note_service.process_audio_upload(1, mock_audio_file, mock_note_data)
            
        # The third call to call_llm_api should be for action items
        if len(note_service.chat_completion_service.call_llm_api.call_args_list) >= 3:
            call_args = note_service.chat_completion_service.call_llm_api.call_args_list[2][1]
            prompt = call_args.get("prompt", "")
            system_prompt = call_args.get("system_prompt", "")
                
            # Verify action items prompt contains expected elements
            assert "Extract all action items, tasks or to-dos" in prompt
            assert "Format as a bulleted list" in prompt
                
            # Verify system prompt
            assert "action item extraction specialist" in system_prompt.lower()
            assert "actionable list" in system_prompt.lower()
    
    @pytest.mark.asyncio
    async def test_multilingual_handling(self, note_service, mock_audio_file, mock_audio_info, mock_stt_service):
        """Test that voice notes are processed correctly with different languages"""
        # Set up transcription return value with Spanish text
        transcription_result = MagicMock()
        transcription_result.text = "Mañana necesito llevar el coche al taller"
        transcription_result.language = "es"
        mock_stt_service.transcribe.return_value = transcription_result
        
        # Create mock note data
        mock_note_data = MagicMock()
        mock_note_data.note_style = NoteStyle.STANDARD
        
        # Process the voice note
        await note_service.process_audio_upload(1, mock_audio_file, mock_note_data)
            
        # Check the standard prompt
        system_prompt = note_service.chat_completion_service.call_llm_api.call_args_list[0][1].get("system_prompt", "")
            
        # Verify system prompt handles multilingual content
        assert "Work with any language naturally" in system_prompt 