# ============================================
# JuraMind Backend - Dockerfile
# Multi-Stage Build für optimierte Image-Größe
# ============================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# Stage 2: Production
FROM python:3.11-slim

WORKDIR /app

# Non-root User für Sicherheit mit Home-Verzeichnis
# Home-Verzeichnis wird benötigt für Haystack/Posthog Telemetrie-Config
RUN addgroup --system --gid 1001 juramind && \
    adduser --system --uid 1001 --gid 1001 --home /home/juramind juramind && \
    mkdir -p /home/juramind && \
    chown -R juramind:juramind /home/juramind

# Haystack Telemetrie deaktivieren (vermeidet Permission-Probleme)
ENV HAYSTACK_TELEMETRY_ENABLED=false
ENV DO_NOT_TRACK=1

# Dependencies aus Builder kopieren
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Anwendungscode kopieren
COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini .

# RAG Wissensbasis und Scripts kopieren
COPY ./data ./data
COPY ./scripts ./scripts

# Startup-Script ausführbar machen
RUN chmod +x /app/scripts/startup.sh

# ChromaDB Verzeichnis erstellen (für RAG-Daten)
RUN mkdir -p /app/chroma_db

# Berechtigungen setzen
RUN chown -R juramind:juramind /app

# Zu Non-root User wechseln
USER juramind

# Port freigeben (Railway nutzt PORT env variable)
EXPOSE 8080

# Health Check (nutzt PORT env variable)
# Längerer start-period für RAG-Indexierung
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD python -c "import httpx; import os; httpx.get(f'http://localhost:{os.getenv(\"PORT\", 8080)}/health')" || exit 1

# Startup-Script: Indexiert RAG, dann startet uvicorn
CMD ["/app/scripts/startup.sh"]

