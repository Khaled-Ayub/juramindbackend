"""
User Schemas für API Validation
Pydantic Models für Request/Response
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

from app.models.user import SubscriptionTier


# ============================================
# Auth Schemas
# ============================================
class UserCreate(BaseModel):
    """
    Schema für User-Registrierung
    """
    email: EmailStr = Field(
        ...,
        description="E-Mail-Adresse des Users"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Passwort (min. 8 Zeichen)"
    )
    first_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Vorname"
    )
    last_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Nachname"
    )
    company: Optional[str] = Field(
        None,
        max_length=200,
        description="Kanzlei/Unternehmen"
    )
    
    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Prüft Passwortstärke:
        - Mindestens 8 Zeichen
        - Mindestens ein Großbuchstabe
        - Mindestens ein Kleinbuchstabe
        - Mindestens eine Zahl
        """
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten")
        if not re.search(r"[a-z]", v):
            raise ValueError("Passwort muss mindestens einen Kleinbuchstaben enthalten")
        if not re.search(r"\d", v):
            raise ValueError("Passwort muss mindestens eine Zahl enthalten")
        return v


class UserLogin(BaseModel):
    """
    Schema für User-Login
    """
    email: EmailStr = Field(
        ...,
        description="E-Mail-Adresse"
    )
    password: str = Field(
        ...,
        description="Passwort"
    )


class UserUpdate(BaseModel):
    """
    Schema für Profil-Update
    """
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=200)
    job_title: Optional[str] = Field(None, max_length=100)


class UserResponse(BaseModel):
    """
    Schema für User-Response (ohne sensible Daten)
    """
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    company: Optional[str]
    job_title: Optional[str]
    subscription_tier: SubscriptionTier
    subscription_expires_at: Optional[datetime]
    analyses_this_month: int
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    # Computed fields
    full_name: Optional[str] = None
    monthly_limit: Optional[int] = None
    can_analyze: Optional[bool] = None
    
    class Config:
        from_attributes = True  # Für SQLAlchemy-Model-Konvertierung


# ============================================
# Token Schemas
# ============================================
class Token(BaseModel):
    """
    JWT Token Response
    """
    access_token: str = Field(
        ...,
        description="JWT Access Token"
    )
    refresh_token: str = Field(
        ...,
        description="JWT Refresh Token"
    )
    token_type: str = Field(
        default="bearer",
        description="Token-Typ (immer 'bearer')"
    )
    expires_in: int = Field(
        ...,
        description="Gültigkeit in Sekunden"
    )


class TokenPayload(BaseModel):
    """
    Dekodierter Token-Inhalt
    """
    sub: str  # User ID
    exp: datetime
    type: str  # "access" oder "refresh"


class RefreshTokenRequest(BaseModel):
    """
    Request für Token-Refresh
    """
    refresh_token: str = Field(
        ...,
        description="Gültiger Refresh Token"
    )


# ============================================
# Password Reset Schemas
# ============================================
class PasswordResetRequest(BaseModel):
    """
    Passwort-Reset anfordern
    """
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """
    Passwort-Reset bestätigen
    """
    token: str
    new_password: str = Field(..., min_length=8)
    
    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Passwort muss mindestens einen Großbuchstaben enthalten")
        if not re.search(r"[a-z]", v):
            raise ValueError("Passwort muss mindestens einen Kleinbuchstaben enthalten")
        if not re.search(r"\d", v):
            raise ValueError("Passwort muss mindestens eine Zahl enthalten")
        return v

