"""
Query Pipeline für RAG-basierte Vertragsanalyse
Verbindet Retrieval aus ChromaDB mit LLM-Analyse
"""

import os
import json
import re
from typing import Dict, Any, Optional, Literal
from haystack import Pipeline
from haystack.components.embedders import OpenAITextEmbedder
from haystack.components.builders import PromptBuilder
from haystack.components.generators import OpenAIGenerator
from haystack.utils import Secret
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever

from .document_store import get_document_store
from .prompts import get_analysis_prompt
from app.core.config import settings


def create_rag_pipeline(
    contract_type: str = "mietvertrag",
    llm_provider: Literal["openai", "anthropic"] = "openai",
    top_k: int = 8
) -> Pipeline:
    """
    Erstellt die RAG-Query-Pipeline für Vertragsanalyse.
    
    Die Pipeline besteht aus:
    1. OpenAITextEmbedder - Erstellt Vektor aus Vertragstext
    2. ChromaEmbeddingRetriever - Findet relevante Dokumente
    3. PromptBuilder - Baut Prompt mit Vertrag + Kontext
    4. Generator (OpenAI/Anthropic) - Analysiert mit LLM
    
    Args:
        contract_type: Art des Vertrags (bestimmt Collection + Prompt)
        llm_provider: "openai" oder "anthropic"
        top_k: Anzahl der abzurufenden Dokumente (Standard: 8)
        
    Returns:
        Konfigurierte Haystack Pipeline
    """
    # Document Store für diese Vertragsart
    document_store = get_document_store(contract_type)
    
    # Pipeline erstellen
    pipeline = Pipeline()
    
    # 1. Text Embedder für den Vertragstext
    # Secret.from_env_var löst API-Key zur Laufzeit auf (Haystack 2.x API)
    pipeline.add_component(
        "embedder",
        OpenAITextEmbedder(
            model="text-embedding-3-small",
            api_key=Secret.from_env_var("OPENAI_API_KEY")
        )
    )
    
    # 2. Retriever für relevante Dokumente
    pipeline.add_component(
        "retriever",
        ChromaEmbeddingRetriever(
            document_store=document_store,
            top_k=top_k
        )
    )
    
    # 3. Prompt Builder mit vertragsart-spezifischem Template
    prompt_template = get_analysis_prompt(contract_type)
    pipeline.add_component(
        "prompt_builder",
        PromptBuilder(template=prompt_template)
    )
    
    # 4. LLM Generator
    # Secret.from_env_var löst API-Keys zur Laufzeit auf (Haystack 2.x API)
    if llm_provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        # Anthropic Claude über Haystack 2.x native Unterstützung
        from haystack_integrations.components.generators.anthropic import AnthropicGenerator
        generator = AnthropicGenerator(
            model=settings.ANTHROPIC_MODEL,
            api_key=Secret.from_env_var("ANTHROPIC_API_KEY")
        )
    else:
        # OpenAI GPT-4
        generator = OpenAIGenerator(
            model=settings.OPENAI_MODEL,
            api_key=Secret.from_env_var("OPENAI_API_KEY"),
            generation_kwargs={
                "temperature": 0.3,  # Niedrig für konsistente Analyse
                "max_tokens": 4000
            }
        )
    
    pipeline.add_component("generator", generator)
    
    # Pipeline-Verbindungen
    pipeline.connect("embedder.embedding", "retriever.query_embedding")
    pipeline.connect("retriever.documents", "prompt_builder.documents")
    pipeline.connect("prompt_builder", "generator")
    
    return pipeline


def analyze_contract_with_rag(
    contract_text: str,
    contract_type: str = "mietvertrag",
    llm_provider: Literal["openai", "anthropic"] = "openai",
    top_k: int = 8
) -> Dict[str, Any]:
    """
    Analysiert einen Vertrag mit RAG (Retrieval Augmented Generation).
    
    Der Prozess:
    1. Vertragstext wird embedded
    2. Relevante Rechtsgrundlagen werden aus ChromaDB abgerufen
    3. LLM analysiert Vertrag MIT Kontext aus Wissensbasis
    4. Strukturierte Analyse wird zurückgegeben
    
    Args:
        contract_text: Der zu analysierende Vertragstext
        contract_type: Art des Vertrags
        llm_provider: "openai" oder "anthropic"
        top_k: Anzahl der Kontext-Dokumente
        
    Returns:
        Dict mit:
        - analysis: Strukturierte Analyse (geparst oder als Text)
        - sources: Verwendete Quellen aus der Wissensbasis
        - provider: Verwendeter LLM-Provider
        - model: Verwendetes Modell
    """
    # Pipeline erstellen
    pipeline = create_rag_pipeline(contract_type, llm_provider, top_k)
    
    # Pipeline ausführen
    result = pipeline.run({
        "embedder": {"text": contract_text},
        "prompt_builder": {"contract": contract_text}
    })
    
    # LLM-Antwort extrahieren
    llm_response = result.get("generator", {}).get("replies", [""])[0]
    
    # Quellen aus Retriever extrahieren
    retrieved_docs = result.get("retriever", {}).get("documents", [])
    sources = [
        {
            "content": doc.content[:300] + "..." if len(doc.content) > 300 else doc.content,
            "source": doc.meta.get("source", doc.meta.get("file_path", "Unbekannt")),
            "score": getattr(doc, "score", None)
        }
        for doc in retrieved_docs
    ]
    
    # JSON aus Antwort parsen
    analysis = _parse_llm_response(llm_response)
    
    # Modell-Info hinzufügen
    model_used = settings.ANTHROPIC_MODEL if llm_provider == "anthropic" else settings.OPENAI_MODEL
    
    # Flache Struktur zurückgeben (nicht verschachtelt)
    # Frontend erwartet summary, risk_score, etc. direkt
    return {
        **analysis,  # Spread: summary, risk_score, clauses, etc.
        "sources": sources,
        "provider": llm_provider,
        "model_used": model_used,
        "rag_enabled": True,
        "documents_used": len(sources)
    }


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """
    Parst die LLM-Antwort und extrahiert das JSON.
    Sehr robust - versucht mehrere Methoden.
    
    Args:
        response: Rohe LLM-Antwort
        
    Returns:
        Geparstes JSON oder Fallback-Dict
    """
    if not response:
        return _create_fallback_response("Leere Antwort vom LLM")
    
    # Bereinigen: Whitespace trimmen
    cleaned = response.strip()
    
    # Methode 1: Direkt parsen (wenn LLM nur JSON zurückgibt)
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict) and "summary" in result:
            return result
    except json.JSONDecodeError:
        pass
    
    # Methode 2: JSON aus Markdown Code-Block extrahieren
    try:
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned)
        if json_match:
            result = json.loads(json_match.group(1).strip())
            if isinstance(result, dict):
                return result
    except json.JSONDecodeError:
        pass
    
    # Methode 3: Erstes vollständiges JSON-Objekt finden (greedy)
    try:
        # Finde die erste öffnende Klammer
        start_idx = cleaned.find('{')
        if start_idx != -1:
            # Finde die passende schließende Klammer
            depth = 0
            for i, char in enumerate(cleaned[start_idx:], start_idx):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = cleaned[start_idx:i+1]
                        result = json.loads(json_str)
                        if isinstance(result, dict):
                            return result
                        break
    except json.JSONDecodeError:
        pass
    
    # Methode 4: Letzte Chance - suche nach JSON-Struktur
    try:
        json_match = re.search(r'\{[^{}]*"summary"[^{}]*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Fallback: Extrahiere was geht aus dem Text
    return _create_fallback_response(cleaned)


def _create_fallback_response(raw_text: str) -> Dict[str, Any]:
    """
    Erstellt eine Fallback-Response wenn JSON-Parsing fehlschlägt.
    Versucht trotzdem nützliche Infos zu extrahieren.
    """
    # Versuche Summary aus dem Text zu extrahieren
    summary = raw_text
    
    # Wenn es wie JSON aussieht, extrahiere nur den Summary-Wert
    summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', raw_text)
    if summary_match:
        summary = summary_match.group(1)
    else:
        # Ersten sinnvollen Satz als Summary nehmen
        sentences = raw_text.split('.')
        if sentences:
            summary = '. '.join(sentences[:3]) + '.' if len(sentences) > 3 else raw_text
    
    # Kürzen wenn zu lang
    if len(summary) > 500:
        summary = summary[:497] + "..."
    
    return {
        "summary": summary,
        "risk_score": 50,
        "overall_risk_level": "medium",
        "clauses": [],
        "missing_clauses": [],
        "positive_aspects": [],
        "parse_warning": "Analyse konnte nicht vollständig strukturiert werden"
    }


async def analyze_contract_with_rag_async(
    contract_text: str,
    contract_type: str = "mietvertrag",
    llm_provider: Literal["openai", "anthropic"] = "openai",
    top_k: int = 8
) -> Dict[str, Any]:
    """
    Async-Wrapper für RAG-Analyse.
    Für Verwendung in FastAPI-Endpoints.
    """
    # Haystack 2.x Pipelines sind sync, daher in Thread ausführen
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            analyze_contract_with_rag,
            contract_text,
            contract_type,
            llm_provider,
            top_k
        )
    
    return result

