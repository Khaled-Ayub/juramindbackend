"""
JuraMind Database Models
Export aller Modelle für einfachen Import
"""

from app.models.user import User
from app.models.document import Document, DocumentAnalysis

__all__ = ["User", "Document", "DocumentAnalysis"]

