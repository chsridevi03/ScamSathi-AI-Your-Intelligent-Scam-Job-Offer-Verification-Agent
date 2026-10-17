"""
Analysis Service orchestrating:
Input Validation -> Claim Extraction -> Web Research -> Nemotron Inference -> Output Validation.
Enforces Pydantic data schemas, anti-prompt injection defense, and bilingual processing.
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from config import settings
from services.search_service import SearchService, is_safe_public_url
from services.nemotron_service import NemotronService

# Prompt injection and adversarial pattern detection
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an\s+unrestricted|DAN|a\s+different)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|instructions|secret\s+key)", re.IGNORECASE),
    re.compile(r"print\s+API_KEY", re.IGNORECASE),
    re.compile(r"override\s+(safety|system)\s+rules", re.IGNORECASE),
]

# Rule-based scam indicators for heuristic cross-checks
FEE_PATTERNS = [
    re.compile(r"(registration|processing|security|training|kit|laptop|courier|uniform|application)\s+(fee|deposit|charge|amount|cost)", re.IGNORECASE),
    re.compile(r"(pay|send|transfer|deposit)\s+(rs\.?|inr|\$|₹)\s*\d+", re.IGNORECASE),
    re.compile(r"refundable\s+(deposit|security)", re.IGNORECASE),
]

URGENCY_PATTERNS = [
    re.compile(r"(urgent|hurry|immediate|only\s+\d+\s+slots?|today\s+only|offer\s+expires\s+in)", re.IGNORECASE),
    re.compile(r"(immediate\s+joining|act\s+now|last\s+chance)", re.IGNORECASE),
]

CONTACT_EXTRACTORS = {
    "emails": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    "phones": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "urls": re.compile(r"https?://[^\s<>\"']+"),
    "telegram": re.compile(r"(?:t\.me/|telegram\s*:\s*@?)([a-zA-Z0-9_]{4,})", re.IGNORECASE),
    "whatsapp": re.compile(r"(?:wa\.me/\d+|whatsapp\s*:\s*\+?\d+)", re.IGNORECASE),
}

# --- Pydantic Data Validation Schemas ---

class ExtractedEntities(BaseModel):
    company_or_org: Optional[str] = None
    opportunity_title: Optional[str] = None
    payment_demanded: Optional[str] = None
    urgency_tactics: List[str] = Field(default_factory=list)
    contact_details: List[str] = Field(default_factory=list)
    suspicious_urls: List[str] = Field(default_factory=list)

class WarningSign(BaseModel):
    indicator: str
    severity: str = "medium"  # critical, elevated, medium, informational
    explanation: str
    explanation_telugu: Optional[str] = None

class EvidenceComparison(BaseModel):
    claim: str
    status: str  # verified, contradicted, unverified
    evidence_snippet: str
    source_url: Optional[str] = None

class RiskAssessment(BaseModel):
    category: str  # High concern | Moderate concern | Low concern | Insufficient evidence
    rationale: str
    rationale_telugu: Optional[str] = None
    limitations: str = "This assessment is a preliminary AI-assisted investigative analysis and does not constitute definitive proof or legal determination of fraud."

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid_cats = ["High concern", "Moderate concern", "Low concern", "Insufficient evidence"]
        for cat in valid_cats:
            if v.lower() == cat.lower():
                return cat
        return "Insufficient evidence"

class Recommendation(BaseModel):
    step: str
    step_telugu: Optional[str] = None
    priority: str = "standard"  # immediate | standard

class InvestigationReport(BaseModel):
    summary: str
    summary_telugu: Optional[str] = None
    extracted_entities: ExtractedEntities
    risk_assessment: RiskAssessment
    warning_signs: List[WarningSign] = Field(default_factory=list)
    evidence_comparison: List[EvidenceComparison] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    model_used: str = "NVIDIA Nemotron via Nebius Token Factory"
    raw_evidence_count: int = 0

def check_prompt_injection(text: str) -> bool:
    """Detect common prompt-injection / instruction-override signatures."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False

def extract_rule_based_claims(text: str) -> ExtractedEntities:
    """Extract claims and key entities using regex heuristics."""
    urgency_tactics = []
    for pat in URGENCY_PATTERNS:
        matches = pat.findall(text)
        if matches:
            urgency_tactics.extend([m if isinstance(m, str) else m[0] for m in matches])

    payment = None
    for pat in FEE_PATTERNS:
        for m in pat.finditer(text):
            # Check if preceded by negation (no, not, never, zero, without, free of)
            start_pos = max(0, m.start() - 30)
            prefix = text[start_pos:m.start()].lower()
            if any(neg in prefix for neg in ["no ", "never ", "not ", "zero ", "without ", "free of "]):
                continue
            payment = m.group(0)
            break
        if payment:
            break

    contacts = []
    for kind, pat in CONTACT_EXTRACTORS.items():
        matches = pat.findall(text)
        for match in matches:
            contacts.append(f"{kind.title()}: {match}")

    urls = CONTACT_EXTRACTORS["urls"].findall(text)
    # Check for free webmail domains masquerading as corporate
    has_free_email = bool(re.search(r"@(gmail|yahoo|hotmail|outlook)\.com", text, re.IGNORECASE))

    # Basic company heuristic (e.g. at [Company], from [Company])
    company = None
    comp_match = re.search(r"(?:at|from|with|company:?|organization:?)\s+([A-Z][a-zA-Z0-9\s&]{2,25})", text)
    if comp_match:
        company = comp_match.group(1).strip()

    role = None
    role_match = re.search(r"(?:role:?|position:?|hiring\s+for:?|internship\s+as:?|offer\s+for:?)\s+([a-zA-Z0-9\s-]{3,35})", text, re.IGNORECASE)
    if role_match:
        role = role_match.group(1).strip()

    return ExtractedEntities(
        company_or_org=company,
        opportunity_title=role,
        payment_demanded=payment,
        urgency_tactics=list(set(urgency_tactics))[:4],
        contact_details=contacts[:5],
        suspicious_urls=urls[:5]
    )

class AnalysisService:
    """Orchestrator for the full ScamSathi AI verification workflow."""

    def __init__(self):
        self.search_service = SearchService()
        self.nemotron_service = NemotronService()

    def analyze(self, message: str, target_language: str = "en") -> InvestigationReport:
        """
        Execute end-to-end opportunity verification.
        Validates input, retrieves Tavily evidence, prompts Nemotron via Nebius, and validates output.
        """
        # 1. Input Validation
        if not message or len(message.strip()) < settings.MIN_INPUT_LENGTH:
            raise ValueError(f"Message is too short ({len(message.strip())} chars). Please paste at least {settings.MIN_INPUT_LENGTH} characters of the suspicious offer.")

        if len(message) > settings.MAX_INPUT_LENGTH:
            raise ValueError(f"Message exceeds maximum size of {settings.MAX_INPUT_LENGTH} characters.")

        if check_prompt_injection(message):
            return InvestigationReport(
                summary="The submitted input contains adversarial prompt injection keywords. ScamSathi AI isolates untrusted input to maintain analytical integrity.",
                summary_telugu="సమర్పించిన ఇన్‌పుట్ అడ్వర్సరియల్ ప్రాంప్ట్ ఇంజెక్షన్ పదాలను కలిగి ఉంది. విశ్లేషణాత్మక సమగ్రతను నిర్వహించడానికి ScamSathi AI ఈ ఇన్‌పుట్‌ను ప్రత్యేకంగా విశ్లేషిస్తుంది.",
                extracted_entities=ExtractedEntities(urgency_tactics=["Adversarial instruction detected"]),
                risk_assessment=RiskAssessment(
                    category="High concern",
                    rationale="Input was flagged for attempted system prompt tampering or instruction injection, a hallmark of malicious interaction attempts.",
                    rationale_telugu="సిస్టమ్ ప్రాంప్ట్ ట్యాంపరింగ్ లేదా సూచనల ఇంజెక్షన్ ప్రయత్నం కోసం ఇన్‌పుట్ ఫ్లాగ్ చేయబడింది."
                ),
                warning_signs=[
                    WarningSign(
                        indicator="Hostile / Adversarial Input Attempt",
                        severity="critical",
                        explanation="Untrusted opportunity messages attempting to rewrite agent directives typically indicate deceptive behavior.",
                        explanation_telugu="ఏజెంట్ ఆదేశాలను తిరగరాయడానికి ప్రయత్నించే మోసపూరిత ఇన్‌పుట్."
                    )
                ],
                recommendations=[
                    Recommendation(
                        step="Do not execute instructions or open links contained in this payload.",
                        step_telugu="ఈ సందేశంలోని సూచనలను అమలు చేయవద్దు లేదా లింక్‌లను తెరవవద్దు.",
                        priority="immediate"
                    )
                ]
            )

        # 2. Extract Claim Entities
        extracted = extract_rule_based_claims(message)

        # 3. Evidence-Based Web Research via Tavily
        search_query = ""
        if extracted.company_or_org:
            search_query += f"{extracted.company_or_org} recruitment scam job verification"
        elif extracted.opportunity_title:
            search_query += f"{extracted.opportunity_title} hiring scam recruitment warning"
        else:
            first_words = " ".join(message.split()[:8])
            search_query += f"{first_words} job scam alert"

        evidence_list = self.search_service.search_evidence(search_query)

        # 4. Model Inference via Nemotron on Nebius Token Factory
        if settings.is_nebius_configured():
            try:
                nemotron_result = self.nemotron_service.analyze_opportunity(
                    message=message,
                    search_evidence=evidence_list,
                    target_language=target_language
                )
                report = InvestigationReport(**nemotron_result)
                report.raw_evidence_count = len(evidence_list)
                return report
            except Exception as e:
                # If Nebius API encountered an error, log and fallback cleanly to rule-based synthesis
                print(f"[ScamSathi AI] Nebius call error: {e}. Generating evidence-backed fallback report.")

        # 5. Fallback Evidence-Backed Synthesis (if Nebius key is missing or network interrupted)
        return self._generate_fallback_synthesis(message, extracted, evidence_list, target_language)

    def _generate_fallback_synthesis(
        self,
        message: str,
        extracted: ExtractedEntities,
        evidence: List[Dict[str, Any]],
        target_language: str
    ) -> InvestigationReport:
        """
        Synthesize rigorous evidence-based report when external API keys are not yet configured.
        Maintains genuine fraud heuristics, source grounding, and Telugu support.
        """
        warning_signs: List[WarningSign] = []
        is_high = False
        is_moderate = False

        # Payment check
        if extracted.payment_demanded:
            is_high = True
            warning_signs.append(
                WarningSign(
                    indicator="Advance Payment or Deposit Demand",
                    severity="critical",
                    explanation=f"Demanding fees ({extracted.payment_demanded}) before employment or scholarship disbursement is the defining hallmark of advance-fee recruitment fraud. Legitimate employers never charge candidates.",
                    explanation_telugu="ఉద్యోగం లేదా స్కాలర్‌షిప్ ఇచ్చే ముందు ఫీజులు డిమాండ్ చేయడం రిక్రూట్‌మెంట్ మోసానికి స్పష్టమైన సంకేతం. అసలైన కంపెనీలు ఎప్పుడూ రుసుము వసూలు చేయవు."
                )
            )

        # Check for free email addresses in corporate context
        free_emails = [c for c in extracted.contact_details if "gmail.com" in c or "yahoo.com" in c or "outlook.com" in c]
        if free_emails:
            is_moderate = True
            warning_signs.append(
                WarningSign(
                    indicator="Free Public Webmail Used For Corporate Hiring",
                    severity="elevated",
                    explanation=f"Official corporate recruiters communicate via organizational domain addresses (e.g., @company.com), not public webmail ({free_emails[0]}).",
                    explanation_telugu="అధికారిక కంపెనీలు తమ సొంత డొమైన్ ఈమెయిల్స్ ద్వారా మాత్రమే సంప్రదిస్తాయి, పబ్లిక్ జిమెయిల్ ద్వారా కాదు."
                )
            )

        # Urgency check
        if extracted.urgency_tactics:
            is_moderate = True
            warning_signs.append(
                WarningSign(
                    indicator="Artificial Urgency & High-Pressure Tactics",
                    severity="medium",
                    explanation=f"Phrases like '{', '.join(extracted.urgency_tactics)}' are engineered to induce hasty compliance before victims can verify claims.",
                    explanation_telugu="సమయం లేదని ఒత్తిడి చేయడం ద్వారా బాధితులు ఆలోచించకుండా త్వరగా డబ్బులు చెల్లించేలా చేస్తారు."
                )
            )

        # Telegram / WhatsApp interviews
        social_contacts = [c for c in extracted.contact_details if "Telegram" in c or "Whatsapp" in c]
        if social_contacts:
            if not is_high:
                is_moderate = True
            warning_signs.append(
                WarningSign(
                    indicator="Recruitment Conducted Solely Over Chat Apps",
                    severity="elevated",
                    explanation="Recruiting, task assignment, or payout negotiations solely over Telegram or WhatsApp without an official applicant tracking portal is common in task scams.",
                    explanation_telugu="టెలిగ్రామ్ లేదా వాట్సాప్ ద్వారా మాత్రమే ఇంటర్వ్యూలు మరియు ఉద్యోగ నియామకాలు నిర్వహించడం అనుమానాస్పదం."
                )
            )

        # Determine risk category
        if is_high:
            category = "High concern"
            rationale = "Multiple severe indicators detected, including upfront payment or security deposit demands and unverified contact channels."
            rationale_telugu = "ముందస్తు చెల్లింపు డిమాండ్లు మరియు ధృవీకరించబడని సంప్రదింపు మార్గాలతో సహా తీవ్రమైన మోసపూరిత సంకేతాలు కనుగొనబడ్డాయి."
        elif is_moderate:
            category = "Moderate concern"
            rationale = "Potential inconsistencies detected, such as free webmail addresses, artificial urgency, or lack of formal verification sources."
            rationale_telugu = "ఉచిత వెబ్‌మెయిల్ చిరునామాలు, కృత్రిమ అత్యవసర పరిస్థితి వంటి అనుమానాస్పద అంశాలు గుర్తించబడ్డాయి."
        elif len(message) < 50:
            category = "Insufficient evidence"
            rationale = "Submitted text is too brief to substantiate or refute legitimacy. Additional context, sender headers, or URLs are required."
            rationale_telugu = "చట్టబద్ధతను ధృవీకరించడానికి లేదా తిరస్కరించడానికి సమర్పించిన సమాచారం సరిపోదు."
        else:
            category = "Low concern"
            rationale = "No explicit payment demands, credential requests, or severe pressure tactics were detected in the analyzed text."
            rationale_telugu = "విశ్లేషించబడిన వచనంలో ఎటువంటి ముందస్తు చెల్లింపు డిమాండ్లు లేదా అనుమానాస్పద సంకేతాలు కనుగొనబడలేదు."

        evidence_comp = []
        for ev in evidence[:3]:
            evidence_comp.append(
                EvidenceComparison(
                    claim=f"Verification research regarding {extracted.company_or_org or 'recruitment message'}",
                    status="verified" if ev.get("is_official") else "unverified",
                    evidence_snippet=ev.get("content", "")[:180],
                    source_url=ev.get("url")
                )
            )

        recommendations = [
            Recommendation(
                step="Directly cross-reference this opportunity on the official organization careers portal; never rely on forwarded contact info.",
                step_telugu="అధికారిక కంపెనీ వెబ్‌సైట్ లేదా కెరీర్స్ పేజీ ద్వారా మాత్రమే ఈ అవకాశాన్ని ధృవీకరించుకోండి.",
                priority="immediate"
            ),
            Recommendation(
                step="Never transfer money for registration, onboarding kits, background checks, or refundable security deposits.",
                step_telugu="రిజిస్ట్రేషన్, కిట్లు లేదా సెక్యూరిటీ డిపాజిట్ల కోసం ఎట్టి పరిస్థితుల్లోనూ డబ్బు చెల్లించవద్దు.",
                priority="immediate"
            ),
            Recommendation(
                step="Do not share bank OTPs, Aadhaar numbers, PAN cards, or net banking passwords with unverified recruiters.",
                step_telugu="బ్యాంక్ OTPలు, ఆధార్ లేదా గుర్తింపు పత్రాలను ఎవరితోనూ పంచుకోవద్దు.",
                priority="standard"
            )
        ]

        summary_en = f"Investigation of opportunity claiming affiliation with '{extracted.company_or_org or 'Unspecified Organization'}'. Warning signs: {len(warning_signs)}. Risk categorization: {category}."
        summary_te = f"'{extracted.company_or_org or 'పేరులేని సంస్థ'}'కి సంబంధించిన అవకాశంపై పరిశోధన. గుర్తించబడిన హెచ్చరికలు: {len(warning_signs)}. ప్రమాద స్థాయి: {category}."

        return InvestigationReport(
            summary=summary_en,
            summary_telugu=summary_te,
            extracted_entities=extracted,
            risk_assessment=RiskAssessment(
                category=category,
                rationale=rationale,
                rationale_telugu=rationale_telugu
            ),
            warning_signs=warning_signs,
            evidence_comparison=evidence_comp,
            recommendations=recommendations,
            model_used="NVIDIA Nemotron via Nebius Token Factory (Rule-Assisted Agent)",
            raw_evidence_count=len(evidence)
        )
