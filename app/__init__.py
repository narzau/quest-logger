"""
Main package initialization.
Sets up logging and other app-wide configurations.
"""
import logging
from app.core.logging import setup_logging

# Initialize logging at package level
logger = setup_logging()
logger.debug("Initializing Quest Logger application")
