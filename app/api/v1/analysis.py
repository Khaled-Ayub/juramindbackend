"""
Analysis API Endpoints
KI-gestützte Dokumentenanalyse
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentAnalysis, AnalysisStatus
from app.schemas.document import (
    AnalysisRequest,
    TextAnalysisRequest,
    DocumentAnalysisResponse,
    AnalysisStats
)
from app.services.ai_service import AIService

router = APIRouter()


@router.get(
    "/providers",
    summary="Verfügbare KI-Provider",
    description="Gibt Liste der konfigurierten KI-Provider zurück"
)
async def get_providers():
    """
    Gibt alle verfügbaren KI-Provider zurück.
    
    Der User kann im Frontend zwischen den Providern wählen:
    - OpenAI GPT-4
    - Anthropic Claude
    
    Nur Provider mit konfiguriertem API-Key werden zurückgegeben.
    """
    ai_service = AIService()
    providers = ai_service.get_available_providers()
    
    return {
        "providers": providers,
        "default": ai_service.default_provider
    }


@router.get(
    "/rag/status",
    summary="RAG-Status",
    description="Gibt Status des RAG-Systems (Wissensbasis) zurück"
)
async def get_rag_status():
    """
    Prüft ob RAG (Retrieval Augmented Generation) verfügbar ist.
    
    RAG ermöglicht Analysen mit Kontext aus der Wissensbasis:
    - BGB Mietrecht
    - BGH-Urteile
    - Checklisten für unwirksame Klauseln
    
    Returns:
        - available: Ob RAG aktiv ist
        - total_documents: Anzahl indexierter Dokumente
        - collections: Dokumentanzahl pro Vertragsart
    """
    ai_service = AIService()
    return ai_service.get_rag_status()


@router.post(
    "/document",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dokument analysieren",
    description="Startet eine KI-Analyse für ein hochgeladenes Dokument"
)
async def analyze_document(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Startet eine Vertragsanalyse für ein hochgeladenes Dokument.
    
    Die Analyse läuft im Hintergrund. Status kann über GET /analysis/{id} abgefragt werden.
    
    Limitierungen basierend auf Subscription-Tier.
    """
    # Prüfen ob User noch Analysen durchführen kann
    if not current_user.can_analyze:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Monatliches Limit erreicht ({current_user.monthly_limit} Analysen). Bitte upgraden Sie Ihr Abo."
        )
    
    # Dokument laden
    result = await db.execute(
        select(Document).where(
            Document.id == request.document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dokument nicht gefunden"
        )
    
    # Neue Analyse erstellen
    new_analysis = DocumentAnalysis(
        document_id=document.id,
        status=AnalysisStatus.PENDING
    )
    
    db.add(new_analysis)
    
    # Nutzungszähler erhöhen
    current_user.analyses_this_month += 1
    
    await db.commit()
    await db.refresh(new_analysis)
    
    # Analyse im Hintergrund starten
    background_tasks.add_task(
        run_analysis,
        analysis_id=new_analysis.id,
        document_text=document.extracted_text or "",
        analysis_type=request.analysis_type,
        language=request.language,
        provider=request.provider  # Provider aus Request
    )
    
    return DocumentAnalysisResponse(
        id=new_analysis.id,
        document_id=new_analysis.document_id,
        status=new_analysis.status,
        error_message=None,
        summary=None,
        overall_risk_level=None,
        risk_score=None,
        clauses=None,
        recommendations=None,
        key_terms=None,
        model_used=None,
        tokens_used=None,
        processing_time_ms=None,
        created_at=new_analysis.created_at,
        completed_at=None
    )


@router.post(
    "/text",
    response_model=DocumentAnalysisResponse,
    summary="Text direkt analysieren",
    description="Analysiert einen Text ohne vorherigen Upload"
)
async def analyze_text(
    request: TextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analysiert einen Vertragstext direkt (ohne Datei-Upload).
    
    Ideal für:
    - Copy & Paste von Vertragsklauseln
    - Schnelle Prüfung einzelner Paragraphen
    
    Parameter:
    - use_rag: Wenn True, wird die Wissensbasis (BGB, Urteile) verwendet
    - contract_type: Bestimmt welche Wissensbasis verwendet wird (mietvertrag, etc.)
    """
    # Prüfen ob User noch Analysen durchführen kann
    if not current_user.can_analyze:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Monatliches Limit erreicht. Bitte upgraden Sie Ihr Abo."
        )
    
    # KI-Analyse durchführen
    ai_service = AIService()
    
    try:
        # Entscheiden ob RAG oder normale Analyse
        if request.use_rag and ai_service.is_rag_available(request.contract_type):
            # RAG-Analyse mit Wissensbasis
            analysis_result = await ai_service.analyze_contract_with_rag(
                text=request.text,
                contract_type=request.contract_type,
                provider=request.provider,
                top_k=request.rag_top_k or 8
            )
        else:
            # Normale Analyse ohne Wissensbasis
            analysis_result = await ai_service.analyze_contract(
                text=request.text,
                document_type=request.document_type.value,
                analysis_type=request.analysis_type,
                provider=request.provider
            )
        
        # Nutzungszähler erhöhen
        current_user.analyses_this_month += 1
        await db.commit()
        
        return DocumentAnalysisResponse(
            id=0,  # Keine persistierte Analyse
            document_id=0,
            status=AnalysisStatus.COMPLETED,
            error_message=None,
            summary=analysis_result.get("summary"),
            overall_risk_level=analysis_result.get("overall_risk_level"),
            risk_score=analysis_result.get("risk_score"),
            clauses=analysis_result.get("clauses"),
            missing_clauses=analysis_result.get("missing_clauses"),
            positive_aspects=analysis_result.get("positive_aspects"),
            recommendations=analysis_result.get("recommendations"),
            key_terms=analysis_result.get("key_terms"),
            model_used=analysis_result.get("model_used"),
            tokens_used=analysis_result.get("tokens_used"),
            processing_time_ms=analysis_result.get("processing_time_ms"),
            sources=analysis_result.get("sources"),
            rag_enabled=analysis_result.get("rag_enabled", False),
            documents_used=analysis_result.get("documents_used", 0),
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analyse fehlgeschlagen: {str(e)}"
        )


@router.get(
    "/{analysis_id}",
    response_model=DocumentAnalysisResponse,
    summary="Analyse-Ergebnis abrufen",
    description="Gibt das Ergebnis einer Dokumentenanalyse zurück"
)
async def get_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Gibt das Ergebnis einer spezifischen Analyse zurück.
    
    Kann auch während der Verarbeitung aufgerufen werden um den Status zu prüfen.
    """
    # Analyse mit Dokument-Check laden
    result = await db.execute(
        select(DocumentAnalysis)
        .join(Document)
        .where(
            DocumentAnalysis.id == analysis_id,
            Document.owner_id == current_user.id
        )
    )
    analysis = result.scalar_one_or_none()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analyse nicht gefunden"
        )
    
    return DocumentAnalysisResponse(
        id=analysis.id,
        document_id=analysis.document_id,
        status=analysis.status,
        error_message=analysis.error_message,
        summary=analysis.summary,
        overall_risk_level=analysis.overall_risk_level,
        risk_score=analysis.risk_score,
        clauses=analysis.clauses.get("clauses") if analysis.clauses else None,
        recommendations=analysis.recommendations.get("recommendations") if analysis.recommendations else None,
        key_terms=analysis.key_terms,
        model_used=analysis.model_used,
        tokens_used=analysis.tokens_used,
        processing_time_ms=analysis.processing_time_ms,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at
    )


@router.get(
    "/stats/me",
    response_model=AnalysisStats,
    summary="Analyse-Statistiken",
    description="Gibt Nutzungsstatistiken des aktuellen Benutzers zurück"
)
async def get_analysis_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Gibt Statistiken über die Nutzung des Analyse-Features zurück.
    
    Enthält:
    - Anzahl Dokumente
    - Anzahl Analysen
    - Monatliche Nutzung vs. Limit
    - Verteilung der Risikostufen
    """
    # Dokumente zählen
    doc_result = await db.execute(
        select(Document).where(Document.owner_id == current_user.id)
    )
    documents = doc_result.scalars().all()
    total_documents = len(documents)
    
    # Analysen zählen
    doc_ids = [d.id for d in documents]
    if doc_ids:
        analysis_result = await db.execute(
            select(DocumentAnalysis).where(
                DocumentAnalysis.document_id.in_(doc_ids)
            )
        )
        analyses = analysis_result.scalars().all()
    else:
        analyses = []
    
    # Risiko-Verteilung
    risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for analysis in analyses:
        if analysis.overall_risk_level:
            risk_distribution[analysis.overall_risk_level.value] = \
                risk_distribution.get(analysis.overall_risk_level.value, 0) + 1
    
    return AnalysisStats(
        total_documents=total_documents,
        total_analyses=len(analyses),
        analyses_this_month=current_user.analyses_this_month,
        monthly_limit=current_user.monthly_limit,
        risk_distribution=risk_distribution,
        recent_analyses=[]  # TODO: Letzte 5 Analysen
    )


# ============================================
# Background Task für Analyse
# ============================================
async def run_analysis(
    analysis_id: int,
    document_text: str,
    analysis_type: str,
    language: str,
    provider: str = None
):
    """
    Führt die eigentliche KI-Analyse im Hintergrund durch.
    
    Args:
        provider: "openai" oder "anthropic" (optional)
    """
    from app.core.database import async_session_maker
    
    async with async_session_maker() as db:
        # Analyse laden
        result = await db.execute(
            select(DocumentAnalysis).where(DocumentAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        
        if not analysis:
            return
        
        # Status auf "processing" setzen
        analysis.status = AnalysisStatus.PROCESSING
        await db.commit()
        
        try:
            # KI-Analyse durchführen
            ai_service = AIService()
            start_time = datetime.now(timezone.utc)
            
            result = await ai_service.analyze_contract(
                text=document_text,
                document_type="contract",
                analysis_type=analysis_type,
                provider=provider  # Provider aus Request
            )
            
            end_time = datetime.now(timezone.utc)
            processing_time = int((end_time - start_time).total_seconds() * 1000)
            
            # Ergebnisse speichern
            analysis.status = AnalysisStatus.COMPLETED
            analysis.summary = result.get("summary")
            analysis.overall_risk_level = result.get("overall_risk_level")
            analysis.risk_score = result.get("risk_score")
            analysis.clauses = {"clauses": result.get("clauses", [])}
            analysis.recommendations = {"recommendations": result.get("recommendations", [])}
            analysis.key_terms = result.get("key_terms")
            analysis.model_used = result.get("model_used")
            analysis.tokens_used = result.get("tokens_used")
            analysis.processing_time_ms = processing_time
            analysis.completed_at = end_time
            
        except Exception as e:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
        
        await db.commit()

