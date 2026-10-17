"""
ScamSathi AI — Intelligent Scam Verification Agent
Streamlit Web Application for NVIDIA x Nebius Global AI Hackathon.
"""

import streamlit as st
import json
import time
from services.analysis_service import AnalysisService, InvestigationReport
from services.report_service import ReportService
from config import settings

st.set_page_config(
    page_title="ScamSathi AI — Intelligent Scam Verification Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Navy & Teal Styling for Cybersecurity Dashboard
st.markdown("""
<style>
    /* Dark Navy & Teal Theme */
    .stApp {
        background-color: #0b1120;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Headers */
    h1, h2, h3, h4 {
        color: #f1f5f9 !important;
        font-weight: 700 !important;
    }
    
    /* Subheaders and descriptions */
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    
    /* Custom Card */
    .cyber-card {
        background-color: #111d35;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    /* Severity indicators */
    .risk-high {
        background-color: rgba(220, 38, 38, 0.15);
        border: 1px solid #dc2626;
        color: #fca5a5;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .risk-moderate {
        background-color: rgba(217, 119, 6, 0.15);
        border: 1px solid #d97706;
        color: #fcd34d;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .risk-low {
        background-color: rgba(22, 163, 74, 0.15);
        border: 1px solid #16a34a;
        color: #86efac;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
    .risk-insufficient {
        background-color: rgba(100, 116, 139, 0.15);
        border: 1px solid #64748b;
        color: #cbd5e1;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Preset sample test messages
PRESET_MESSAGES = {
    "Select a benchmark sample to test...": "",
    "🚨 High Concern: Telegram Part-Time Review Job (₹2,500 Deposit)": (
        "Congratulations! Your profile on LinkedIn has been shortlisted by Global Marketing Ltd for Part-Time Social Media Evaluator. "
        "Earn ₹3,500 - ₹5,000 daily by simply rating travel listings and watching YouTube videos. "
        "Work 1-2 hours from phone. Daily payouts via UPI/Paytm. "
        "To activate your verified employee portal and receive task tokens, an advance security deposit of ₹2,500 is required (100% refundable with first salary). "
        "Hurry! Only 4 positions remaining today. Contact Manager Priya on Telegram: https://t.me/global_hr_priya immediately."
    ),
    "🚨 High Concern: Fraudulent PM Higher Education Scholarship": (
        "NATIONAL SCHOLARSHIP PORTAL ALERT: You are selected for Pradhan Mantri National Merit Scholarship 2026. "
        "Sanctioned grant: ₹60,000. To transfer the scholarship funds directly into your bank account, send your Aadhaar OTP "
        "and remit an application processing fee of ₹500 via Google Pay to treasury-agent@okaxis. "
        "Offer valid for 4 hours only. Do not miss this official government award."
    ),
    "⚠️ Moderate Concern: Remote Data Entry Internship (Gmail recruiter)": (
        "Apex Tech Solutions LLC is looking for Remote Virtual Assistants and Data Entry Interns. "
        "Stipend: ₹25,000 per month. Flexible hours. No prior experience needed. "
        "Please send your resume, photo ID card copy, and contact number to hr.apextechsolutions2026@gmail.com. "
        "Immediate onboarding starts this Monday."
    ),
    "✅ Low Concern: Legitimate Google STEP Internship Announcement": (
        "Google is accepting applications for the Student Training in Engineering Program (STEP) Internship 2026. "
        "The 12-week summer program is open to first and second-year undergraduate students pursuing a Bachelor's degree in Computer Science or related STEM fields. "
        "Google never charges any application fees, registration fees, or equipment security deposits at any stage of the recruitment process. "
        "Submit your application and transcripts exclusively via the official portal at https://careers.google.com/jobs."
    )
}

# Sidebar Configuration
with st.sidebar:
    st.markdown("### 🛡️ ScamSathi AI Control Center")
    st.markdown("NVIDIA × Nebius Global AI Hackathon")
    
    st.markdown("---")
    language = st.radio(
        "Display Language / భాష:",
        options=["English", "Telugu (తెలుగు)"],
        index=0
    )
    lang_code = "te" if "Telugu" in language else "en"

    st.markdown("---")
    st.markdown("#### Model & Service Status")
    nebius_status = "🟢 Configured" if settings.is_nebius_configured() else "🟡 Fallback / Ready"
    tavily_status = "🟢 Live Web Search" if settings.is_tavily_configured() else "🟡 Domain Checking"
    
    st.markdown(f"**NVIDIA Nemotron:** {nebius_status}")
    st.caption(f"Model ID: `{settings.NEBIUS_MODEL_ID}`")
    st.markdown(f"**Tavily Search API:** {tavily_status}")

    st.markdown("---")
    st.markdown("#### About ScamSathi AI")
    st.caption(
        "ScamSathi AI safeguards students and job seekers against recruitment fraud, advance-fee scams, and fake scholarship notifications through evidence-based research and open-source NVIDIA Nemotron inference."
    )

# Main Application Header
st.title("🛡️ ScamSathi AI — Intelligent Scam Verification Agent")
st.markdown(
    '<p class="hero-subtitle">Evidence-based opportunity verification for students & job seekers powered by NVIDIA Nemotron & Tavily Search.</p>',
    unsafe_allow_html=True
)

# Preset Selector
selected_preset_key = st.selectbox(
    "Load Benchmark Opportunity Message (or paste your own below):",
    options=list(PRESET_MESSAGES.keys()),
    index=0
)

# User input text area
default_text = PRESET_MESSAGES.get(selected_preset_key, "")
user_message = st.text_area(
    "Paste Suspicious Message, Internship Offer, Scholarship Email, or Job Text:",
    value=default_text,
    height=160,
    max_chars=settings.MAX_INPUT_LENGTH,
    placeholder="Paste the complete text or message you received (e.g. recruitment email, WhatsApp text, Telegram job offer, scholarship notification)..."
)

col_act1, col_act2 = st.columns([2, 8])
with col_act1:
    analyze_button = st.button("🔍 Investigate with ScamSathi", type="primary", use_container_width=True)
with col_act2:
    st.caption("🔒 All message submissions are processed in memory and never stored or retained.")

if analyze_button:
    if not user_message or len(user_message.strip()) < settings.MIN_INPUT_LENGTH:
        st.error(f"Please provide at least {settings.MIN_INPUT_LENGTH} characters of text to investigate.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Step 1/4: Validating input & isolating adversarial prompt keywords...")
            progress_bar.progress(25)
            time.sleep(0.2)

            status_text.text("Step 2/4: Extracting opportunity entities & querying Tavily Web Search...")
            progress_bar.progress(50)
            time.sleep(0.2)

            status_text.text("Step 3/4: Prompting NVIDIA Nemotron via Nebius Token Factory...")
            progress_bar.progress(75)
            
            service = AnalysisService()
            report: InvestigationReport = service.analyze(user_message, target_language=lang_code)

            status_text.text("Step 4/4: Validating Pydantic schema & compiling evidence report...")
            progress_bar.progress(100)
            time.sleep(0.1)

            progress_bar.empty()
            status_text.empty()

            # Render Report
            st.markdown("---")
            st.subheader("📋 Investigation Report")

            # Risk Category Header
            cat = report.risk_assessment.category
            cat_css = "risk-high" if "high" in cat.lower() else "risk-moderate" if "moderate" in cat.lower() else "risk-low" if "low" in cat.lower() else "risk-insufficient"
            
            col_risk1, col_risk2 = st.columns([1, 2])
            with col_risk1:
                st.markdown(f'<div class="{cat_css}">Risk Assessment: {cat.upper()}</div>', unsafe_allow_html=True)
            with col_risk2:
                rationale_display = report.risk_assessment.rationale_telugu if lang_code == "te" and report.risk_assessment.rationale_telugu else report.risk_assessment.rationale
                st.markdown(f"**Rationale:** {rationale_display}")

            st.caption(f"⚠️ *{report.risk_assessment.limitations}*")

            # Two Column Split: Extracted Claims & Warning Signs
            col_claims, col_warnings = st.columns(2)

            with col_claims:
                st.markdown("#### 🔍 Extracted Claims")
                ee = report.extracted_entities
                st.markdown(f"• **Organization:** {ee.company_or_org or 'Not explicitly identified'}")
                st.markdown(f"• **Opportunity Title:** {ee.opportunity_title or 'Not explicitly identified'}")
                st.markdown(f"• **Payment Demands:** {ee.payment_demanded or 'None detected'}")
                if ee.urgency_tactics:
                    st.markdown(f"• **Urgency Signals:** {', '.join(ee.urgency_tactics)}")
                if ee.contact_details:
                    st.markdown(f"• **Contact Channels:** {', '.join(ee.contact_details)}")

            with col_warnings:
                st.markdown(f"#### ⚠️ Warning Signs ({len(report.warning_signs)})")
                if not report.warning_signs:
                    st.success("No severe warning signs detected in submitted text.")
                else:
                    for ws in report.warning_signs:
                        expl = ws.explanation_telugu if lang_code == "te" and ws.explanation_telugu else ws.explanation
                        st.markdown(f"• **[{ws.severity.upper()}] {ws.indicator}**  \n  {expl}")

            # Evidence Sources
            st.markdown("---")
            st.markdown(f"#### 🌐 Retrieved Web Evidence ({len(report.evidence_comparison)} references)")
            for ev in report.evidence_comparison:
                st.markdown(f"**Claim:** {ev.claim} — *Status: {ev.status.upper()}*")
                st.markdown(f"> {ev.evidence_snippet}")
                if ev.source_url:
                    st.markdown(f"🔗 [View Source]({ev.source_url})")

            # Recommended Actions
            st.markdown("---")
            st.markdown("#### 🛡️ Safe Verification Next Steps")
            for rec in report.recommendations:
                step_display = rec.step_telugu if lang_code == "te" and rec.step_telugu else rec.step
                st.markdown(f"• **[{rec.priority.upper()}]** {step_display}")

            # Download PDF Report
            st.markdown("---")
            pdf_bytes = ReportService.generate_pdf_report(report, language=lang_code)
            st.download_button(
                label="📥 Download Official Investigation PDF Report",
                data=pdf_bytes,
                file_name="ScamSathi_Investigation_Report.pdf",
                mime="application/pdf"
            )

        except Exception as err:
            st.error(f"Analysis Error: {str(err)}")
