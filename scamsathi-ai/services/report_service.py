"""
Report generation service for ScamSathi AI.
Provides clean investigation summaries and downloadable PDF reports.
"""

import io
from typing import Optional
from services.analysis_service import InvestigationReport

class ReportService:
    """Generates printable text and PDF format investigation reports."""

    @staticmethod
    def generate_text_summary(report: InvestigationReport, language: str = "en") -> str:
        """Create a clean plain-text summary suitable for terminal or quick export."""
        is_te = language == "te"
        
        lines = [
            "=" * 68,
            "SCAMSATHI AI — INTELLIGENT SCAM VERIFICATION REPORT",
            "=" * 68,
            f"Risk Assessment Category: {report.risk_assessment.category.upper()}",
            f"Rationale: {report.risk_assessment.rationale_telugu if is_te and report.risk_assessment.rationale_telugu else report.risk_assessment.rationale}",
            "-" * 68,
            "EXTRACTED OPPORTUNITY CLAIMS:",
            f"• Organization: {report.extracted_entities.company_or_org or 'Not specified'}",
            f"• Opportunity Title: {report.extracted_entities.opportunity_title or 'Not specified'}",
            f"• Payment Demands: {report.extracted_entities.payment_demanded or 'None detected'}",
            f"• Contact Channels: {', '.join(report.extracted_entities.contact_details) if report.extracted_entities.contact_details else 'None identified'}",
            "-" * 68,
            f"WARNING SIGNS DETECTED ({len(report.warning_signs)}):",
        ]

        for idx, ws in enumerate(report.warning_signs, 1):
            expl = ws.explanation_telugu if is_te and ws.explanation_telugu else ws.explanation
            lines.append(f"  {idx}. [{ws.severity.upper()}] {ws.indicator}")
            lines.append(f"     Why it matters: {expl}")

        lines.append("-" * 68)
        lines.append(f"EVIDENCE COMPARISON ({len(report.evidence_comparison)} sources):")
        for idx, ev in enumerate(report.evidence_comparison, 1):
            lines.append(f"  {idx}. Claim: {ev.claim}")
            lines.append(f"     Status: {ev.status.upper()}")
            lines.append(f"     Evidence: {ev.evidence_snippet}")
            if ev.source_url:
                lines.append(f"     Source Link: {ev.source_url}")

        lines.append("-" * 68)
        lines.append("RECOMMENDED SAFE NEXT STEPS:")
        for idx, rec in enumerate(report.recommendations, 1):
            step = rec.step_telugu if is_te and rec.step_telugu else rec.step
            lines.append(f"  {idx}. [{rec.priority.upper()}] {step}")

        lines.append("=" * 68)
        lines.append(f"LIMITATIONS: {report.risk_assessment.limitations}")
        lines.append(f"INFERENCE ENGINE: {report.model_used}")
        lines.append("=" * 68)

        return "\n".join(lines)

    @staticmethod
    def generate_pdf_report(report: InvestigationReport, language: str = "en") -> bytes:
        """
        Generate a clean PDF report using ReportLab if installed,
        or fallback to formatted text buffer.
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=40,
                leftMargin=40,
                topMargin=40,
                bottomMargin=40
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Heading1'],
                fontSize=20,
                leading=24,
                textColor=colors.HexColor('#0F172A')
            )
            h2_style = ParagraphStyle(
                'H2Style',
                parent=styles['Heading2'],
                fontSize=13,
                leading=16,
                textColor=colors.HexColor('#0284C7'),
                spaceBefore=10,
                spaceAfter=4
            )
            body_style = ParagraphStyle(
                'Body',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                textColor=colors.HexColor('#334155')
            )

            elements = []
            elements.append(Paragraph("<b>ScamSathi AI</b> — Investigation Report", title_style))
            elements.append(Paragraph("Intelligent Scam Verification Agent for Students & Job Seekers", body_style))
            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1')))
            elements.append(Spacer(1, 10))

            # Risk Category
            cat = report.risk_assessment.category
            elements.append(Paragraph(f"<b>Risk Assessment:</b> {cat.upper()}", h2_style))
            elements.append(Paragraph(f"<b>Rationale:</b> {report.risk_assessment.rationale}", body_style))
            elements.append(Spacer(1, 10))

            # Warning signs
            elements.append(Paragraph(f"<b>Potential Warning Signs ({len(report.warning_signs)})</b>", h2_style))
            for ws in report.warning_signs:
                elements.append(Paragraph(f"• <b>[{ws.severity.upper()}] {ws.indicator}</b>: {ws.explanation}", body_style))
                elements.append(Spacer(1, 4))

            # Evidence
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(f"<b>Evidence & Public Verification Sources</b>", h2_style))
            for ev in report.evidence_comparison:
                url_text = f" (<font color='#0284C7'>{ev.source_url}</font>)" if ev.source_url else ""
                elements.append(Paragraph(f"• <b>Claim:</b> {ev.claim} [{ev.status.upper()}]<br/>&nbsp;&nbsp;{ev.evidence_snippet}{url_text}", body_style))
                elements.append(Spacer(1, 4))

            # Recommendations
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("<b>Recommended Safe Next Steps</b>", h2_style))
            for rec in report.recommendations:
                elements.append(Paragraph(f"• <b>[{rec.priority.upper()}]</b> {rec.step}", body_style))
                elements.append(Spacer(1, 4))

            elements.append(Spacer(1, 12))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0')))
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<b>Disclaimer:</b> {report.risk_assessment.limitations}", ParagraphStyle('Disclaimer', parent=body_style, fontSize=8, leading=10, textColor=colors.HexColor('#64748B'))))

            doc.build(elements)
            buffer.seek(0)
            return buffer.getvalue()

        except ImportError:
            # Fallback plain text bytes if reportlab is not installed
            text = ReportService.generate_text_summary(report, language)
            return text.encode("utf-8")
