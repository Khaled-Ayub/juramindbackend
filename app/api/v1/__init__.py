"""
JuraMind API v1 Router
Sammelt alle v1 Endpoints
"""

from fastapi import APIRouter
from app.api.v1 import auth, documents, analysis, users

# Haupt-Router für API v1
api_router = APIRouter()

# Sub-Router einbinden
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentifizierung"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Benutzer"]
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Dokumente"]
)

api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analyse"]
)

