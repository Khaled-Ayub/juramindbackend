"""
Konfiguration für JuraMind Backend
Lädt Umgebungsvariablen und definiert App-Settings
"""

import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


# Default-Werte als Konstante, damit wir sie auch in Validatoren sauber wiederverwenden können
DEFAULT_CORS_ORIGINS: List[str] = [
    "http://localhost:3000",        # Next.js Dev
    "http://localhost:8080",        # Vite Dev
    "https://juramind.vercel.app",  # Vercel
    "https://juramind.flowedge.de", # Production (FlowEdge)
]


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
    # Achtung: Pydantic Settings erwartet für List[str] standardmäßig JSON aus ENV.
    # In Railway wird oft ein kommaseparierter String gepflegt -> wir parsen beides.
    CORS_ORIGINS: List[str] = DEFAULT_CORS_ORIGINS

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        """
        Akzeptiert folgende Formate:
        - JSON: ["https://a.de","https://b.de"]
        - Komma-separiert: https://a.de,https://b.de
        - Stern: *
        - Leer/None: nutzt DEFAULT_CORS_ORIGINS
        """
        if v is None:
            return list(DEFAULT_CORS_ORIGINS)

        # Falls bereits als Liste geliefert (z.B. aus Code / Tests)
        if isinstance(v, (list, tuple, set)):
            return [str(x).strip() for x in v if str(x).strip()]

        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return list(DEFAULT_CORS_ORIGINS)
            if s == "*":
                return ["*"]

            # Wenn JSON übergeben wurde, bevorzugt das verwenden
            # (Railway/ENV kann auch Anführungszeichen enthalten)
            if s.startswith("["):
                try:
                    loaded = json.loads(s)
                    if isinstance(loaded, list):
                        return [str(x).strip() for x in loaded if str(x).strip()]
                except Exception:
                    # Fallback: weiter unten als CSV behandeln
                    pass

            # CSV-Fallback
            return [p.strip() for p in s.split(",") if p.strip()]

        # Fallback: pydantic soll selbst versuchen zu casten
        return v
    
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
    
    # Pydantic v2 Settings-Konfiguration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached Settings-Instanz
    Wird nur einmal geladen und dann wiederverwendet
    """
    return Settings()


# Globale Settings-Instanz
settings = get_settings()

