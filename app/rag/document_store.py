"""
Document Store Setup für RAG
Verwendet ChromaDB als Vector Store mit separaten Collections pro Vertragsart
"""

import os
from pathlib import Path
from haystack_integrations.document_stores.chroma import ChromaDocumentStore

# Pfad zum persistenten ChromaDB-Verzeichnis
# Wird relativ zum Backend-Root erstellt
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR", 
    str(Path(__file__).parent.parent.parent / "chroma_db")
)

# Collections pro Vertragsart für bessere Trennung und Relevanz
# Jede Vertragsart hat ihre eigene Wissensbasis
COLLECTIONS = {
    "mietvertrag": "mietrecht",      # BGB Mietrecht, BGH-Urteile, Checklisten
    "arbeitsvertrag": "arbeitsrecht", # Arbeitsrecht (TODO: Dateien hinzufügen)
    "kaufvertrag": "kaufrecht",       # Kaufrecht (TODO: Dateien hinzufügen)
    "kfz": "kfz_recht",               # KFZ-Recht (TODO: Dateien hinzufügen)
    "gewerbe": "gewerberecht",        # Gewerberecht (TODO: Dateien hinzufügen)
    "sonstige": "allgemein",          # Allgemeines Vertragsrecht
}


def get_document_store(contract_type: str = "mietvertrag") -> ChromaDocumentStore:
    """
    Gibt den Document Store für eine bestimmte Vertragsart zurück.
    
    Args:
        contract_type: Art des Vertrags (mietvertrag, arbeitsvertrag, etc.)
        
    Returns:
        ChromaDocumentStore für die entsprechende Collection
        
    Beispiel:
        >>> store = get_document_store("mietvertrag")
        >>> # Store enthält nur mietrechtliche Dokumente
    """
    # Collection-Name aus Mapping holen, Fallback auf "allgemein"
    collection_name = COLLECTIONS.get(contract_type, "allgemein")
    
    # ChromaDB Document Store erstellen/laden
    # persist_path sorgt für Persistenz über Neustarts hinweg
    return ChromaDocumentStore(
        persist_path=CHROMA_PERSIST_DIR,
        collection_name=collection_name
    )


def get_all_document_stores() -> dict:
    """
    Gibt alle Document Stores für alle Vertragsarten zurück.
    Nützlich für Admin-Zwecke oder Batch-Operationen.
    
    Returns:
        Dict mit Vertragsart -> DocumentStore Mapping
    """
    return {
        contract_type: get_document_store(contract_type)
        for contract_type in COLLECTIONS.keys()
    }


def get_document_count(contract_type: str = "mietvertrag") -> int:
    """
    Gibt die Anzahl der indexierten Dokumente für eine Vertragsart zurück.
    
    Args:
        contract_type: Art des Vertrags
        
    Returns:
        Anzahl der Dokumente in der Collection
    """
    store = get_document_store(contract_type)
    return store.count_documents()

