"""
KI-Service für JuraMind
Unterstützt OpenAI GPT-4 und Anthropic Claude für Vertragsanalyse
Mit optionalem RAG (Retrieval Augmented Generation)
"""

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from typing import Dict, Any, List, Optional, Literal
import json

from app.core.config import settings

# RAG-Import (optional, nur wenn aktiviert)
try:
    from app.rag.query_pipeline import analyze_contract_with_rag_async
    from app.rag.document_store import get_document_count
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


class AIService:
    """
    Service-Klasse für KI-gestützte Vertragsanalyse
    
    Unterstützt:
    - OpenAI GPT-4
    - Anthropic Claude
    
    Der Provider kann pro Request gewählt werden!
    
    Features:
    - Klauselerkennung
    - Risikoanalyse
    - Empfehlungen
    """
    
    def __init__(self, provider: str = None):
        """
        Initialisiert beide KI-Clients
        
        Args:
            provider: "openai" oder "anthropic" (optional, kann pro Request überschrieben werden)
        """
        # Standard-Provider aus Config, kann überschrieben werden
        self.default_provider = provider or settings.AI_PROVIDER
        
        # Beide Clients initialisieren (falls Keys vorhanden)
        self.openai_client = None
        self.anthropic_client = None
        
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    def _get_model(self, provider: str) -> str:
        """Gibt das Modell für den Provider zurück"""
        if provider == "openai":
            return settings.OPENAI_MODEL
        return settings.ANTHROPIC_MODEL
    
    def get_available_providers(self) -> list:
        """Gibt Liste der verfügbaren Provider zurück"""
        available = []
        if self.openai_client:
            available.append({
                "id": "openai",
                "name": "OpenAI GPT-4",
                "model": settings.OPENAI_MODEL
            })
        if self.anthropic_client:
            available.append({
                "id": "anthropic", 
                "name": "Anthropic Claude",
                "model": settings.ANTHROPIC_MODEL
            })
        return available
    
    def is_rag_available(self, contract_type: str = "mietvertrag") -> bool:
        """
        Prüft ob RAG für eine Vertragsart verfügbar ist.
        RAG ist verfügbar wenn:
        1. RAG-Module importiert werden konnten
        2. Mindestens ein Dokument indexiert ist
        """
        if not RAG_AVAILABLE:
            return False
        try:
            count = get_document_count(contract_type)
            return count > 0
        except Exception:
            return False
    
    def get_rag_status(self) -> dict:
        """Gibt Status des RAG-Systems zurück"""
        if not RAG_AVAILABLE:
            return {
                "available": False,
                "message": "RAG-Module nicht installiert"
            }
        
        try:
            from app.rag.document_store import COLLECTIONS
            collections = {}
            for contract_type in COLLECTIONS.keys():
                count = get_document_count(contract_type)
                collections[contract_type] = count
            
            total = sum(collections.values())
            return {
                "available": total > 0,
                "total_documents": total,
                "collections": collections,
                "message": f"{total} Dokumente indexiert" if total > 0 else "Keine Dokumente indexiert"
            }
        except Exception as e:
            return {
                "available": False,
                "message": f"Fehler: {str(e)}"
            }
    
    async def analyze_contract_with_rag(
        self,
        text: str,
        contract_type: str = "mietvertrag",
        provider: Literal["openai", "anthropic"] = None,
        top_k: int = 8
    ) -> Dict[str, Any]:
        """
        Analysiert einen Vertrag MIT RAG (Wissensbasis).
        
        Der Vertragstext wird zusammen mit relevanten Rechtsgrundlagen
        aus der Wissensbasis an das LLM gesendet.
        
        Args:
            text: Der zu analysierende Vertragstext
            contract_type: Art des Vertrags (mietvertrag, arbeitsvertrag, etc.)
            provider: "openai" oder "anthropic"
            top_k: Anzahl der abzurufenden Kontext-Dokumente
            
        Returns:
            Strukturiertes Analyse-Ergebnis mit Quellen
        """
        if not RAG_AVAILABLE:
            raise ValueError("RAG ist nicht verfügbar. Bitte RAG-Dependencies installieren.")
        
        active_provider = provider or self.default_provider
        
        # RAG-Analyse durchführen
        result = await analyze_contract_with_rag_async(
            contract_text=text,
            contract_type=contract_type,
            llm_provider=active_provider,
            top_k=top_k
        )
        
        # Ergebnis formatieren
        analysis = result.get("analysis", {})
        
        return {
            "summary": analysis.get("summary", ""),
            "overall_risk_level": analysis.get("overall_risk_level", "medium"),
            "risk_score": analysis.get("risk_score", 50),
            "clauses": analysis.get("clauses", []),
            "missing_clauses": analysis.get("missing_clauses", []),
            "positive_aspects": analysis.get("positive_aspects", []),
            "recommendations": analysis.get("general_recommendations", []),
            "sources": result.get("sources", []),
            "model_used": result.get("model"),
            "provider": result.get("provider"),
            "rag_enabled": True,
            "documents_used": result.get("documents_used", 0)
        }
    
    async def analyze_contract(
        self,
        text: str,
        document_type: str = "contract",
        analysis_type: str = "full",
        provider: str = None
    ) -> Dict[str, Any]:
        """
        Analysiert einen Vertragstext mit dem gewählten KI-Provider
        
        Args:
            text: Der zu analysierende Vertragstext
            document_type: Art des Dokuments
            analysis_type: "full", "quick", "clauses_only"
            provider: "openai" oder "anthropic" (überschreibt Default)
        
        Returns:
            Strukturiertes Analyse-Ergebnis
        """
        # Provider für diesen Request bestimmen
        active_provider = provider or self.default_provider
        
        # Prüfen ob Provider verfügbar
        if active_provider == "openai" and not self.openai_client:
            raise ValueError("OpenAI ist nicht konfiguriert (API Key fehlt)")
        if active_provider == "anthropic" and not self.anthropic_client:
            raise ValueError("Anthropic ist nicht konfiguriert (API Key fehlt)")
        # System-Prompt für juristische Analyse
        system_prompt = """Du bist ein erfahrener deutscher Rechtsanwalt und Vertragsexperte.
Deine Aufgabe ist es, Verträge zu analysieren und strukturierte Bewertungen abzugeben.

Analysiere den Vertrag nach folgenden Kriterien:
1. Identifiziere alle wichtigen Klauseln
2. Bewerte das Risiko jeder Klausel (low, medium, high, critical)
3. Prüfe auf rechtliche Probleme nach deutschem Recht
4. Gib konkrete Handlungsempfehlungen

Antworte IMMER im folgenden JSON-Format:
{
    "summary": "Kurze Zusammenfassung des Vertrags (2-3 Sätze)",
    "overall_risk_level": "low|medium|high|critical",
    "risk_score": 0-100,
    "clauses": [
        {
            "id": 1,
            "title": "Klauseltitel (z.B. § 3 Haftung)",
            "content": "Relevanter Text der Klausel",
            "risk_level": "low|medium|high|critical",
            "ai_comment": "Deine juristische Einschätzung",
            "legal_references": ["Relevante Paragraphen, z.B. § 307 BGB"]
        }
    ],
    "recommendations": [
        {
            "priority": "high|medium|low",
            "clause_id": 1,
            "suggestion": "Konkrete Empfehlung"
        }
    ],
    "key_terms": {
        "parties": ["Vertragsparteien"],
        "dates": {"start": "Datum", "end": "Datum"},
        "amounts": [{"value": 1000, "currency": "EUR", "context": "Beschreibung"}]
    }
}"""
        
        # User-Prompt mit dem Vertragstext
        user_prompt = f"""Analysiere den folgenden {document_type}:

---
{text}
---

Führe eine {analysis_type} Analyse durch und antworte im vorgegebenen JSON-Format."""
        
        try:
            if active_provider == "openai":
                return await self._analyze_with_openai(system_prompt, user_prompt)
            else:
                return await self._analyze_with_claude(system_prompt, user_prompt)
                
        except Exception as e:
            return {
                "error": str(e),
                "summary": "Analyse fehlgeschlagen",
                "overall_risk_level": None,
                "risk_score": None,
                "clauses": [],
                "recommendations": [],
                "key_terms": {}
            }
    
    async def _analyze_with_openai(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """
        Führt Analyse mit OpenAI GPT-4 durch
        """
        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        result["model_used"] = self.model
        result["tokens_used"] = response.usage.total_tokens
        result["provider"] = "openai"
        
        return result
    
    async def _analyze_with_claude(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """
        Führt Analyse mit Anthropic Claude durch
        """
        response = await self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Claude Response parsen
        content = response.content[0].text
        
        # JSON aus Response extrahieren
        try:
            # Versuche direkt zu parsen
            result = json.loads(content)
        except json.JSONDecodeError:
            # Falls Claude zusätzlichen Text enthält, extrahiere JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("Konnte JSON nicht aus Claude-Response extrahieren")
        
        result["model_used"] = self.model
        result["tokens_used"] = response.usage.input_tokens + response.usage.output_tokens
        result["provider"] = "anthropic"
        
        return result
    
    async def analyze_clause(
        self,
        clause_text: str,
        context: Optional[str] = None,
        provider: str = None
    ) -> Dict[str, Any]:
        """
        Analysiert eine einzelne Vertragsklausel
        
        Args:
            clause_text: Text der Klausel
            context: Optionaler Kontext
            provider: "openai" oder "anthropic"
        """
        active_provider = provider or self.default_provider
        model = self._get_model(active_provider)
        
        prompt = f"""Analysiere diese Vertragsklausel nach deutschem Recht:

{clause_text}

{"Kontext: " + context if context else ""}

Bewerte:
1. Risikostufe (low/medium/high/critical)
2. Rechtliche Einschätzung
3. Relevante Paragraphen
4. Empfehlung

Antworte als JSON."""
        
        if active_provider == "openai":
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        else:
            response = await self.anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(content)
    
    async def suggest_improvement(
        self,
        clause_text: str,
        issue: str
    ) -> str:
        """
        Schlägt eine verbesserte Version einer Klausel vor
        """
        prompt = f"""Als Vertragsexperte, verbessere diese Klausel:

Original:
{clause_text}

Problem:
{issue}

Schlage eine rechtssichere Alternative vor, die das Problem behebt.
Erkläre kurz die Änderungen."""
        
        if self.provider == "openai":
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return response.choices[0].message.content
        else:
            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
    
    async def legal_search(
        self,
        query: str,
        area_of_law: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Beantwortet juristische Fragen
        """
        system_prompt = """Du bist ein deutscher Rechtsexperte.
Beantworte juristische Fragen präzise und mit Quellenangaben.
Verweise auf relevante Gesetze, Paragraphen und Rechtsprechung.
Weise immer darauf hin, dass dies keine Rechtsberatung ersetzt."""
        
        user_prompt = f"""Frage: {query}
{"Rechtsgebiet: " + area_of_law if area_of_law else ""}

Antworte als JSON mit:
- answer: Deine Antwort
- legal_basis: Relevante Rechtsgrundlagen
- case_law: Relevante Rechtsprechung (wenn bekannt)
- disclaimer: Hinweis zur Rechtsnatur der Antwort"""
        
        if self.provider == "openai":
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        else:
            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=3000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            content = response.content[0].text
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(content)
