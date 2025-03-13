"""
Integration tests for note lifecycle.
Tests the full lifecycle of a note from creation to processing and export.
"""
import pytest
import os
from fastapi.testclient import TestClient
import tempfile

from app.main import app
from app.models.note import NoteStyle, NoteExportFormat
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings

# Create a test client with authentication bypass
@pytest.fixture
def authenticated_client():
    # Override dependency to bypass authentication
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "test_user"}
    
    # Override db dependency to use test database
    test_db = TestingSessionLocal()
    app.dependency_overrides[get_db] = lambda: test_db
    
    # Initialize the test database
    Base.metadata.create_all(bind=engine)
    
    # Create a test client
    client = TestClient(app)
    
    yield client
    
    # Clean up
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides = {}

@pytest.fixture
def sample_note_data():
    """Sample data for creating a note"""
    return {
        "title": "Integration Test Note",
        "content": "This is a test note created during integration testing",
        "tags": ["integration", "test"],
        "folder": "Integration Tests"
    }

@pytest.fixture
def sample_audio_file():
    """Create a temporary audio file for testing"""
    # For a real test, we would use a real audio file
    # But for testing purposes, we'll create a simple file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
        temp.write(b'dummy audio content')
        temp_name = temp.name
    
    yield temp_name
    
    # Clean up
    if os.path.exists(temp_name):
        os.unlink(temp_name)


class TestNoteLifecycle:
    """Test the complete lifecycle of a note"""
    
    @pytest.mark.skip(reason="This is an integration test that requires a real database and audio processing, marked as skip for CI")
    def test_basic_note_lifecycle(self, authenticated_client, sample_note_data):
        """Test creating, retrieving, updating, and deleting a note"""
        # Step 1: Create a new note
        response = authenticated_client.post("/notes", json=sample_note_data)
        assert response.status_code == 201
        note_data = response.json()
        note_id = note_data["id"]
        assert note_data["title"] == sample_note_data["title"]
        
        # Step 2: Retrieve the note
        response = authenticated_client.get(f"/notes/{note_id}")
        assert response.status_code == 200
        assert response.json()["id"] == note_id
        assert response.json()["title"] == sample_note_data["title"]
        
        # Step 3: Update the note
        update_data = {"title": "Updated Note Title"}
        response = authenticated_client.put(f"/notes/{note_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Note Title"
        
        # Step 4: Delete the note
        response = authenticated_client.delete(f"/notes/{note_id}")
        assert response.status_code == 200
        
        # Verify the note is gone
        response = authenticated_client.get(f"/notes/{note_id}")
        assert response.status_code == 404
    
    @pytest.mark.skip(reason="This is an integration test that requires real audio processing, marked as skip for CI")
    def test_voice_note_lifecycle(self, authenticated_client, sample_audio_file):
        """Test the lifecycle of a voice note from upload to processing to export"""
        # Step 1: Upload a voice note
        with open(sample_audio_file, "rb") as f:
            response = authenticated_client.post(
                "/notes/voice",
                files={"file": ("test.mp3", f, "audio/mpeg")},
                data={"note_style": "standard"}
            )
        
        assert response.status_code == 202
        note_data = response.json()
        note_id = note_data["id"]
        assert note_data["status"] == "processing"
        
        # Step 2: Process the note
        # In a real scenario, this would be done asynchronously
        # For testing, we'll call the process endpoint directly
        response = authenticated_client.post(f"/notes/{note_id}/process")
        assert response.status_code == 200
        assert response.json()["status"] in ["processing", "completed"]
        
        # Step 3: Wait for processing to complete
        # In a real test, we would poll until completed or timeout
        # For this test, we'll skip the wait
        
        # Step 4: Export the note in different formats
        for export_format in ["text", "markdown"]:
            response = authenticated_client.get(f"/notes/{note_id}/export?format={export_format}")
            assert response.status_code == 200
            assert response.json()["format"] == export_format
            assert "content" in response.json()
        
        # Step 5: Delete the note
        response = authenticated_client.delete(f"/notes/{note_id}")
        assert response.status_code == 200
        
        # Verify the note is gone
        response = authenticated_client.get(f"/notes/{note_id}")
        assert response.status_code == 404 