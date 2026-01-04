"""
RAG-Modul für JuraMind
Retrieval Augmented Generation mit Haystack 2.x und ChromaDB
"""

from .document_store import get_document_store, COLLECTIONS
from .query_pipeline import analyze_contract_with_rag
from .indexing_pipeline import index_documents, create_indexing_pipeline

__all__ = [
    "get_document_store",
    "COLLECTIONS",
    "analyze_contract_with_rag",
    "index_documents",
    "create_indexing_pipeline",
]

