"""
Configuration module for ScamSathi AI.
Manages environment variables, timeouts, validation limits, and model parameters.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Settings:
    """Application settings with strict validation and safe defaults."""
    
    # API credentials
    NEBIUS_API_KEY: str = os.getenv("NEBIUS_API_KEY", "").strip()
    NEBIUS_BASE_URL: str = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1").rstrip("/")
    NEBIUS_MODEL_ID: str = os.getenv("NEBIUS_MODEL_ID", "nvidia/nemotron-4-340b-instruct").strip()
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()

    # Safety limits
    MAX_INPUT_LENGTH: int = 10000
    MIN_INPUT_LENGTH: int = 15
    REQUEST_TIMEOUT_SECONDS: int = 45
    MAX_SEARCH_RESULTS: int = 6

    # Model parameters
    MODEL_TEMPERATURE: float = 0.1
    MAX_TOKENS: int = 3000

    @classmethod
    def is_nebius_configured(cls) -> bool:
        return bool(cls.NEBIUS_API_KEY and len(cls.NEBIUS_API_KEY) > 8)

    @classmethod
    def is_tavily_configured(cls) -> bool:
        return bool(cls.TAVILY_API_KEY and len(cls.TAVILY_API_KEY) > 8)

settings = Settings()
