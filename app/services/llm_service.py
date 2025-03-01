# app/services/llm_service.py
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from openai import OpenAI, AsyncOpenAI

from app.schemas.quest import QuestCreate
from app.models.quest import QuestRarity, QuestType
from app.core.config import settings


class LLMProvider(BaseModel):
    name: str
    api_key: str
    base_url: str
    default_model: str


class LLMService:
    """
    Service for interacting with LLMs through OpenRouter or OpenAI
    using the OpenAI SDK which works transparently with OpenRouter
    """

    def __init__(self, provider: str = "openrouter"):
        self.provider = self._get_provider_config(provider)

        # Initialize AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=self.provider.api_key, base_url=self.provider.base_url
        )

    def _get_provider_config(self, provider_name: str) -> LLMProvider:
        """
        Get configuration for the specified provider
        """
        if provider_name == "openrouter":
            return LLMProvider(
                name="openrouter",
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_API_URL,
                default_model=settings.OPENROUTER_DEFAULT_MODEL,
            )
        elif provider_name == "openai":
            return LLMProvider(
                name="openai",
                api_key=settings.OPENAI_API_KEY,
                base_url=f"{settings.OPENAI_API_URL}/v1",
                default_model="gpt-4o",
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

    async def call_llm_api(
        self,
        prompt: str,
        system_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_response: bool = False,
    ) -> str:
        """
        Make a generic call to the LLM API using OpenAI SDK
        """
        model = model or self.provider.default_model

        # Prepare extra headers if using OpenRouter
        extra_headers = {}
        if self.provider.name == "openrouter":
            extra_headers = {
                "HTTP-Referer": str(settings.SERVER_HOST),  # Convert to string
                "X-Title": "ADHD Quest Tracker",
            }

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Prepare response format if JSON is requested
        response_format = {"type": "json_object"} if json_response else None

        # Make the API call
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            extra_headers=extra_headers,
        )

        # Extract and return content
        return response.choices[0].message.content or ""

    async def translate_text(
        self, text: str, source_language: str, target_language: str = "english"
    ) -> str:
        """
        Translate text between any language pair

        Args:
            text: The text to translate
            source_language: The source language
            target_language: The target language (default: "english")

        Returns:
            Translated text
        """
        system_prompt = """
        You are a helpful translation assistant. Your task is to translate the provided text
        accurately, maintaining the meaning and intent of the original text.
        Keep the translation natural and conversational.
        Return only the translation, with no additional text or explanation.
        """

        prompt = f"""
        Please translate the following text from {source_language} to {target_language}:
        
        {text}
        """

        # Use a lighter model for translation if configured
        model = (
            getattr(settings, "OPENROUTER_TRANSLATION_MODEL", None)
            or self.provider.default_model
        )

        # Make the API call with the specified model
        translation = await self.call_llm_api(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more accurate translation
            model=model,
        )

        return translation

    async def parse_quest_from_text(self, text: str) -> QuestCreate:
        """
        Use an LLM to parse a quest from text input

        Args:
            text: The text to parse into a quest structure

        Returns:
            QuestCreate object with structured quest data
        """
        system_prompt = """
        You are a helpful assistant that extracts structured task information from user voice commands.
        Convert the user's voice command into a properly formatted quest object.
        
        Extract the following fields:
        - title: The main task description (required)
        - description: Additional details about the task (optional)
        - due_date: When the task is due in ISO format (optional)
        - rarity: The importance/complexity of the task (common, uncommon, rare, epic, legendary)
        - quest_type: The type of task (daily, regular, epic, boss)
        - priority: Numeric priority from 1 (low) to 5 (high)
        
        Default values if not specified:
        - rarity: common
        - quest_type: regular
        - priority: 1
        - due_date: null
        
        Return only valid JSON without any explanation or additional text.
        """

        try:
            # Use a lighter model for parsing if configured
            model = (
                getattr(settings, "OPENROUTER_PARSING_MODEL", None)
                or self.provider.default_model
            )

            response = await self.call_llm_api(
                prompt=f"Convert this voice command to a quest: {text}",
                system_prompt=system_prompt,
                json_response=True,
                model=model,
            )

            # Parse the JSON response
            quest_data = json.loads(response)

            # Map string values to enums if needed
            if "rarity" in quest_data:
                quest_data["rarity"] = QuestRarity(quest_data["rarity"])
            if "quest_type" in quest_data:
                quest_data["quest_type"] = QuestType(quest_data["quest_type"])

            # Create and return QuestCreate object
            return QuestCreate(**quest_data)

        except Exception as e:
            # Handle parsing errors
            # For simplicity, create a basic quest if parsing fails
            return QuestCreate(
                title=f"New Quest: {text[:50]}{'...' if len(text) > 50 else ''}",
                description=text,
                rarity=QuestRarity.COMMON,
                quest_type=QuestType.REGULAR,
                priority=1,
            )


def get_llm_service() -> LLMService:
    """
    Provides an LLMService instance for dependency injection.
    """
    return LLMService()
