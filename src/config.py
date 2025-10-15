"""
Configuration module for loading and validating environment variables.

This module loads all required secrets and settings from environment variables.
It validates that critical values are present at startup to fail fast.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Application configuration loaded from environment variables."""
    
    # GitHub configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")
    
    # Groq API configuration for LLM code generation
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # User secret for request validation
    USER_SECRET: str = os.getenv("USER_SECRET", "")
    
    # Storage for processed requests (prevents duplicates)
    STORAGE_PATH: Path = Path("/tmp/tds_processed.json")
    
    # Storage for decoded attachments
    ATTACHMENTS_DIR: Path = Path("/tmp/tds_attachments")
    
    # Log file location
    # Uses /tmp for cloud hosting (Railway, Render, Fly.io all support /tmp)
    # Set LOG_FILE_PATH env var to override, or None to disable file logging
    LOG_FILE: Path = Path(os.getenv("LOG_FILE_PATH", "/tmp/tds_app.log")) if os.getenv("LOG_FILE_PATH", "/tmp/tds_app.log") else None
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # INFO for production, DEBUG for dev
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate that all required configuration values are present.
        Raises ValueError if any required value is missing.
        """
        missing = []
        
        if not cls.GITHUB_TOKEN:
            missing.append("GITHUB_TOKEN")
        if not cls.GITHUB_USERNAME:
            missing.append("GITHUB_USERNAME")
        if not cls.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not cls.USER_SECRET:
            missing.append("USER_SECRET")
        
        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Configuration validated successfully")
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directories ensured: {cls.ATTACHMENTS_DIR}, {cls.STORAGE_PATH.parent}")


# Validate configuration on module load
Config.validate()
Config.ensure_directories()
