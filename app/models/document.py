"""
Document Models für JuraMind
Speichert hochgeladene Dokumente und deren Analysen
"""

from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List, Dict, Any
import enum

from app.core.database import Base


class DocumentType(str, enum.Enum):
    """
    Dokumenttypen die JuraMind verarbeiten kann
    """
    CONTRACT = "contract"           # Vertrag
    LEGAL_OPINION = "legal_opinion" # Rechtsgutachten
    COURT_DECISION = "court_decision"  # Gerichtsurteil
    CORRESPONDENCE = "correspondence"   # Schriftverkehr
    OTHER = "other"


class AnalysisStatus(str, enum.Enum):
    """
    Status einer Dokumentenanalyse
    """
    PENDING = "pending"       # Wartet auf Verarbeitung
    PROCESSING = "processing" # Wird analysiert
    COMPLETED = "completed"   # Erfolgreich abgeschlossen
    FAILED = "failed"         # Fehler bei Analyse


class RiskLevel(str, enum.Enum):
    """
    Risikostufen für Vertragsklauseln
    """
    LOW = "low"           # Unbedenklich
    MEDIUM = "medium"     # Prüfen empfohlen
    HIGH = "high"         # Kritisch
    CRITICAL = "critical" # Sofortige Aufmerksamkeit


class Document(Base):
    """
    Hochgeladenes Dokument
    
    Speichert:
    - Datei-Metadaten
    - Extrahierter Text
    - Verknüpfung zu Analysen
    """
    __tablename__ = "documents"
    
    # ============================================
    # Primärschlüssel
    # ============================================
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # ============================================
    # Besitzer
    # ============================================
    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="documents"
    )
    
    # ============================================
    # Datei-Informationen
    # ============================================
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    file_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # ============================================
    # Dokumenten-Metadaten
    # ============================================
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType),
        default=DocumentType.OTHER
    )
    
    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ============================================
    # Extrahierter Inhalt
    # ============================================
    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
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
    
    # ============================================
    # Relationships
    # ============================================
    analyses: Mapped[List["DocumentAnalysis"]] = relationship(
        "DocumentAnalysis",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Document {self.original_filename}>"


class DocumentAnalysis(Base):
    """
    KI-Analyse eines Dokuments
    
    Speichert:
    - Analyse-Ergebnisse
    - Gefundene Klauseln und Risiken
    - KI-Empfehlungen
    """
    __tablename__ = "document_analyses"
    
    # ============================================
    # Primärschlüssel
    # ============================================
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # ============================================
    # Verknüpftes Dokument
    # ============================================
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="analyses"
    )
    
    # ============================================
    # Analyse-Status
    # ============================================
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus),
        default=AnalysisStatus.PENDING
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # ============================================
    # Analyse-Ergebnisse
    # ============================================
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    overall_risk_level: Mapped[Optional[RiskLevel]] = mapped_column(
        Enum(RiskLevel),
        nullable=True
    )
    
    risk_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    
    # ============================================
    # Detaillierte Ergebnisse (JSON)
    # ============================================
    clauses: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    """
    Format:
    {
        "clauses": [
            {
                "id": 1,
                "title": "§ 3 Haftung",
                "content": "...",
                "risk_level": "high",
                "ai_comment": "...",
                "legal_references": ["§ 307 BGB"]
            }
        ]
    }
    """
    
    recommendations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    """
    Format:
    {
        "recommendations": [
            {
                "priority": "high",
                "clause_id": 1,
                "suggestion": "..."
            }
        ]
    }
    """
    
    key_terms: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    """
    Format:
    {
        "parties": ["Auftraggeber", "Auftragnehmer"],
        "dates": {"start": "2024-01-01", "end": "2024-12-31"},
        "amounts": [{"value": 10000, "currency": "EUR", "context": "Auftragswert"}]
    }
    """
    
    # ============================================
    # KI-Metadaten
    # ============================================
    model_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # ============================================
    # Timestamps
    # ============================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    def __repr__(self) -> str:
        return f"<DocumentAnalysis {self.id} for Document {self.document_id}>"

