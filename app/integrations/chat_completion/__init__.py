from app.integrations.chat_completion.llm import ChatCompletionService


def get_chat_completion_service() -> ChatCompletionService:
    """
    Provides an LLMService instance for dependency injection.
    """
    return ChatCompletionService()
