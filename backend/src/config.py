from __future__ import annotations

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 應用程式 
    APP_ENV: Literal["development", "production"] = "development"

    # 資料庫 
    DATABASE_URL: str = "sqlite+aiosqlite:///./knowledge_shredder.db"

    # 上傳限制
    UPLOAD_MAX_SIZE_MB: int = 20

    # LLM 接口
    LLM_PROVIDER: str = "azure_openai"

    # Azure OpenAI
    AOAI_ENDPOINT: str = ""
    AOAI_API_KEY: str = ""
    AOAI_DEPLOYMENT: str = ""
    AOAI_API_VERSION: str = "2024-02-01"
    
    # Gemini
    GEMINI_API_KEY: str = "gemini_key"
    GEMINI_MODEL:str ="gemini-2.0-flash"

settings = Settings()
