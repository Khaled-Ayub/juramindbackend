"""
Auth API Endpoints
Login, Register, Token Refresh
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.core.config import settings
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    RefreshTokenRequest
)

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Neuen Benutzer registrieren",
    description="Erstellt einen neuen Benutzer-Account"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Registriert einen neuen Benutzer.
    
    - **email**: Gültige E-Mail-Adresse (unique)
    - **password**: Min. 8 Zeichen, Groß-/Kleinbuchstaben, Zahl
    - **first_name**: Optional
    - **last_name**: Optional
    - **company**: Optional (Kanzlei/Firma)
    """
    # Prüfen ob E-Mail bereits existiert
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ein Account mit dieser E-Mail existiert bereits"
        )
    
    # Neuen User erstellen
    new_user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        company=user_data.company,
        is_active=True,
        is_verified=False  # E-Mail-Verifizierung noch nicht implementiert
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        company=new_user.company,
        job_title=new_user.job_title,
        subscription_tier=new_user.subscription_tier,
        subscription_expires_at=new_user.subscription_expires_at,
        analyses_this_month=new_user.analyses_this_month,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at,
        last_login_at=new_user.last_login_at,
        full_name=new_user.full_name,
        monthly_limit=new_user.monthly_limit,
        can_analyze=new_user.can_analyze
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Benutzer einloggen",
    description="Authentifiziert einen Benutzer und gibt JWT-Tokens zurück"
)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Loggt einen Benutzer ein und gibt Access + Refresh Token zurück.
    
    - **email**: Registrierte E-Mail-Adresse
    - **password**: Passwort
    
    Returns:
    - **access_token**: Kurzlebiger Token für API-Calls (30 min)
    - **refresh_token**: Langlebiger Token zum Erneuern (7 Tage)
    """
    # User suchen
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    # Prüfen ob User existiert und Passwort stimmt
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige E-Mail oder Passwort",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Prüfen ob Account aktiv ist
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account ist deaktiviert"
        )
    
    # Last Login aktualisieren
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Tokens erstellen
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Token erneuern",
    description="Erstellt neue Tokens mit einem gültigen Refresh Token"
)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Erneuert Access und Refresh Token.
    
    - **refresh_token**: Gültiger Refresh Token aus vorherigem Login
    """
    # Token dekodieren
    payload = decode_token(request.refresh_token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder abgelaufener Token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Prüfen ob es ein Refresh Token ist
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kein gültiger Refresh Token"
        )
    
    user_id = payload.get("sub")
    
    # User laden
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer nicht gefunden oder inaktiv"
        )
    
    # Neue Tokens erstellen
    token_data = {"sub": str(user.id)}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Benutzer ausloggen",
    description="Invalidiert die aktuelle Session (Client muss Tokens löschen)"
)
async def logout():
    """
    Logout-Endpoint.
    
    Da JWTs stateless sind, muss der Client die Tokens lokal löschen.
    In einer erweiterten Version könnte hier ein Token-Blacklist implementiert werden.
    """
    # Bei JWT-basierten Systemen gibt es serverseitig nichts zu tun
    # Der Client muss die Tokens aus dem localStorage/Cookie löschen
    return None

