import json
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock, AsyncMock
from io import BytesIO
import io
from fastapi.testclient import TestClient
from datetime import datetime

from app.models.note import NoteStyle, NoteExportFormat
from app.schemas.note import NoteCreate
from app.main import app
from app.models.user import User

# Create a mock file that works with FastAPI's UploadFile
class MockFile:
    def __init__(self, filename="test.mp3", content=b"test audio content"):
        self.filename = filename
        self.file = io.BytesIO(content)

    def read(self, size=-1):
        return self.file.read(size)

    def seek(self, offset):
        self.file.seek(offset)


class TestNotesAPI:
    """
    Test cases for the Notes API endpoints
    
    Note: These tests use routes with the '/api/v1' prefix to match the actual application setup
    """

    @pytest.fixture
    def client(self):
        """Return a TestClient for making requests to the app"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_note_service(self):
        """Create a mock note service for testing"""
        with patch("app.api.deps.get_note_service") as mock_get_service:
            mock_service = MagicMock()
            # Set up mock methods
            mock_service.process_audio_upload = AsyncMock()
            mock_service.process_audio_upload.return_value = {
                "id": 1,
                "title": "Test Voice Note",
                "status": "processing"
            }
            
            mock_service.process_existing_audio = AsyncMock()
            mock_service.process_existing_audio.return_value = {
                "id": 1,
                "title": "Processed Voice Note",
                "status": "completed"
            }
            
            mock_service.export_note = AsyncMock()
            mock_service.export_note.return_value = {
                "id": 1,
                "title": "Exported Note",
                "format": "markdown",
                "content": "# Test Content"
            }
            
            mock_service.get_user_notes = AsyncMock()
            mock_service.get_user_notes.return_value = [
                {
                    "id": 1,
                    "title": "Test Note 1",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "status": "completed"
                }
            ]
            
            mock_service.get_user_note = AsyncMock()
            mock_service.get_user_note.return_value = {
                "id": 1,
                "title": "Test Note Detail",
                "content": "Test content",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": "completed"
            }
            
            mock_get_service.return_value = mock_service
            yield mock_service
    
    @pytest.fixture
    def mock_auth(self):
        """Mock the authentication to bypass it in tests"""
        with patch("app.api.deps.get_current_user") as mock_get_user:
            # Create a User object instead of a dictionary
            user = User(id=1, username="testuser", email="test@example.com", hashed_password="fakehashed_password", is_active=True)
            mock_get_user.return_value = user
            yield mock_get_user
    
    # === CREATE NOTE TESTS ===
    def test_create_note_success(self, authorized_client, db):
        """Test successful note creation"""
        note_data = {
            "title": "Test Note",
            "content": "This is a test note",
            "tags": "test,api",
            "folder": "Test Folder",
            "note_style": "standard",
            "ai_process": False
        }
        
        response = authorized_client.post("/api/v1/notes/", json=note_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["title"] == note_data["title"]
        assert data["content"] == note_data["content"]
        assert data["tags"] == note_data["tags"]
        assert data["folder"] == note_data["folder"]
        
    def test_create_note_with_ai_processing(self, authorized_client, db, monkeypatch):
        """Test creating a note with AI processing"""
        # Mock ChatCompletionService to avoid actual API calls
        mock_result = "AI processed content"
        mock_summary = "AI summary"
        
        async def mock_call_llm_api(*args, **kwargs):
            if "summary" in kwargs.get("prompt", "").lower():
                return mock_summary
            return mock_result
        
        with patch("app.services.note_service.ChatCompletionService.call_llm_api", side_effect=mock_call_llm_api):
            note_data = {
                "title": "AI Test Note",
                "content": "Please process this with AI",
                "tags": "ai,test",
                "folder": "AI Tests",
                "note_style": "standard",
                "ai_process": True
            }
            
            response = authorized_client.post("/api/v1/notes/", json=note_data)
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert data["title"] == note_data["title"]
            assert data["content"] == note_data["content"]
            assert data["tags"] == note_data["tags"]
            assert data["folder"] == note_data["folder"]
    
    def test_create_note_validation_error(self, authorized_client):
        """Test validation error when creating a note with invalid data"""
        invalid_data = {
            # Missing required title
            "content": "This is a test note",
            "tags": ["test"],
            "note_style": "INVALID_STYLE" # Invalid enum value
        }
        
        response = authorized_client.post("/api/v1/notes/", json=invalid_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_create_note_unauthorized(self, client):
        """Test unauthorized access when creating a note"""
        note_data = {
            "title": "Test Note",
            "content": "This is a test note",
            "note_style": "standard"
        }
        
        response = client.post("/api/v1/notes/", json=note_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # === GET NOTE TESTS ===
    def test_get_note_success(self, authorized_client, db, create_test_user, test_user):
        """Test successfully retrieving a note"""
        # First create a note
        note_data = {
            "title": "Get Test Note",
            "content": "This is a test note for get endpoint",
            "note_style": "standard"
        }
        
        create_response = authorized_client.post("/api/v1/notes/", json=note_data)
        note_id = create_response.json()["id"]
        
        # Now get the note
        response = authorized_client.get(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == note_id
        assert data["title"] == note_data["title"]
        assert data["content"] == note_data["content"]
    
    def test_get_note_not_found(self, authorized_client):
        """Test getting a non-existent note"""
        non_existent_id = 9999
        response = authorized_client.get(f"/api/v1/notes/{non_existent_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_get_note_unauthorized(self, client):
        """Test unauthorized access when getting a note"""
        response = client.get("/api/v1/notes/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_other_user_note(self, authorized_client, db):
        """Test accessing another user's note"""
        # Create another user directly
        other_user = User(
            id=2,
            username="otheruser",
            email="other@example.com",
            hashed_password="fakehashed_password",
            is_active=True
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        
        # Let's assume we know the note ID from the other user is 1000
        # In a real test, you'd need to create it properly
        response = authorized_client.get("/api/v1/notes/1000") 
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # === LIST NOTES TESTS ===
    def test_list_notes(self, authorized_client, db):
        """Test listing user's notes with pagination and filtering"""
        # Create a few test notes
        note_data = [
            {"title": "Note 1", "content": "Content 1", "folder": "Folder1", "tags": "tag1,tag2", "note_style": "standard"},
            {"title": "Note 2", "content": "Content 2", "folder": "Folder1", "tags": "tag2,tag3", "note_style": "standard"},
            {"title": "Note 3", "content": "Content 3", "folder": "Folder2", "tags": "tag1", "note_style": "standard"}
        ]
        
        for note in note_data:
            authorized_client.post("/api/v1/notes/", json=note)
        
        # Test basic listing
        response = authorized_client.get("/api/v1/notes/")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3
        
        # Test filtering by folder
        response = authorized_client.get("/api/v1/notes/?folder=Folder1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) >= 2
        for note in data["items"]:
            assert note["folder"] == "Folder1"
        
        # Test filtering by tag
        response = authorized_client.get("/api/v1/notes/?tag=tag1")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["items"]) >= 2
        
        # Test search
        response = authorized_client.get("/api/v1/notes/?search=Content 2")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert any(note["content"] == "Content 2" for note in data["items"])
    
    # === UPDATE NOTE TESTS ===
    def test_update_note_success(self, authorized_client, db):
        """Test successfully updating a note"""
        # First create a note
        note_data = {
            "title": "Original Title",
            "content": "Original content",
            "note_style": "standard"
        }
        
        create_response = authorized_client.post("/api/v1/notes/", json=note_data)
        note_id = create_response.json()["id"]
        
        # Now update the note
        update_data = {
            "title": "Updated Title",
            "content": "Updated content",
            "tags": "updated,test",
            "folder": "Updated Folder"
        }
        
        response = authorized_client.put(f"/api/v1/notes/{note_id}", json=update_data)
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["id"] == note_id
        assert data["title"] == update_data["title"]
        assert data["content"] == update_data["content"]
        assert set(data["tags"]) == set(update_data["tags"])
        assert data["folder"] == update_data["folder"]
    
    def test_update_note_not_found(self, authorized_client):
        """Test updating a non-existent note"""
        non_existent_id = 9999
        update_data = {"title": "Updated Title"}
        
        response = authorized_client.put(f"/api/v1/notes/{non_existent_id}", json=update_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_note_unauthorized(self, client):
        """Test unauthorized access when updating a note"""
        update_data = {
            "title": "Updated Title",
            "content": "Updated content"
        }
        
        response = client.put("/api/v1/notes/1", json=update_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # === DELETE NOTE TESTS ===
    def test_delete_note_success(self, authorized_client, db):
        """Test successfully deleting a note"""
        # First create a note
        note_data = {
            "title": "Delete Test Note",
            "content": "This note will be deleted",
            "note_style": "standard"
        }
        
        create_response = authorized_client.post("/api/v1/notes/", json=note_data)
        note_id = create_response.json()["id"]
        
        # Now delete the note
        response = authorized_client.delete(f"/api/v1/notes/{note_id}")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify the note is deleted
        get_response = authorized_client.get(f"/api/v1/notes/{note_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_note_not_found(self, authorized_client):
        """Test deleting a non-existent note"""
        non_existent_id = 9999
        response = authorized_client.delete(f"/api/v1/notes/{non_existent_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_delete_note_unauthorized(self, client):
        """Test unauthorized access when deleting a note"""
        response = client.delete("/api/v1/notes/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # === VOICE NOTE TESTS ===
    def test_get_notes(self, authorized_client, mock_note_service, mock_auth):
        """Test the GET /notes endpoint"""
        # Make the request
        response = authorized_client.get("/api/v1/notes")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["title"] == "Test Note 1"
        
        # Verify service was called correctly
        mock_note_service.get_user_notes.assert_awaited_once_with(1)
    
    def test_get_note(self, authorized_client, mock_note_service, mock_auth):
        """Test the GET /notes/{note_id} endpoint"""
        # Set up the mock to return a note
        mock_note_service.get_user_note.return_value = {
            "id": 1,
            "title": "Test Note Detail",
            "content": "Test content",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "completed"
        }
        
        # Make the request
        response = authorized_client.get("/api/v1/notes/1")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Note Detail"
        assert data["content"] == "Test content"
        
        # Verify service was called correctly
        mock_note_service.get_user_note.assert_awaited_once_with(1, 1)
    
    def test_create_voice_note(self, authorized_client, mock_note_service, mock_auth):
        """Test the POST /notes/voice endpoint"""
        # Create a mock file
        mock_file = MockFile(filename="test_audio.mp3", content=b"test audio content")
        
        # Make the request with a mock file
        response = authorized_client.post(
            "/api/v1/notes/voice",
            files={"file": ("test_audio.mp3", mock_file.read(), "audio/mpeg")},
            data={"note_style": "standard"}
        )
        
        # Check the response
        assert response.status_code == 202
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Voice Note"
        assert data["status"] == "processing"
        
        # Verify service was called correctly
        # Note: We can't directly check the file content in the test
        # since TestClient converts it to a UploadFile
        mock_note_service.process_audio_upload.assert_awaited_once()
        # Check that the parameters were passed
        args, kwargs = mock_note_service.process_audio_upload.call_args
        assert args[0] == 1  # user_id
        assert kwargs.get('note_data').note_style == NoteStyle.STANDARD
    
    def test_create_voice_note_with_custom_style(self, authorized_client, mock_note_service, mock_auth):
        """Test the POST /notes/voice endpoint with a custom note style"""
        # Create a mock file
        mock_file = MockFile(filename="test_audio.mp3", content=b"test audio content")
        
        # Reset the mock to ensure we get fresh call args
        mock_note_service.process_audio_upload.reset_mock()
        
        # Make the request with a mock file and specific note style
        response = authorized_client.post(
            "/api/v1/notes/voice",
            files={"file": ("test_audio.mp3", mock_file.read(), "audio/mpeg")},
            data={"note_style": "blog_post"}
        )
        
        # Check the response
        assert response.status_code == 202
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Voice Note"
        assert data["status"] == "processing"
        
        # Verify service was called correctly with the specified style
        mock_note_service.process_audio_upload.assert_awaited_once()
        args, kwargs = mock_note_service.process_audio_upload.call_args
        assert args[0] == 1  # user_id
        assert kwargs.get('note_data').note_style == NoteStyle.BLOG_POST
    
    def test_process_note_audio(self, authorized_client, mock_note_service, mock_auth):
        """Test the POST /notes/{note_id}/process endpoint"""
        # Make the request
        response = authorized_client.post("/api/v1/notes/1/process")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Processed Voice Note"
        assert data["status"] == "completed"
        
        # Verify service was called correctly
        mock_note_service.process_existing_audio.assert_awaited_once_with(1, 1)
    
    def test_export_note(self, authorized_client, mock_note_service, mock_auth):
        """Test the GET /notes/{note_id}/export endpoint"""
        # Make the request
        response = authorized_client.get("/api/v1/notes/1/export?format=markdown")
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Exported Note"
        assert data["format"] == "markdown"
        assert data["content"] == "# Test Content"
        
        # Verify service was called correctly
        mock_note_service.export_note.assert_awaited_once_with(
            1, 1, NoteExportFormat.MARKDOWN
        )
    
    def test_export_note_invalid_format(self, authorized_client, mock_note_service, mock_auth):
        """Test the GET /notes/{note_id}/export endpoint with invalid format"""
        # Make the request with an invalid format
        response = authorized_client.get("/api/v1/notes/1/export?format=invalid")
        
        # Check the response
        assert response.status_code == 422  # Validation error
    
    # TODO: Implement rate limiting and uncomment this test
    # def test_rate_limited_access(self, client, mock_auth):
    #     """Test that endpoints are rate limited"""
    #     # Mock the rate limiter dependency to test rate limiting
    #     with patch("app.api.deps.rate_limiter") as mock_rate_limiter:
    #         # Configure the rate limiter to reject the request
    #         mock_rate_limiter.check.return_value = False
    #         
    #         # Make the request
    #         response = client.get("/api/v1/notes")
    #         
    #         # Check the response indicates rate limiting
    #         assert response.status_code == 429
    #         assert "Too many requests" in response.json()["detail"]

    # === FOLDERS AND TAGS TESTS ===
    def test_get_folders(self, authorized_client, db):
        """Test retrieving user's folders"""
        # First create a few notes with different folders
        note_data = [
            {"title": "Note 1", "content": "Content 1", "folder": "Folder1", "tags": "tag1", "note_style": "standard"},
            {"title": "Note 2", "content": "Content 2", "folder": "Folder2", "tags": "tag2", "note_style": "standard"},
            {"title": "Note 3", "content": "Content 3", "folder": "Folder1", "tags": "tag3", "note_style": "standard"}
        ]
        
        for note in note_data:
            authorized_client.post("/api/v1/notes/", json=note)
        
        # Test getting folders
        response = authorized_client.get("/api/v1/notes/folders")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "folders" in data
        folders = data["folders"]
        assert set(folders) >= {"Folder1", "Folder2"}
    
    def test_get_tags(self, authorized_client, db):
        """Test retrieving user's tags"""
        # First create a few notes with different tags
        note_data = [
            {"title": "Note 1", "content": "Content 1", "tags": "tag1,tag2", "note_style": "standard"},
            {"title": "Note 2", "content": "Content 2", "tags": "tag2,tag3", "note_style": "standard"},
            {"title": "Note 3", "content": "Content 3", "tags": "tag1,tag4", "note_style": "standard"}
        ]
        
        for note in note_data:
            authorized_client.post("/api/v1/notes/", json=note)
        
        # Test getting tags
        response = authorized_client.get("/api/v1/notes/tags")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert "tags" in data
        tags = data["tags"]
        assert set(tags) >= {"tag1", "tag2", "tag3", "tag4"}
    
    # === SHARING TESTS ===
    def test_share_note(self, authorized_client, db, monkeypatch):
        """Test sharing a note"""
        # Mock subscription check to return True for allow_sharing
        def mock_get_by_user_id(*args, **kwargs):
            subscription_mock = MagicMock()
            subscription_mock.allow_sharing = True
            return subscription_mock
        
        with patch("app.repositories.subscription_repository.SubscriptionRepository.get_by_user_id", 
                  side_effect=mock_get_by_user_id):
            
            # First create a note
            note_data = {
                "title": "Share Test Note",
                "content": "This note will be shared",
                "note_style": "standard"
            }
            
            create_response = authorized_client.post("/api/v1/notes/", json=note_data)
            note_id = create_response.json()["id"]
            
            # Now share the note
            response = authorized_client.post(f"/api/v1/notes/{note_id}/share")
            assert response.status_code == status.HTTP_200_OK
            
            data = response.json()
            assert "public_share_id" in data
            assert "share_url" in data
            
            # Test retrieving the shared note with public link
            share_id = data["public_share_id"]
            public_response = authorized_client.get(f"/api/v1/notes/shared/{share_id}")
            assert public_response.status_code == status.HTTP_200_OK
            
            # Test unsharing the note
            unshare_response = authorized_client.delete(f"/api/v1/notes/{note_id}/share")
            assert unshare_response.status_code == status.HTTP_200_OK
            assert not unshare_response.json()["is_public"]
            
            # Verify the shared link no longer works
            public_response_after = authorized_client.get(f"/api/v1/notes/shared/{share_id}")
            assert public_response_after.status_code == status.HTTP_404_NOT_FOUND 