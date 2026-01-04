"""
Konfiguration für JuraMind Backend
Lädt Umgebungsvariablen und definiert App-Settings
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Zentrale Konfigurationsklasse
    Werte werden aus .env oder Umgebungsvariablen geladen
    """
    
    # ============================================
    # App Metadata
    # ============================================
    APP_NAME: str = "JuraMind API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "KI-gestützte Rechtsassistenz API"
    DEBUG: bool = False
    
    # ============================================
    # Server
    # ============================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ============================================
    # Database (PostgreSQL auf Railway)
    # ============================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/juramind"
    
    # ============================================
    # Security / JWT
    # ============================================
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ============================================
    # CORS (Frontend URLs)
    # ============================================
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",      # Next.js Dev
        "http://localhost:8080",       # Vite Dev
        "https://juramind.vercel.app", # Production
    ]
    
    # ============================================
    # KI / LLM Provider
    # ============================================
    # Welchen Provider nutzen: "openai" oder "anthropic"
    AI_PROVIDER: str = "anthropic"
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # ============================================
    # Rate Limiting
    # ============================================
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # ============================================
    # File Upload
    # ============================================
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: List[str] = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Cached Settings-Instanz
    Wird nur einmal geladen und dann wiederverwendet
    """
    return Settings()


# Globale Settings-Instanz
settings = get_settings()

