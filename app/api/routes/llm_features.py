# app/api/routes/llm_features.py (updated with dependency injection)
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app import models
from app.api import deps
from app.services.llm_service import LLMService, get_llm_service
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/translate", response_model=Dict[str, str])
async def translate_text(
    *,
    db: Session = Depends(deps.get_db),
    text: str = Body(..., embed=True),
    source_language: str = Body(..., embed=True),
    target_language: str = Body("english", embed=True),
    current_user: models.User = Depends(deps.get_current_active_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Dict[str, str]:
    """
    Translate text from one language to another using LLM.

    - **text**: The text to translate
    - **source_language**: Source language (e.g., "french", "spanish", "german")
    - **target_language**: Target language (default is "english")

    Returns the translated text.
    """
    if not settings.ENABLE_LLM_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="LLM features are not enabled on this server.",
        )

    try:
        logger.info(f"Translating text from {source_language} to {target_language}")

        # Use dedicated translate method (with injected service)
        translation = await llm_service.translate_text(
            text=text, source_language=source_language, target_language=target_language
        )

        logger.info(f"Translation completed successfully")

        return {
            "original_text": text,
            "translated_text": translation,
            "source_language": source_language,
            "target_language": target_language,
        }

    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error translating text: {str(e)}",
        )


@router.get("/diagnostics", response_model=Dict[str, Any])
async def llm_diagnostics(
    current_user: models.User = Depends(deps.get_current_active_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Dict[str, Any]:
    """
    Run diagnostics on LLM service configuration.
    This endpoint is for troubleshooting connection issues.
    """
    if not settings.ENABLE_LLM_FEATURES:
        raise HTTPException(
            status_code=400,
            detail="LLM features are not enabled on this server.",
        )

    try:
        # Get configuration information
        provider_info = {
            "name": llm_service.provider.name,
            "base_url": llm_service.provider.base_url,
            "default_model": llm_service.provider.default_model,
            # Mask API key for security
            "api_key_set": bool(llm_service.provider.api_key),
            "api_key_prefix": llm_service.provider.api_key[:4] + "..."
            if llm_service.provider.api_key
            else None,
        }

        # Test connection
        test_result = None
        try:
            # Simple echo test
            test_result = await llm_service.call_llm_api(
                prompt="Echo test",
                system_prompt="Respond with exactly: 'Connection successful'",
                temperature=0.0,
                # Use the lightest model available
                model=getattr(settings, "OPENROUTER_TRANSLATION_MODEL", None)
                or llm_service.provider.default_model,
            )
        except Exception as e:
            test_result = f"Connection error: {str(e)}"

        # Return diagnostic information
        return {
            "provider": provider_info,
            "server_host": str(settings.SERVER_HOST),
            "models": {
                "default": settings.OPENROUTER_DEFAULT_MODEL,
                "translation": getattr(settings, "OPENROUTER_TRANSLATION_MODEL", None),
                "parsing": getattr(settings, "OPENROUTER_PARSING_MODEL", None),
            },
            "connection_test": test_result,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Diagnostics error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error running diagnostics: {str(e)}",
        )
