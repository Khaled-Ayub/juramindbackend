"""
Datenbank-Konfiguration für JuraMind
Async SQLAlchemy Setup mit PostgreSQL
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

from app.core.config import settings


# ============================================
# Naming Convention für Constraints
# ============================================
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)


# ============================================
# Base Model für alle DB-Modelle
# ============================================
class Base(DeclarativeBase):
    """
    Basisklasse für alle SQLAlchemy-Modelle
    """
    metadata = metadata


# ============================================
# Async Engine & Session
# ============================================
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # SQL-Logging nur im Debug-Modus
    future=True,
    pool_pre_ping=True,   # Verbindungsprüfung vor Nutzung
    pool_size=5,          # Verbindungspool-Größe
    max_overflow=10       # Max. zusätzliche Verbindungen
)

# Session Factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


# ============================================
# Dependency für FastAPI
# ============================================
async def get_db() -> AsyncSession:
    """
    Dependency die eine DB-Session bereitstellt
    Wird automatisch geschlossen nach Request
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================
# Datenbank-Initialisierung
# ============================================
async def init_db():
    """
    Erstellt alle Tabellen in der Datenbank
    Nur für Entwicklung - in Produktion Alembic nutzen!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Schließt alle Datenbankverbindungen
    """
    await engine.dispose()

