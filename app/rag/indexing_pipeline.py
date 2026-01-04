"""
Indexing Pipeline für RAG
Verarbeitet Textdateien und speichert sie als Vektoren in ChromaDB
"""

import os
from pathlib import Path
from typing import List, Optional
from haystack import Pipeline
from haystack.components.converters import TextFileToDocument
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.embedders import OpenAIDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack.dataclasses import Document
from haystack.utils import Secret

from .document_store import get_document_store


def create_indexing_pipeline(contract_type: str = "mietvertrag") -> Pipeline:
    """
    Erstellt die Indexing-Pipeline für eine bestimmte Vertragsart.
    
    Die Pipeline besteht aus:
    1. TextFileToDocument - Konvertiert .txt Dateien zu Haystack Documents
    2. DocumentSplitter - Teilt Dokumente in Chunks (5 Sätze, 2 Überlappung)
    3. OpenAIDocumentEmbedder - Erstellt Vektoren mit text-embedding-3-small
    4. DocumentWriter - Schreibt in ChromaDB
    
    Args:
        contract_type: Art des Vertrags (bestimmt die Collection)
        
    Returns:
        Konfigurierte Haystack Pipeline
    """
    # Document Store für diese Vertragsart
    document_store = get_document_store(contract_type)
    
    # Pipeline erstellen
    pipeline = Pipeline()
    
    # 1. Text-Datei zu Document konvertieren
    pipeline.add_component(
        "converter", 
        TextFileToDocument(encoding="utf-8")
    )
    
    # 2. Dokumente in Chunks aufteilen
    # 5 Sätze pro Chunk mit 2 Sätzen Überlappung
    # Optimiert für rechtliche Texte (Paragraphen, Urteile)
    pipeline.add_component(
        "splitter", 
        DocumentSplitter(
            split_by="sentence",
            split_length=5,      # 5 Sätze pro Chunk
            split_overlap=2      # 2 Sätze Überlappung für Kontext
        )
    )
    
    # 3. Embeddings mit OpenAI erstellen
    # text-embedding-3-small ist kostengünstig und ausreichend präzise
    # Secret.from_env_var löst den API-Key zur Laufzeit auf (Haystack 2.x API)
    pipeline.add_component(
        "embedder", 
        OpenAIDocumentEmbedder(
            model="text-embedding-3-small",
            api_key=Secret.from_env_var("OPENAI_API_KEY")
        )
    )
    
    # 4. In Document Store schreiben
    pipeline.add_component(
        "writer", 
        DocumentWriter(
            document_store=document_store,
            policy="upsert"  # Aktualisiert existierende Dokumente
        )
    )
    
    # Pipeline-Verbindungen
    pipeline.connect("converter", "splitter")
    pipeline.connect("splitter", "embedder")
    pipeline.connect("embedder", "writer")
    
    return pipeline


def index_documents(
    file_paths: List[str], 
    contract_type: str = "mietvertrag"
) -> dict:
    """
    Indexiert eine Liste von Textdateien für eine Vertragsart.
    
    Args:
        file_paths: Liste von Pfaden zu .txt Dateien
        contract_type: Art des Vertrags (mietvertrag, arbeitsvertrag, etc.)
        
    Returns:
        Dict mit Indexierungs-Statistiken
        
    Beispiel:
        >>> files = ["data/mietrecht/bgb_mietrecht.txt", "data/urteile/bgh_mietrecht.txt"]
        >>> result = index_documents(files, "mietvertrag")
        >>> print(f"Indexiert: {result['documents_written']} Chunks")
    """
    # Pipeline erstellen
    pipeline = create_indexing_pipeline(contract_type)
    
    # Pipeline ausführen
    result = pipeline.run({
        "converter": {"sources": file_paths}
    })
    
    # Statistiken zurückgeben
    return {
        "contract_type": contract_type,
        "files_processed": len(file_paths),
        "documents_written": result.get("writer", {}).get("documents_written", 0),
        "files": [str(Path(f).name) for f in file_paths]
    }


def index_directory(
    directory: str, 
    contract_type: str = "mietvertrag",
    pattern: str = "*.txt"
) -> dict:
    """
    Indexiert alle Dateien in einem Verzeichnis.
    
    Args:
        directory: Pfad zum Verzeichnis
        contract_type: Art des Vertrags
        pattern: Glob-Pattern für Dateien (Standard: *.txt)
        
    Returns:
        Dict mit Indexierungs-Statistiken
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        raise FileNotFoundError(f"Verzeichnis nicht gefunden: {directory}")
    
    # Alle passenden Dateien finden
    files = list(dir_path.glob(pattern))
    
    if not files:
        return {
            "contract_type": contract_type,
            "files_processed": 0,
            "documents_written": 0,
            "message": f"Keine {pattern} Dateien in {directory} gefunden"
        }
    
    # Indexieren
    return index_documents([str(f) for f in files], contract_type)


def clear_index(contract_type: str = "mietvertrag") -> dict:
    """
    Löscht alle Dokumente aus dem Index einer Vertragsart.
    Nützlich für Re-Indexierung.
    
    Args:
        contract_type: Art des Vertrags
        
    Returns:
        Dict mit Lösch-Statistiken
    """
    store = get_document_store(contract_type)
    count_before = store.count_documents()
    
    # Alle Dokumente löschen
    store.delete_documents(
        document_ids=store.filter_documents()  # Alle IDs
    )
    
    return {
        "contract_type": contract_type,
        "documents_deleted": count_before
    }

