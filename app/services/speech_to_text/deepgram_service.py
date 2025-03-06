# app/services/speech_to_text/deepgram_service.py
import os
import tempfile
from typing import Optional, Dict, Any, BinaryIO

from fastapi import UploadFile
from app.core.config import settings
from .base import BaseSTTService, TranscriptionResult

# Import Deepgram SDK
from deepgram import (
    DeepgramClient,
    PrerecordedOptions,
    FileSource,
)


class DeepgramSTTService(BaseSTTService):
    """
    Speech-to-text service using Deepgram's SDK
    """

    def __init__(self):
        # Initialize the Deepgram client with the API key from settings
        # The SDK automatically reads from DEEPGRAM_API_KEY environment variable
        # We can also pass it explicitly if needed
        self.client = DeepgramClient(api_key=settings.DEEPGRAM_API_KEY)
        self.model = getattr(settings, "DEEPGRAM_MODEL", "nova-2")

    async def transcribe(
        self,
        audio_file: UploadFile,
        language: Optional[str],
    ) -> TranscriptionResult:
        """
        Transcribe audio using Deepgram SDK

        Note: translate_to_english parameter is ignored as we delegate translation
        to the LLM service instead
        """
        try:
            # Save uploaded file to a temporary location
            temp_file_path = await self.save_upload_file_temp(audio_file)

            # Read the audio file into a buffer
            with open(temp_file_path, "rb") as file:
                buffer_data = file.read()

            # Prepare the file source
            payload: FileSource = {
                "buffer": buffer_data,
                "mimetype": audio_file.content_type,
            }

            # Configure Deepgram options
            options = PrerecordedOptions(
                model=self.model,
                smart_format=True,
                punctuate=True,
                diarize=False,
                utterances=False,
                language=language,
                detect_language=True if not language else False,
            )

            # Call Deepgram API
            print(options)

            response = self.client.listen.rest.v("1").transcribe_file(
                payload, options, timeout=60
            )

            # Extract results from response
            results = response.results
            print(results, "results deep ram")
            # Get the channels data (we'll use the first channel)
            if not results.channels or len(results.channels) == 0:
                return TranscriptionResult(text="", raw_response=results.to_dict())

            channel = results.channels[0]

            # Get transcript from alternatives (use the first one)
            if not channel.alternatives or len(channel.alternatives) == 0:
                return TranscriptionResult(text="", raw_response=results.to_dict())

            alternative = channel.alternatives[0]

            # Extract transcript text
            transcript = alternative.transcript

            # Get confidence score
            confidence = (
                alternative.confidence if hasattr(alternative, "confidence") else None
            )

            return TranscriptionResult(
                text=transcript,
                language=language,
                confidence=confidence,
                translation=None,  # No translation from Deepgram
                raw_response=results.to_dict(),
            )

        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
