import os
import tempfile
import logging
from typing import Dict, Any
from fastapi import UploadFile
from pydub import AudioSegment

# Set up module logger
logger = logging.getLogger(__name__)


async def get_audio_info(audio_file: UploadFile) -> Dict[str, Any]:
    """
    Extract information from an audio file, including duration.

    Args:
        audio_file: The uploaded audio file

    Returns:
        A dictionary containing audio information such as:
        - duration: float (in seconds)
        - channels: int
        - sample_width: int (in bytes)
        - frame_rate: int (in Hz)
        - format: str (file format like mp3, wav, etc.)
    """
    temp_file_path = None
    try:
        # Save the audio to a temporary file
        suffix = os.path.splitext(audio_file.filename)[1] if audio_file.filename else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            content = await audio_file.read()
            temp.write(content)
            temp_file_path = temp.name

        # Reset file pointer for future use
        await audio_file.seek(0)

        # Load with pydub to extract information
        audio = AudioSegment.from_file(temp_file_path)

        # Extract information
        audio_info = {
            "duration": audio.duration_seconds,
            "channels": audio.channels,
            "sample_width": audio.sample_width,
            "frame_rate": audio.frame_rate,
            "format": suffix.lstrip(".") if suffix else "unknown",
        }

        logger.debug(
            f"Audio analysis complete: duration={audio_info['duration']:.2f}s, format={audio_info['format']}"
        )
        return audio_info

    except Exception as e:
        # Log the error but return a default with just estimated duration
        # This ensures the process doesn't completely fail if the audio analysis fails
        logger.error(f"Error analyzing audio file: {str(e)}", exc_info=True)
        return {"duration": 120.0, "error": str(e)}  # Fallback to 2 minutes

    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(
                    f"Failed to delete temporary audio file {temp_file_path}: {str(e)}"
                )
