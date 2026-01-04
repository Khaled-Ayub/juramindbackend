"""
JuraMind API Schemas (Pydantic Models)
Für Request/Response Validation
"""

from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
    Token,
    TokenPayload
)
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentAnalysisResponse,
    ClauseAnalysis,
    AnalysisRequest
)

__all__ = [
    # User
    "UserCreate",
    "UserLogin", 
    "UserResponse",
    "UserUpdate",
    "Token",
    "TokenPayload",
    # Document
    "DocumentCreate",
    "DocumentResponse",
    "DocumentAnalysisResponse",
    "ClauseAnalysis",
    "AnalysisRequest"
]

