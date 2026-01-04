#!/usr/bin/env python3
"""
Script zum Indexieren der Wissensbasis in ChromaDB.

Verwendung:
    python scripts/index_knowledge_base.py

Dieses Script:
1. Lädt alle .txt Dateien aus data/mietrecht/ und data/urteile/
2. Erstellt Embeddings mit OpenAI text-embedding-3-small
3. Speichert sie in ChromaDB für RAG-Abfragen

Voraussetzungen:
- OPENAI_API_KEY muss gesetzt sein
- Dateien müssen in data/ vorhanden sein
"""

import sys
import os
from pathlib import Path

# Projekt-Root zum Path hinzufügen
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Umgebungsvariablen laden
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# Prüfen ob API Key vorhanden
if not os.getenv("OPENAI_API_KEY"):
    print("❌ OPENAI_API_KEY nicht gesetzt!")
    print("   Bitte in .env Datei setzen oder als Umgebungsvariable exportieren.")
    sys.exit(1)

from app.rag.indexing_pipeline import index_documents
from app.rag.document_store import get_document_store, get_document_count


def print_header():
    """Gibt Header aus."""
    print("\n" + "=" * 60)
    print("   JuraMind - Wissensbasis Indexierung")
    print("=" * 60 + "\n")


def index_mietrecht():
    """Indexiert Mietrecht-Dokumente."""
    data_dir = PROJECT_ROOT / "data"
    
    # Mietrecht-Dateien sammeln
    mietrecht_files = list((data_dir / "mietrecht").glob("*.txt"))
    urteile_files = list((data_dir / "urteile").glob("*.txt"))
    
    all_files = mietrecht_files + urteile_files
    
    if not all_files:
        print("⚠️  Keine Dateien gefunden in data/mietrecht/ oder data/urteile/")
        return
    
    print(f"📁 Gefundene Dateien:")
    for f in all_files:
        print(f"   - {f.name}")
    
    print(f"\n📊 Indexiere {len(all_files)} Dateien für 'mietvertrag'...")
    
    # Indexieren
    result = index_documents(
        file_paths=[str(f) for f in all_files],
        contract_type="mietvertrag"
    )
    
    print(f"✅ Erfolgreich indexiert!")
    print(f"   - Dateien verarbeitet: {result['files_processed']}")
    print(f"   - Chunks erstellt: {result['documents_written']}")
    
    # Statistik aus Store
    count = get_document_count("mietvertrag")
    print(f"   - Gesamt in ChromaDB: {count} Dokumente")


def show_stats():
    """Zeigt Statistiken aller Collections."""
    print("\n📈 Collection-Statistiken:")
    
    from app.rag.document_store import COLLECTIONS
    
    for contract_type, collection in COLLECTIONS.items():
        try:
            count = get_document_count(contract_type)
            status = "✅" if count > 0 else "⬜"
            print(f"   {status} {collection}: {count} Dokumente")
        except Exception as e:
            print(f"   ❌ {collection}: Fehler - {e}")


def main():
    """Hauptfunktion."""
    print_header()
    
    print("🔧 Konfiguration:")
    print(f"   - Projekt-Root: {PROJECT_ROOT}")
    print(f"   - Data-Verzeichnis: {PROJECT_ROOT / 'data'}")
    print(f"   - ChromaDB: {PROJECT_ROOT / 'chroma_db'}")
    print(f"   - OpenAI API Key: {'✅ Gesetzt' if os.getenv('OPENAI_API_KEY') else '❌ Fehlt'}")
    
    print("\n" + "-" * 60 + "\n")
    
    # Mietrecht indexieren
    try:
        index_mietrecht()
    except Exception as e:
        print(f"❌ Fehler beim Indexieren: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Statistiken anzeigen
    show_stats()
    
    print("\n" + "=" * 60)
    print("✅ Indexierung abgeschlossen!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

