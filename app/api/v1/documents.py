"""
Document API Endpoints
Upload, Download, Verwaltung
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid
import os

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.document import Document, DocumentType
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentListResponse
)

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dokument hochladen",
    description="Lädt ein Dokument hoch (PDF oder DOCX)"
)
async def upload_document(
    file: UploadFile = File(..., description="PDF oder DOCX Datei"),
    title: Optional[str] = None,
    description: Optional[str] = None,
    document_type: DocumentType = DocumentType.CONTRACT,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lädt ein Dokument hoch für spätere Analyse.
    
    Unterstützte Formate:
    - PDF (.pdf)
    - Word (.docx)
    
    Max. Dateigröße: 10 MB
    """
    # Dateityp prüfen
    if file.content_type not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dateityp nicht unterstützt. Erlaubt: PDF, DOCX"
        )
    
    # Dateigröße prüfen
    content = await file.read()
    file_size = len(content)
    
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Datei zu groß. Maximum: {settings.MAX_UPLOAD_SIZE_MB} MB"
        )
    
    # Eindeutigen Dateinamen generieren
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    # Text extrahieren (TODO: Implementierung in Service)
    extracted_text = None
    page_count = None
    
    # Dokument in DB speichern
    new_document = Document(
        owner_id=current_user.id,
        filename=unique_filename,
        original_filename=file.filename,
        file_type=file.content_type,
        file_size=file_size,
        document_type=document_type,
        title=title or file.filename,
        description=description,
        extracted_text=extracted_text,
        page_count=page_count
    )
    
    db.add(new_document)
    await db.commit()
    await db.refresh(new_document)
    
    # TODO: Datei in Cloud-Storage speichern (S3, GCS, etc.)
    # Für lokale Entwicklung: Temporär im Speicher
    
    return DocumentResponse(
        id=new_document.id,
        filename=new_document.filename,
        original_filename=new_document.original_filename,
        file_type=new_document.file_type,
        file_size=new_document.file_size,
        document_type=new_document.document_type,
        title=new_document.title,
        description=new_document.description,
        page_count=new_document.page_count,
        created_at=new_document.created_at,
        updated_at=new_document.updated_at
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Dokumente auflisten",
    description="Gibt alle Dokumente des Benutzers zurück"
)
async def list_documents(
    page: int = Query(1, ge=1, description="Seitennummer"),
    page_size: int = Query(20, ge=1, le=100, description="Einträge pro Seite"),
    document_type: Optional[DocumentType] = Query(None, description="Nach Typ filtern"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Listet alle Dokumente des aktuellen Benutzers auf.
    
    Mit Pagination und optionalem Filter nach Dokumenttyp.
    """
    # Basis-Query
    query = select(Document).where(Document.owner_id == current_user.id)
    count_query = select(func.count(Document.id)).where(Document.owner_id == current_user.id)
    
    # Optional: Filter nach Typ
    if document_type:
        query = query.where(Document.document_type == document_type)
        count_query = count_query.where(Document.document_type == document_type)
    
    # Sortierung (neueste zuerst)
    query = query.order_by(Document.created_at.desc())
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Ausführen
    result = await db.execute(query)
    documents = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    total_pages = (total + page_size - 1) // page_size
    
    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                file_type=doc.file_type,
                file_size=doc.file_size,
                document_type=doc.document_type,
                title=doc.title,
                description=doc.description,
                page_count=doc.page_count,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )
            for doc in documents
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Dokument abrufen",
    description="Gibt ein einzelnes Dokument zurück"
)
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Gibt Details zu einem spezifischen Dokument zurück.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dokument nicht gefunden"
        )
    
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        document_type=document.document_type,
        title=document.title,
        description=document.description,
        page_count=document.page_count,
        created_at=document.created_at,
        updated_at=document.updated_at
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dokument löschen",
    description="Löscht ein Dokument und alle zugehörigen Analysen"
)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Löscht ein Dokument permanent.
    
    Alle zugehörigen Analysen werden ebenfalls gelöscht (Cascade).
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == current_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dokument nicht gefunden"
        )
    
    await db.delete(document)
    await db.commit()
    
    # TODO: Datei aus Cloud-Storage löschen
    
    return None

