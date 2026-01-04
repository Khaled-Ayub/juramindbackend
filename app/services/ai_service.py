"""
KI-Service für JuraMind
OpenAI/GPT-4 Integration für Vertragsanalyse
"""

from openai import AsyncOpenAI
from typing import Dict, Any, List, Optional
import json
import tiktoken

from app.core.config import settings


class AIService:
    """
    Service-Klasse für KI-gestützte Vertragsanalyse
    
    Verwendet OpenAI GPT-4 für:
    - Klauselerkennung
    - Risikoanalyse
    - Empfehlungen
    """
    
    def __init__(self):
        """
        Initialisiert den OpenAI-Client
        """
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.encoding = tiktoken.encoding_for_model("gpt-4")
    
    def count_tokens(self, text: str) -> int:
        """
        Zählt die Tokens in einem Text
        """
        return len(self.encoding.encode(text))
    
    async def analyze_contract(
        self,
        text: str,
        document_type: str = "contract",
        analysis_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Analysiert einen Vertragstext mit GPT-4
        
        Args:
            text: Der zu analysierende Vertragstext
            document_type: Art des Dokuments
            analysis_type: "full", "quick", "clauses_only"
        
        Returns:
            Strukturiertes Analyse-Ergebnis
        """
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
            # API-Call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Niedrige Temperatur für konsistente Ergebnisse
                response_format={"type": "json_object"},
                max_tokens=4000
            )
            
            # Response parsen
            content = response.choices[0].message.content
            result = json.loads(content)
            
            # Metadaten hinzufügen
            result["model_used"] = self.model
            result["tokens_used"] = response.usage.total_tokens
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON-Parsing fehlgeschlagen: {str(e)}",
                "summary": "Analyse konnte nicht durchgeführt werden",
                "overall_risk_level": None,
                "risk_score": None,
                "clauses": [],
                "recommendations": [],
                "key_terms": {}
            }
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
    
    async def analyze_clause(
        self,
        clause_text: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analysiert eine einzelne Vertragsklausel
        
        Args:
            clause_text: Text der Klausel
            context: Optionaler Kontext (z.B. Vertragsart)
        
        Returns:
            Klausel-Analyse
        """
        prompt = f"""Analysiere diese Vertragsklausel nach deutschem Recht:

{clause_text}

{"Kontext: " + context if context else ""}

Bewerte:
1. Risikostufe (low/medium/high/critical)
2. Rechtliche Einschätzung
3. Relevante Paragraphen
4. Empfehlung

Antworte als JSON."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def suggest_improvement(
        self,
        clause_text: str,
        issue: str
    ) -> str:
        """
        Schlägt eine verbesserte Version einer Klausel vor
        
        Args:
            clause_text: Ursprüngliche Klausel
            issue: Identifiziertes Problem
        
        Returns:
            Verbesserter Klauseltext
        """
        prompt = f"""Als Vertragsexperte, verbessere diese Klausel:

Original:
{clause_text}

Problem:
{issue}

Schlage eine rechtssichere Alternative vor, die das Problem behebt.
Erkläre kurz die Änderungen."""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        
        return response.choices[0].message.content
    
    async def legal_search(
        self,
        query: str,
        area_of_law: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Beantwortet juristische Fragen
        
        Args:
            query: Rechtliche Fragestellung
            area_of_law: Rechtsgebiet (optional)
        
        Returns:
            Strukturierte Antwort mit Quellen
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
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)

