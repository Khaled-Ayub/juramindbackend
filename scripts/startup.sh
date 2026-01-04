#!/bin/bash
# ============================================
# JuraMind Backend - Startup Script
# ============================================
# Dieses Script:
# 1. Prüft ob ChromaDB bereits indexiert ist
# 2. Indexiert nur wenn nötig (persistent Volume)
# 3. Startet den uvicorn Server

echo "🚀 JuraMind Backend startet..."

# ChromaDB Verzeichnis (wird von Railway Volume gemountet)
CHROMA_DIR="${CHROMA_PERSIST_DIR:-/app/chroma_db}"
echo "📁 ChromaDB Verzeichnis: $CHROMA_DIR"

# Verzeichnis erstellen falls nicht vorhanden
mkdir -p "$CHROMA_DIR" 2>/dev/null || true

# Prüfen ob bereits indexiert (Marker-Datei)
INDEXED_MARKER="$CHROMA_DIR/.indexed"

if [ -f "$INDEXED_MARKER" ]; then
    echo "✅ RAG-Wissensbasis bereits indexiert (gefunden: $INDEXED_MARKER)"
    echo "   Überspringe Indexierung..."
else
    # RAG-Wissensbasis indexieren (nur wenn API Key vorhanden)
    if [ -n "$OPENAI_API_KEY" ]; then
        echo "📚 Indexiere RAG-Wissensbasis (erstmalig)..."
        if python /app/scripts/index_knowledge_base.py; then
            # Marker-Datei erstellen nach erfolgreicher Indexierung
            echo "$(date -Iseconds)" > "$INDEXED_MARKER"
            echo "✅ Indexierung erfolgreich! Marker erstellt."
        else
            echo "⚠️ Indexierung fehlgeschlagen, starte trotzdem..."
        fi
    else
        echo "⚠️ OPENAI_API_KEY nicht gesetzt - RAG-Indexierung übersprungen"
    fi
fi

# Server starten
echo "🌐 Starte uvicorn auf Port ${PORT:-8080}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

