from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import UploadFile
import tempfile
import os


class TranscriptionResult:
    """
    Standard result object for all transcription services
    """

    def __init__(
        self,
        text: str,
        language_detected: Optional[str] = None,
        confidence: Optional[float] = None,
        translation: Optional[str] = None,
        raw_response: Optional[Dict[str, Any]] = None,
    ):
        self.text = text  # Original transcribed text
        self.language_detected = language_detected  # Detected language code
        self.confidence = confidence  # Confidence score if available
        self.translation = translation  # Translated text (if requested)
        self.raw_response = raw_response  # Original provider response

    def get_text_for_parsing(self) -> str:
        """
        Returns the best text for further processing:
        - If translation to English was requested and available, use that
        - Otherwise, use the original transcription
        """
        return self.translation if self.translation else self.text


class BaseSTTService(ABC):
    """
    Abstract base class for all speech-to-text services
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_file: UploadFile,
        language: Optional[str] = None,
        translate_to_english: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text

        Args:
            audio_file: The audio file to transcribe
            language: Optional language hint (ISO code)
            translate_to_english: Whether to translate non-English results to English

        Returns:
            TranscriptionResult object with standardized output
        """
        pass

    async def save_upload_file_temp(self, upload_file: UploadFile) -> str:
        """
        Save an upload file to a temporary file and return the path
        """
        try:
            suffix = (
                os.path.splitext(upload_file.filename)[1]
                if upload_file.filename
                else ""
            )
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                content = await upload_file.read()
                temp.write(content)
                return temp.name
        finally:
            await upload_file.seek(0)  # Reset file pointer
