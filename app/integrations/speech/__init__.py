from app.integrations.speech.deepgram_stt_client import DeepgramSTTClient

def get_stt_client() -> DeepgramSTTClient:
    """
    Provides an LLMService instance for dependency injection.
    """
    return DeepgramSTTClient()

