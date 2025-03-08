from app.integrations.speech.base import BaseSTTService
from app.integrations.speech.factory import STTServiceFactory

def get_stt_service() -> BaseSTTService:
    """
    Provides an LLMService instance for dependency injection.
    """
    return STTServiceFactory.create(provider="deepgram")

