"""PDF digest generator for VPG Intelligence Digest.

Converts the HTML digest to a PDF with embedded links, suitable for
email attachment delivery. This bypasses enterprise spam filters that
block or scramble HTML email content.

Uses weasyprint for HTML-to-PDF conversion with full CSS support.
Falls back to a simple text-based PDF via reportlab if weasyprint
is not available.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _generate_with_weasyprint(html: str, output_path: Path, cid_images: dict | None = None) -> Path:
    """Generate PDF using weasyprint (preferred — full CSS support)."""
    from weasyprint import HTML

    # Convert CID references to data URIs for PDF rendering
    pdf_html = html
    if cid_images:
        for cid, img_data in cid_images.items():
            data_uri = img_data.get("data_uri", "")
            if data_uri:
                pdf_html = pdf_html.replace(f"cid:{cid}", data_uri)

    html_doc = HTML(string=pdf_html)
    html_doc.write_pdf(str(output_path))
    return output_path


def _generate_with_reportlab(
    context: dict, output_path: Path
) -> Path:
    """Generate PDF using reportlab (fallback — simpler layout)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DigestTitle",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.HexColor("#1B2A4A"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DigestSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#6B82A6"),
        spaceAfter=16,
    )
    heading_style = ParagraphStyle(
        "BUHeading",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#1B2A4A"),
        spaceBefore=16,
        spaceAfter=8,
    )
    signal_heading_style = ParagraphStyle(
        "SignalHeading",
        parent=styles["Heading3"],
        fontSize=13,
        textColor=colors.HexColor("#1B2A4A"),
        spaceBefore=8,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "FieldLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#2E75B6"),
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "FieldValue",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#2D3748"),
        leading=14,
        spaceAfter=4,
    )
    source_style = ParagraphStyle(
        "SourceLink",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#2E75B6"),
        spaceAfter=8,
    )

    story = []

    # Title
    story.append(Paragraph("VPG Intelligence Digest", title_style))
    week = context.get("week_number", "")
    year = context.get("year", "")
    date_range = context.get("date_range", "")
    story.append(Paragraph(
        f"Week {week}, {year} &bull; {date_range} &bull; "
        f"{context.get('total_signals', 0)} Signals &bull; "
        f"{context.get('bu_count', 0)} Business Units",
        subtitle_style,
    ))
    story.append(Spacer(1, 8))

    def _render_signal_card(signal, story_list):
        """Add a signal action card to the story."""
        sig_type = (signal.get("signal_type", "") or "").replace("-", " ").title()
        headline = signal.get("headline", "Untitled Signal")
        score = signal.get("composite_score", 0)
        score_label = f"[{score}]" if score else ""

        story_list.append(Paragraph(
            f"<b>{sig_type}</b> {score_label} &mdash; {headline}",
            signal_heading_style,
        ))

        if signal.get("what_summary"):
            story_list.append(Paragraph("WHAT", label_style))
            story_list.append(Paragraph(
                _clean_html(signal["what_summary"]), body_style
            ))

        if signal.get("why_it_matters"):
            story_list.append(Paragraph("WHY IT MATTERS", label_style))
            story_list.append(Paragraph(
                _clean_html(signal["why_it_matters"]), body_style
            ))

        if signal.get("quick_win"):
            story_list.append(Paragraph("QUICK WIN", label_style))
            story_list.append(Paragraph(
                _clean_html(signal["quick_win"]), body_style
            ))

        if signal.get("suggested_owner"):
            story_list.append(Paragraph("OWNER", label_style))
            story_list.append(Paragraph(signal["suggested_owner"], body_style))

        if signal.get("estimated_impact"):
            story_list.append(Paragraph("EST. IMPACT", label_style))
            story_list.append(Paragraph(signal["estimated_impact"], body_style))

        if signal.get("url"):
            story_list.append(Paragraph(
                f'Source: <a href="{signal["url"]}" color="#2E75B6">{signal["url"][:80]}</a>',
                source_style,
            ))

        story_list.append(Spacer(1, 6))

    # Signal of the week
    sotw = context.get("signal_of_week")
    if sotw:
        story.append(Paragraph("SIGNAL OF THE WEEK", ParagraphStyle(
            "SOTWBadge", parent=styles["Normal"],
            fontSize=11, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#1B2A4A"),
            spaceBefore=4, spaceAfter=4,
        )))
        _render_signal_card(sotw, story)

    # Top signals summary
    top_signals = context.get("top_signals", [])
    if top_signals:
        story.append(Paragraph("Top Signals This Week", heading_style))
        for sig in top_signals:
            score = sig.get("composite_score", 0)
            headline = sig.get("headline", "")
            sig_type = (sig.get("signal_type", "") or "").replace("-", " ").title()
            story.append(Paragraph(
                f"&bull; [{score}] {headline} <i>({sig_type})</i>",
                body_style,
            ))
        story.append(Spacer(1, 8))

    # BU Sections
    for section in context.get("bu_sections", []):
        bu_name = section.get("bu_name", "Unknown")
        story.append(Paragraph(bu_name, heading_style))

        for signal in section.get("signals", []):
            _render_signal_card(signal, story)

    # Footer
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Powered by VPG Strategic Intelligence &bull; "
        f"Auto-generated from {context.get('total_signals', 0)} validated industry signals",
        ParagraphStyle(
            "Footer", parent=styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#8BA3C7"),
            alignment=1,
        ),
    ))

    doc.build(story)
    return output_path


def _clean_html(text: str) -> str:
    """Strip HTML tags from text for reportlab Paragraph (which has its own markup)."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def generate_pdf(
    html: str,
    context: dict,
    output_dir: Path,
    filename: str | None = None,
    cid_images: dict | None = None,
) -> Path:
    """Generate a PDF version of the digest.

    Tries weasyprint first (full HTML/CSS rendering), falls back to
    reportlab (structured text-based PDF).

    Args:
        html: Rendered HTML content of the digest.
        context: Template context dict (used for reportlab fallback).
        output_dir: Directory to save the PDF.
        filename: Optional filename (defaults to digest-YYYY-WNN.pdf).
        cid_images: CID image data for resolving embedded images.

    Returns:
        Path to the generated PDF file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        week = context.get("week_number", 0)
        year = context.get("year", 0)
        filename = f"digest-{year}-W{week:02d}.pdf"

    output_path = output_dir / filename

    # Try weasyprint first
    try:
        result = _generate_with_weasyprint(html, output_path, cid_images)
        logger.info("PDF generated with weasyprint: %s", result)
        return result
    except ImportError:
        logger.info("weasyprint not available, trying reportlab fallback")
    except Exception as e:
        logger.warning("weasyprint failed: %s — trying reportlab fallback", e)

    # Try reportlab fallback
    try:
        result = _generate_with_reportlab(context, output_path)
        logger.info("PDF generated with reportlab: %s", result)
        return result
    except ImportError:
        logger.error(
            "Neither weasyprint nor reportlab available. "
            "Install one: pip install weasyprint  OR  pip install reportlab"
        )
        raise RuntimeError(
            "PDF generation requires weasyprint or reportlab. "
            "Install with: pip install weasyprint  or  pip install reportlab"
        )
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        raise
