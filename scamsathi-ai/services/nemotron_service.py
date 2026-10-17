"""
NVIDIA Nemotron AI model service integration via Nebius Token Factory.
Uses OpenAI-compatible protocol to query NVIDIA open-source models:
e.g. nvidia/nemotron-4-340b-instruct or nvidia/llama-3.1-nemotron-70b-instruct.
"""

import json
import re
from typing import Dict, Any, Optional
import requests
from config import settings

SYSTEM_CYBERSECURITY_PROMPT = """You are ScamSathi AI — an Intelligent Scam Verification Agent engineered for students and job seekers.
Your mission is to perform rigorous, objective cybersecurity and fraud analysis on submitted opportunity messages (job offers, internship notifications, scholarship claims, lottery announcements, recruitment emails).

CRITICAL DIRECTIVES:
1. Ground every claim against the provided real-world search evidence.
2. Clearly separate verified claims from unverified or suspicious claims.
3. Categorize the risk strictly into one of four categories:
   - "High concern"
   - "Moderate concern"
   - "Low concern"
   - "Insufficient evidence"
4. Explain WHY each warning sign matters to a student or job seeker (e.g., identity theft, financial loss, advance-fee fraud, domain spoofing).
5. Never output arbitrary percentage confidence scores (e.g., do not say "95% scam"). Risk must be qualitative and evidence-based.
6. Provide actionable, practical safety steps (e.g., official recruitment portals, checking domain records, reporting to cybercrime agencies).
7. If the requested language is Telugu ("te"), provide the Telugu translation for the summary, warning signs, and recommendations while keeping source URLs, official domain names, and technical terms intact.

You MUST respond strictly with valid JSON conforming to this schema:
{
  "summary": "Concise summary of the opportunity message and key red flags",
  "summary_telugu": "అవకాశ సందేశం యొక్క సంక్షిప్త సారాంశం మరియు ప్రధాన హెచ్చరికలు",
  "extracted_entities": {
    "company_or_org": "Extracted organization or null",
    "opportunity_title": "Extracted role/scheme title or null",
    "payment_demanded": "Extracted payment or deposit requirement or null",
    "urgency_tactics": ["List of urgency phrases detected"],
    "contact_details": ["Extracted emails, phones, Telegram, WhatsApp"],
    "suspicious_urls": ["Extracted or mentioned links"]
  },
  "risk_assessment": {
    "category": "High concern | Moderate concern | Low concern | Insufficient evidence",
    "rationale": "Clear, grounded justification for this assessment",
    "rationale_telugu": "స్పష్టమైన హేతుబద్ధత వివరణ",
    "limitations": "Explicit disclaimer that this is preliminary investigative analysis, not legal proof of fraud"
  },
  "warning_signs": [
    {
      "indicator": "Specific warning sign",
      "severity": "critical | elevated | medium | informational",
      "explanation": "Why this matters to the user",
      "explanation_telugu": "ఇది ఎందుకు ముఖ్యం"
    }
  ],
  "evidence_comparison": [
    {
      "claim": "Claim made in message",
      "status": "verified | contradicted | unverified",
      "evidence_snippet": "Relevant supporting or contradicting finding from evidence",
      "source_url": "URL of official or research source"
    }
  ],
  "recommendations": [
    {
      "step": "Safe verification action",
      "step_telugu": "సురక్షిత చర్య",
      "priority": "immediate | standard"
    }
  ],
  "model_used": "NVIDIA Nemotron via Nebius Token Factory"
}
"""

class NemotronService:
    """NVIDIA Nemotron client connecting to Nebius Token Factory."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model_id: Optional[str] = None):
        self.api_key = api_key or settings.NEBIUS_API_KEY
        self.base_url = (base_url or settings.NEBIUS_BASE_URL).rstrip("/")
        self.model_id = model_id or settings.NEBIUS_MODEL_ID

    def analyze_opportunity(
        self,
        message: str,
        search_evidence: list,
        target_language: str = "en"
    ) -> Dict[str, Any]:
        """
        Send the extracted claims and retrieved evidence to NVIDIA Nemotron on Nebius.
        Returns validated structured JSON.
        """
        if not self.api_key:
            raise ValueError(
                "NEBIUS_API_KEY is not configured. Please set NEBIUS_API_KEY in your .env or environment to query NVIDIA Nemotron on Nebius Token Factory."
            )

        # Build evidence context
        evidence_text = ""
        if search_evidence:
            for idx, item in enumerate(search_evidence, 1):
                official_tag = "[OFFICIAL SOURCE]" if item.get("is_official") else "[WEB SEARCH]"
                evidence_text += f"\nSource {idx} {official_tag}: {item.get('title')}\nURL: {item.get('url')}\nExcerpt: {item.get('content')}\n"
        else:
            evidence_text = "No public search evidence retrieved or search service unavailable."

        user_content = f"""USER SUBMITTED MESSAGE TO INVESTIGATE:
\"\"\"
{message.strip()}
\"\"\"

RETRIEVED WEB EVIDENCE:
{evidence_text}

TARGET LANGUAGE: {target_language} (Ensure both English and Telugu fields are populated accurately).

Analyze this opportunity now. Output ONLY valid JSON."""

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_CYBERSECURITY_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": settings.MODEL_TEMPERATURE,
            "max_tokens": settings.MAX_TOKENS,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=settings.REQUEST_TIMEOUT_SECONDS
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Nebius Token Factory API returned status {response.status_code}: {response.text[:300]}"
            )

        resp_data = response.json()
        choices = resp_data.get("choices", [])
        if not choices:
            raise ValueError("Nebius API returned empty choices array.")

        raw_content = choices[0].get("message", {}).get("content", "")
        if not raw_content:
            raise ValueError("Empty response content from Nemotron model.")

        # Clean markdown codeblocks if model wrapped response in ```json ... ```
        cleaned_json = re.sub(r"^```(?:json)?\s*", "", raw_content.strip())
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json.strip())

        parsed = json.loads(cleaned_json)
        return parsed
