# app/services/llm_service.py
import json
import asyncio
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from openai import OpenAI, AsyncOpenAI
import logging

from app.schemas.quest import QuestCreate
from app.models.quest import QuestRarity, QuestType
from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(BaseModel):
    name: str
    api_key: str
    base_url: str
    default_model: str


class ChatCompletionService:
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
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        json_response: bool = False,
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Call the LLM API with the given prompt.

        Args:
            prompt: User prompt to send to the LLM
            system_prompt: System instructions for the LLM
            temperature: Temperature parameter for response randomness
            json_response: Whether to request a JSON response
            model: Specific model to use, or None for default

        Returns:
            Response text from the LLM, or None if an error occurred
        """
        from app.utils.timeout import with_timeout
        from app.core.exceptions import ProcessingException

        if not settings.ENABLE_LLM_FEATURES:
            logger.warning("LLM features are disabled in settings")
            return None

        if not model:
            model = settings.OPENROUTER_DEFAULT_MODEL

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            }

            json_format_text = ""
            if json_response:
                json_format_text = "You must respond with a JSON object, nothing else."
                messages[0]["content"] = f"{system_prompt} {json_format_text}"
                # Add JSON response formatting
                headers["HTTP-Referer"] = "https://questlogger.app"
                headers["X-Title"] = "Quest Logger"

            logger.info(
                f"Calling LLM API with model: {model}, json_response: {json_response}"
            )

            # Use the async client that was initialized in __init__
            try:
                # Use AsyncOpenAI client for proper async operation
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"} if json_response else None,
                    timeout=settings.LLM_TIMEOUT,
                )

                # Extract the response text
                content = response.choices[0].message.content

                if json_response:
                    # Validate JSON format for json_response=True
                    try:
                        json.loads(content)
                    except json.JSONDecodeError:
                        logger.error(
                            f"Invalid JSON response from LLM: {content[:100]}..."
                        )
                        return None

                return content
            except asyncio.TimeoutError:
                logger.error(f"LLM API call timed out (limit: {settings.LLM_TIMEOUT}s)")
                raise ProcessingException("LLM API call timed out")

        except ProcessingException as e:
            # Already logged in timeout utility
            return None
        except Exception as e:
            logger.error(f"Error calling LLM API: {str(e)}", exc_info=True)
            return None

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

    async def parse_quest_from_text(
        self, text: str, language: Optional[str], country: str
    ) -> QuestCreate:
        """
        Use an LLM to parse a quest from text input

        Args:
            text: The text to parse into a quest structure
            language: Detected language of the input text
            country: User's country for cultural context

        Returns:
            QuestCreate object with structured quest data
        """
        from datetime import datetime, timezone, timedelta
        import calendar

        current_time = datetime.now(timezone.utc)
        current_time_iso = current_time.replace(microsecond=0).isoformat()

        # Helper functions for date calculations
        def next_weekday(current_date, weekday):
            """Find the next occurrence of a specific weekday"""
            days_ahead = weekday - current_date.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            return (current_date + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        def this_weekday(current_date, weekday):
            """Find this week's occurrence of a specific weekday"""
            days_ahead = weekday - current_date.weekday()
            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7
            return (current_date + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        def next_month(current_date):
            """Get the first day of next month"""
            if current_date.month == 12:
                return f"{current_date.year + 1}-01-01"
            else:
                return f"{current_date.year}-{current_date.month + 1:02d}-01"

        def end_of_month(current_date):
            """Get the last day of current month"""
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            return f"{current_date.year}-{current_date.month:02d}-{last_day}"

        system_prompt = f"""
        You extract task data from voice commands into quest objects. ALWAYS format response as JSON.

        Current: {current_time_iso} ({current_time.strftime('%Y-%m-%d')}, {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][current_time.weekday()]})

        Date reference:
        - Today: {current_time.strftime('%Y-%m-%d')}
        - Tomorrow: {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')}
        - Next Mon: {next_weekday(current_time, 0)}
        - Next Tue: {next_weekday(current_time, 1)}
        - Next Wed: {next_weekday(current_time, 2)}
        - Next Thu: {next_weekday(current_time, 3)}
        - Next Fri: {next_weekday(current_time, 4)}
        - Next Sat: {next_weekday(current_time, 5)}
        - Next Sun: {next_weekday(current_time, 6)}

        Extract these fields in {language}:
        - title: Brief task name (MAXIMUM 20 CHARACTERS. NOT MORE. WONT WORK OTHERWISE)
        - description: Format based on complexity:
          * FOR SINGLE TASKS: Just "#### Task details" with 1-2 sentences
          * FOR MULTIPLE TASKS: "#### Summary" followed by "- [ ] subtask1" etc.
          * FOR MULTIPLE TASKS: Sub tasks must be kept concise and brief to the point
          * Always remove "I need to", "I have to", and similar phrases
        - due_date: ISO format (YYYY-MM-DDTHH:MM:SSZ)
          * IMPORTANT: If specific date mentioned (e.g., Monday, Friday, tomorrow), calculate correctly
          * If no time specified, use 23:59:59
          * If no date, set to null
        - rarity: common/uncommon/rare/epic/legendary (default: common)
        - quest_type: daily/regular/epic/boss (default: regular)
        - priority: 1-100 (default: 33)

        Examples:
        1. SINGLE TASK: "Dentist appointment on Friday at 2pm"
        {{
          "title": "Dentist appointment",
          "description": "#### Dental visit\\nGo to dentist office on Friday at 2pm",
          "due_date": "{(current_time.replace(hour=14, minute=0, second=0) + timedelta(days=(4-current_time.weekday()) % 7)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
          "rarity": "common",
          "quest_type": "regular",
          "priority": 40
        }}

        2. MULTIPLE TASKS: "Work on app: add markdown, create daily system, improve mobile UI"
        {{
          "title": "App improvements",
          "description": "#### App development\\n- [ ] Add markdown support\\n- [ ] Create daily system\\n- [ ] Improve mobile UI",
          "due_date": null,
          "rarity": "uncommon",
          "quest_type": "regular",
          "priority": 40
        }}

        Return valid JSON ONLY. Match input language in output.
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
            if settings.ENVIRONMENT != "production":
                logger.debug(f"LLM response for quest parsing: {response}")

            quest_data = json.loads(response)

            # Safely handle enum conversions with case insensitivity
            if "rarity" in quest_data:
                try:
                    quest_data["rarity"] = QuestRarity(quest_data["rarity"].lower())
                except (ValueError, KeyError):
                    logger.warning(
                        f"Invalid rarity value in LLM response: {quest_data.get('rarity')}, defaulting to COMMON"
                    )
                    quest_data["rarity"] = QuestRarity.COMMON

            if "quest_type" in quest_data:
                try:
                    quest_data["quest_type"] = QuestType(
                        quest_data["quest_type"].lower()
                    )
                except (ValueError, KeyError):
                    logger.warning(
                        f"Invalid quest_type value in LLM response: {quest_data.get('quest_type')}, defaulting to REGULAR"
                    )
                    quest_data["quest_type"] = QuestType.REGULAR

            # Ensure due_date is parsed as UTC datetime or None
            if "due_date" in quest_data:
                try:
                    quest_data["due_date"] = datetime.fromisoformat(
                        quest_data["due_date"]
                    )
                except (ValueError, TypeError):
                    del quest_data["due_date"]

            # Create and return QuestCreate object
            return QuestCreate(**quest_data)

        except Exception as e:
            raise ValueError(f"Error parsing quest from text: {e}")
