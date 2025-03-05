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

    # app/services/llm_service.py
    async def parse_quest_from_text(self, text: str, language: Optional[str], country: str) -> QuestCreate:
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
            return (current_date + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        def this_weekday(current_date, weekday):
            """Find this week's occurrence of a specific weekday"""
            days_ahead = weekday - current_date.weekday()
            if days_ahead < 0:  # Target day already happened this week
                days_ahead += 7
            return (current_date + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
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
        You are a helpful assistant that extracts structured task information from user voice commands. Convert the user's voice command into a properly formatted quest object.

        CRITICAL INFORMATION: The values of the task fields must match the user's language. input language must match output language. meaning english input = english output, spanish input = spanish output.
        CRITICAL INFORMATION: It's important to take into account the user's country in order to properly interpret its text. For example, Argentinian spanish is not the same as Mexican spanish.
        CRITICAL INFORMATION: due dates must computed relative to the current date and time (Current date in ISO format: {current_time_iso})
        CRITICAL INFORMATION: if a date is provided, but not a specific time. then automatically set it to 23:59:59 (hh:mm:ss)
        
        User's language: {language}
        User's country: {country}
        Current day: {current_time.weekday()} (0: Monday, 1: Tuesday, 2: Wednesday, 3: Thursday, 4: Friday, 5: Saturday, 6: Sunday)
        Current Date: {current_time.strftime('%Y-%m-%d')}
        Current date in ISO format: {current_time_iso}
        Current Time (UTC): {current_time.strftime('%H:%M:%S')}
        Current Day of Month: {current_time.day}
        Current Month: {current_time.month}
        Current Year: {current_time.year}



        # Date Calculation Helper:
        - For "today" use: {current_time.strftime('%Y-%m-%d')}
        - For "tomorrow" use: {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')}
        - For "next Monday" use: {next_weekday(current_time, 0)}
        - For "next Tuesday" use: {next_weekday(current_time, 1)}
        - For "next Wednesday" use: {next_weekday(current_time, 2)}
        - For "next Thursday" use: {next_weekday(current_time, 3)}
        - For "next Friday" use: {next_weekday(current_time, 4)}
        - For "next Saturday" use: {next_weekday(current_time, 5)}
        - For "next Sunday" use: {next_weekday(current_time, 6)}
        - For "in X days" use: {(current_time + timedelta(days=3)).strftime('%Y-%m-%d')} (example for "in 3 days")
        - For "next month" use: {next_month(current_time)}
        - For "end of month" use: {end_of_month(current_time)}

        Extract the following fields:
        - title: The main task description (required). Keep it very short and concise (3-6 words). Do not include dates/times here.
        - description: Additional details about the task (optional).
        - due_date: The due date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ), computed relative to the current date and time. Follow the date calculation guide above.
        - rarity: Importance/complexity (common, uncommon, rare, epic, legendary). Default: common.
        - quest_type: Type (daily, regular, epic, boss). Default: regular.
        - priority: Numeric priority from 1 (low) to 100 (high). Default: 33. Higher if urgent.

        These extracted fields values must respect the original language of the user's input.

        Examples: (if today was 2025-03-05, which is a Wednesday)
        
        User says: "El viernes tengo que llevar a mi gato al veterinario. Turno a las 11 am"
        {{
          "title": "Llevar gato al veterinario",
          "description": "El viernes tengo que turno a las 11 AM para llevar a mi gato al veterinario.",
          "due_date": "2025-03-7T11:00:00Z",
          "rarity": "common",
          "quest_type": "regular",
          "priority": 2
        }}

        User says: "I have a dentist appointment next Monday at 11 am."
        {{
          "title": "Dentist appointment",
          "description": "I have a dentist appointment next Monday at 11 am",
          "due_date": "2025-03-10T11:00:00Z",
          "rarity": "common",
          "quest_type": "regular",
          "priority": 2
        }}
        

        The values of the fields must be generated based on the user's language. input language must match output language. meaning english input = english output. spanish input = spanish output.
        Return valid JSON only. Do not include comments in the JSON response. No explanations. 
        In case there is not enough information to extract the required fields, ONLY THEN it's acceptable to provide a non-valid JSON response.
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
            print(response)
            quest_data = json.loads(response)

            # Safely handle enum conversions with case insensitivity
            if "rarity" in quest_data:
                try:
                    quest_data["rarity"] = QuestRarity(quest_data["rarity"].lower())
                except (ValueError, KeyError):
                    quest_data["rarity"] = QuestRarity.COMMON

            if "quest_type" in quest_data:
                try:
                    quest_data["quest_type"] = QuestType(quest_data["quest_type"].lower())
                except (ValueError, KeyError):
                    quest_data["quest_type"] = QuestType.REGULAR

            # Ensure due_date is parsed as UTC datetime or None
            if "due_date" in quest_data:
              try:
                  quest_data["due_date"] = datetime.fromisoformat(quest_data["due_date"])
              except (ValueError, TypeError):
                  del quest_data["due_date"]

            # Create and return QuestCreate object
            return QuestCreate(**quest_data)

        except Exception as e:
            raise ValueError(f"Error parsing quest from text: {e}")
          
def get_llm_service() -> LLMService:
    """
    Provides an LLMService instance for dependency injection.
    """
    return LLMService()
