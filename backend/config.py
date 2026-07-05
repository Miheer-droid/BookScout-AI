"""
BookScout AI - Configuration
Central configuration for the application.
"""

import os


class Settings:
    """Application settings."""

    # Ollama Configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # Scraping Configuration
    REQUEST_TIMEOUT: int = 15
    MAX_RETRIES: int = 2
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Research Configuration
    MAX_CANDIDATE_BOOKS: int = 5
    MAX_SEARCH_RESULTS: int = 8

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
