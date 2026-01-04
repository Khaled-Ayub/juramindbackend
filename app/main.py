"""
JuraMind API - Hauptanwendung
FastAPI Application Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.v1 import api_router


# ============================================
# Lifecycle Management
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Anwendungs-Lifecycle:
    - Startup: Datenbankverbindung herstellen
    - Shutdown: Verbindungen schließen
    """
    # Startup
    print("🚀 JuraMind API startet...")
    
    if settings.DEBUG:
        # Nur in Entwicklung: Tabellen automatisch erstellen
        await init_db()
        print("📦 Datenbank-Tabellen erstellt/geprüft")
    
    print(f"✅ JuraMind API läuft auf {settings.HOST}:{settings.PORT}")
    
    yield
    
    # Shutdown
    print("🛑 JuraMind API fährt herunter...")
    await close_db()
    print("👋 Auf Wiedersehen!")


# ============================================
# FastAPI Application
# ============================================
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,  # Swagger nur in Dev
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# ============================================
# Middleware
# ============================================

# CORS für Frontend-Zugriff
# Nutzt cors_origins_list Property, die JSON/CSV/Wildcard parst
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request-Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Fügt X-Process-Time Header zu jeder Response hinzu
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response


# ============================================
# Exception Handlers
# ============================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Globaler Exception Handler für unbehandelte Fehler
    """
    # In Produktion: Keine Details zeigen
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": "Ein interner Fehler ist aufgetreten"}
        )


# ============================================
# API Routes
# ============================================

# v1 API unter /api/v1 einbinden
app.include_router(api_router, prefix="/api/v1")


# ============================================
# Health & Status Endpoints
# ============================================
@app.get(
    "/",
    tags=["Status"],
    summary="API Root",
    description="Basis-Endpoint mit API-Informationen"
)
async def root():
    """
    Gibt grundlegende API-Informationen zurück
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else None
    }


@app.get(
    "/health",
    tags=["Status"],
    summary="Health Check",
    description="Prüft ob die API erreichbar ist"
)
async def health_check():
    """
    Health-Check für Load Balancer und Monitoring
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION
    }


@app.get(
    "/api/v1/status",
    tags=["Status"],
    summary="API Status",
    description="Detaillierter API-Status"
)
async def api_status():
    """
    Detaillierter Status mit Feature-Informationen
    """
    return {
        "api": "JuraMind",
        "version": settings.APP_VERSION,
        "features": {
            "contract_analysis": True,
            "legal_search": True,
            "document_upload": True
        },
        "limits": {
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE
        }
    }


# ============================================
# Für lokale Entwicklung
# ============================================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

