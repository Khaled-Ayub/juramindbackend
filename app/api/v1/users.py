"""
User API Endpoints
Profil-Management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_password_hash
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Eigenes Profil abrufen",
    description="Gibt die Profildaten des eingeloggten Benutzers zurück"
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Gibt das Profil des aktuell eingeloggten Benutzers zurück.
    
    Enthält:
    - Persönliche Daten
    - Subscription-Status
    - Nutzungsstatistiken
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        company=current_user.company,
        job_title=current_user.job_title,
        subscription_tier=current_user.subscription_tier,
        subscription_expires_at=current_user.subscription_expires_at,
        analyses_this_month=current_user.analyses_this_month,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        full_name=current_user.full_name,
        monthly_limit=current_user.monthly_limit,
        can_analyze=current_user.can_analyze
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Profil aktualisieren",
    description="Aktualisiert die Profildaten des eingeloggten Benutzers"
)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Aktualisiert das Profil des aktuell eingeloggten Benutzers.
    
    Nur übergebene Felder werden aktualisiert (PATCH-Semantik).
    
    Aktualisierbare Felder:
    - **first_name**
    - **last_name**
    - **company**
    - **job_title**
    """
    # Nur übergebene Felder aktualisieren
    update_data = user_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        company=current_user.company,
        job_title=current_user.job_title,
        subscription_tier=current_user.subscription_tier,
        subscription_expires_at=current_user.subscription_expires_at,
        analyses_this_month=current_user.analyses_this_month,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
        full_name=current_user.full_name,
        monthly_limit=current_user.monthly_limit,
        can_analyze=current_user.can_analyze
    )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Account löschen",
    description="Löscht den eigenen Account permanent"
)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Löscht den Account des aktuell eingeloggten Benutzers.
    
    ⚠️ Diese Aktion ist nicht rückgängig zu machen!
    Alle Dokumente und Analysen werden ebenfalls gelöscht.
    """
    await db.delete(current_user)
    await db.commit()
    return None

