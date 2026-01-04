"""
Document Schemas für API Validation
Pydantic Models für Dokument-Endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.document import DocumentType, AnalysisStatus, RiskLevel


# ============================================
# Document Schemas
# ============================================
class DocumentCreate(BaseModel):
    """
    Schema für Dokument-Upload Metadaten
    """
    title: Optional[str] = Field(
        None,
        max_length=500,
        description="Optionaler Titel des Dokuments"
    )
    description: Optional[str] = Field(
        None,
        description="Optionale Beschreibung"
    )
    document_type: DocumentType = Field(
        default=DocumentType.OTHER,
        description="Art des Dokuments"
    )


class DocumentResponse(BaseModel):
    """
    Schema für Dokument-Response
    """
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    document_type: DocumentType
    title: Optional[str]
    description: Optional[str]
    page_count: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    # Optional: Analyse-Zusammenfassung
    latest_analysis: Optional["DocumentAnalysisResponse"] = None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """
    Schema für Dokument-Liste mit Pagination
    """
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================
# Analysis Schemas
# ============================================
class ClauseAnalysis(BaseModel):
    """
    Einzelne Klausel-Analyse
    """
    id: int = Field(..., description="Klausel-ID")
    title: str = Field(..., description="Klausel-Titel (z.B. '§ 3 Haftung')")
    content: str = Field(..., description="Klausel-Text")
    risk_level: RiskLevel = Field(..., description="Risikostufe")
    ai_comment: str = Field(..., description="KI-Kommentar zur Klausel")
    legal_references: List[str] = Field(
        default=[],
        description="Relevante Gesetzesverweise"
    )


class RecommendationItem(BaseModel):
    """
    Einzelne Empfehlung
    """
    priority: str = Field(..., description="Priorität (high/medium/low)")
    clause_id: Optional[int] = Field(None, description="Betroffene Klausel")
    suggestion: str = Field(..., description="Empfohlene Maßnahme")


class KeyTerms(BaseModel):
    """
    Extrahierte Schlüsselbegriffe
    """
    parties: List[str] = Field(default=[], description="Vertragsparteien")
    dates: Dict[str, str] = Field(default={}, description="Wichtige Daten")
    amounts: List[Dict[str, Any]] = Field(default=[], description="Beträge und Werte")


class DocumentAnalysisResponse(BaseModel):
    """
    Vollständige Analyse-Response
    """
    id: int
    document_id: int
    status: AnalysisStatus
    error_message: Optional[str]
    
    # Ergebnisse
    summary: Optional[str] = Field(
        None,
        description="Kurze Zusammenfassung des Dokuments"
    )
    overall_risk_level: Optional[RiskLevel] = Field(
        None,
        description="Gesamt-Risikobewertung"
    )
    risk_score: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Risiko-Score (0-100)"
    )
    
    # Detaillierte Ergebnisse
    clauses: Optional[List[ClauseAnalysis]] = None
    recommendations: Optional[List[RecommendationItem]] = None
    key_terms: Optional[KeyTerms] = None
    
    # Metadaten
    model_used: Optional[str]
    tokens_used: Optional[int]
    processing_time_ms: Optional[int]
    
    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ============================================
# Analysis Request Schemas
# ============================================
class AnalysisRequest(BaseModel):
    """
    Anfrage für neue Dokumentenanalyse
    """
    document_id: int = Field(
        ...,
        description="ID des zu analysierenden Dokuments"
    )
    analysis_type: str = Field(
        default="full",
        description="Art der Analyse: 'full', 'quick', 'clauses_only'"
    )
    language: str = Field(
        default="de",
        description="Sprache für die Analyse"
    )


class TextAnalysisRequest(BaseModel):
    """
    Direkte Text-Analyse (ohne Dokument-Upload)
    """
    text: str = Field(
        ...,
        min_length=50,
        max_length=100000,
        description="Zu analysierender Text"
    )
    document_type: DocumentType = Field(
        default=DocumentType.CONTRACT,
        description="Art des Dokuments"
    )
    analysis_type: str = Field(
        default="full",
        description="Art der Analyse"
    )


# ============================================
# Statistics Schemas
# ============================================
class AnalysisStats(BaseModel):
    """
    Analyse-Statistiken für Dashboard
    """
    total_documents: int
    total_analyses: int
    analyses_this_month: int
    monthly_limit: int
    risk_distribution: Dict[str, int] = Field(
        default={},
        description="Verteilung der Risikostufen"
    )
    recent_analyses: List[DocumentAnalysisResponse] = []

