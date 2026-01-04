"""
User Model für JuraMind
Speichert Benutzerinformationen und Subscription-Status
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
import enum

from app.core.database import Base


class SubscriptionTier(str, enum.Enum):
    """
    Subscription-Stufen für JuraMind
    """
    FREE = "free"           # Kostenlos, limitiert
    STARTER = "starter"     # Einzelanwalt
    PROFESSIONAL = "professional"  # Kleine Kanzlei
    ENTERPRISE = "enterprise"      # Große Kanzlei


class User(Base):
    """
    Benutzer-Modell
    
    Speichert:
    - Authentifizierungsdaten
    - Profilinformationen
    - Subscription-Status
    - Nutzungsstatistiken
    """
    __tablename__ = "users"
    
    # ============================================
    # Primärschlüssel
    # ============================================
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # ============================================
    # Authentifizierung
    # ============================================
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )
    
    # ============================================
    # Profil
    # ============================================
    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    company: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True
    )
    
    job_title: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # ============================================
    # Subscription
    # ============================================
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier),
        default=SubscriptionTier.FREE
    )
    
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    # ============================================
    # Nutzungslimits
    # ============================================
    analyses_this_month: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    
    analyses_reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # ============================================
    # Timestamps
    # ============================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # ============================================
    # Relationships
    # ============================================
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="owner",
        cascade="all, delete-orphan"
    )
    
    # ============================================
    # Properties
    # ============================================
    @property
    def full_name(self) -> str:
        """Vollständiger Name des Users"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email.split("@")[0]
    
    @property
    def monthly_limit(self) -> int:
        """Maximale Analysen pro Monat basierend auf Subscription"""
        limits = {
            SubscriptionTier.FREE: 5,
            SubscriptionTier.STARTER: 50,
            SubscriptionTier.PROFESSIONAL: 200,
            SubscriptionTier.ENTERPRISE: 999999,  # Unlimited
        }
        return limits.get(self.subscription_tier, 5)
    
    @property
    def can_analyze(self) -> bool:
        """Prüft ob der User noch Analysen durchführen kann"""
        return self.analyses_this_month < self.monthly_limit
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"

