# app/services/speech_to_text/factory.py
from typing import Dict, Optional, Type
from app.core.config import settings
from .base import BaseSTTService

# Import all service implementations

from .deepgram_service import DeepgramSTTService


class STTServiceFactory:
    """
    Factory class to create the appropriate STT service based on configuration
    """

    _services: Dict[str, Type[BaseSTTService]] = {"deepgram": DeepgramSTTService}

    @classmethod
    def create(cls, provider: Optional[str] = None) -> BaseSTTService:
        """
        Create and return a configured STT service instance

        Args:
            provider: The provider to use, or None to use the default from settings

        Returns:
            Configured STT service instance
        """
        # Use specified provider or default from settings
        provider_name = provider or settings.DEFAULT_STT_PROVIDER

        # Get the service class
        service_class = cls._services.get(provider_name.lower())
        if not service_class:
            raise ValueError(f"Unknown STT provider: {provider_name}")

        # Create and return the service instance
        return service_class()

    @classmethod
    def get_available_providers(cls) -> Dict[str, bool]:
        """
        Get a dictionary of available providers and whether they are configured

        Returns:
            Dict mapping provider names to boolean indicating if they're configured
        """
        available = {}

        # Check Deepgram configuration
        available["deepgram"] = bool(settings.DEEPGRAM_API_KEY)

        return available

