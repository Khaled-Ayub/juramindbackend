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
    
    return {
        "analysis": analysis,
        "sources": sources,
        "provider": llm_provider,
        "model": model_used,
        "documents_used": len(sources)
    }


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """
    Parst die LLM-Antwort und extrahiert das JSON.
    
    Args:
        response: Rohe LLM-Antwort
        
    Returns:
        Geparstes JSON oder Fallback-Dict
    """
    try:
        # Versuche direkt zu parsen
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    try:
        # JSON aus Markdown Code-Block extrahieren
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            return json.loads(json_match.group(1))
    except json.JSONDecodeError:
        pass
    
    try:
        # JSON-Objekt aus Text extrahieren
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Fallback: Rohe Antwort als Summary
    return {
        "summary": response[:500] if len(response) > 500 else response,
        "risk_score": 50,
        "overall_risk_level": "medium",
        "clauses": [],
        "missing_clauses": [],
        "positive_aspects": [],
        "parse_error": "JSON konnte nicht aus LLM-Antwort extrahiert werden"
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

