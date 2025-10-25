"""
Global configuration settings for the medical claims microservice.

Combines OCR, LLM, and logging options into one centralized module.
All settings can be overridden via environment variables or a `.env` file.
"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ==== OCR / Extraction Settings ====
    USE_LLM: bool = False
    OCR_ENGINE: str = "tesseract"

    # ==== LLM Options ====
    # Whether to use LLM extraction when regex-based parsing fails
    USE_LLM_EXTRACTION: bool = True

    # Whether to use LLM for question-answering fallback
    USE_LLM_QA: bool = True

    # Placeholder API key for future OpenAI/Gemini integration
    LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")

    # ==== Paths ====
    PERSIST_PATH: str = os.getenv("CLAIMS_STORE_PATH", "data/parsed_store.json")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "data/tmp")

    # ==== Logging ====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Helper to get current app settings instance."""
    return Settings()
