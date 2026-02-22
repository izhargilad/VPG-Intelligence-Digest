"""PDF digest generator for VPG Intelligence Digest.

Generates a professionally designed PDF with VPG branding, color-coded
signal type badges, score indicators, and structured action cards.

Uses reportlab for programmatic PDF generation with full layout control.
Falls back to weasyprint for HTML-to-PDF if available.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── VPG Brand Colors ──────────────────────────────────────────────────
NAVY = "#1B2A4A"
BLUE = "#2E75B6"
ACCENT = "#E8792F"
LIGHT_BG = "#F0F3F7"
WHITE = "#FFFFFF"
DARK_TEXT = "#2D3748"
MID_TEXT = "#4A5568"
LIGHT_TEXT = "#8BA3C7"

SIGNAL_TYPE_COLORS = {
    "competitive-threat":    {"color": "#B71C1C", "bg": "#FDE8E8", "icon": "\u26a0\ufe0f",  "label": "Competitive Threat"},
    "revenue-opportunity":   {"color": "#1B5E20", "bg": "#E6F4EA", "icon": "\U0001f4b0", "label": "Revenue Opportunity"},
    "market-shift":          {"color": "#0D47A1", "bg": "#E3F2FD", "icon": "\U0001f3af", "label": "Market Shift"},
    "partnership-signal":    {"color": "#006064", "bg": "#E0F2F1", "icon": "\U0001f91d", "label": "Partnership Signal"},
    "customer-intelligence": {"color": "#4A148C", "bg": "#F3E5F5", "icon": "\U0001f4ca", "label": "Customer Intelligence"},
    "technology-trend":      {"color": "#01579B", "bg": "#E1F5FE", "icon": "\U0001f680", "label": "Technology Trend"},
    "trade-tariff":          {"color": "#263238", "bg": "#ECEFF1", "icon": "\U0001f30d", "label": "Trade & Tariff"},
}
_DEFAULT_TYPE = {"color": BLUE, "bg": "#E3F2FD", "icon": "", "label": "Signal"}


def _clean_html(text: str) -> str:
    """Strip HTML tags for reportlab Paragraph markup."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(text))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _score_color(score: float) -> str:
    """Return a color hex based on score value."""
    if score >= 7.5:
        return "#1B5E20"  # Green
    if score >= 5.5:
        return BLUE
    return "#B71C1C"  # Red


def _generate_with_reportlab(context: dict, output_path: Path) -> Path:
    """Generate a professionally designed PDF using reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        topMargin=0.4 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    W = doc.width  # usable width

    # ── Styles ─────────────────────────────────────────────────────
    s_title = ParagraphStyle("Title2", parent=styles["Title"],
        fontSize=26, textColor=colors.HexColor(WHITE),
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=32)
    s_subtitle = ParagraphStyle("Sub", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor(LIGHT_TEXT),
        alignment=TA_CENTER, spaceAfter=2)
    s_stats = ParagraphStyle("Stats", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor(WHITE),
        alignment=TA_CENTER, leading=14)

    s_section = ParagraphStyle("Section", parent=styles["Heading2"],
        fontSize=15, textColor=colors.HexColor(NAVY),
        fontName="Helvetica-Bold", spaceBefore=18, spaceAfter=6)
    s_bu_head = ParagraphStyle("BUHead", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor(WHITE),
        fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=0, leading=20)

    s_card_head = ParagraphStyle("CardHead", parent=styles["Normal"],
        fontSize=12, textColor=colors.HexColor(NAVY),
        fontName="Helvetica-Bold", leading=16, spaceAfter=2)
    s_badge = ParagraphStyle("Badge", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor(WHITE),
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=12)
    s_score_badge = ParagraphStyle("ScoreBadge", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor(WHITE),
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=14)

    s_label = ParagraphStyle("Label", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor(BLUE),
        fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=1)
    s_body = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor(DARK_TEXT),
        leading=13, spaceAfter=2)
    s_body_bullet = ParagraphStyle("BodyBullet", parent=s_body,
        bulletIndent=8, leftIndent=18, bulletFontSize=8)
    s_meta = ParagraphStyle("Meta", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor(MID_TEXT), leading=11)
    s_source = ParagraphStyle("Src", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor(BLUE), leading=11)
    s_footer = ParagraphStyle("Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor(LIGHT_TEXT),
        alignment=TA_CENTER, spaceBefore=12)

    story = []

    # ── Navy Header Bar ────────────────────────────────────────────
    week = context.get("week_number", "")
    year = context.get("year", "")
    date_range = context.get("date_range", "")
    total = context.get("total_signals", 0)
    bu_count = context.get("bu_count", 0)

    header_data = [[
        Paragraph("VPG Intelligence Digest", s_title),
    ], [
        Paragraph(
            f"Week {week}, {year} &bull; {date_range} &bull; "
            f"<b>{total}</b> Signals &bull; <b>{bu_count}</b> Business Units",
            s_stats,
        ),
    ]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(NAVY)),
        ("TOPPADDING", (0, 0), (0, 0), 20),
        ("BOTTOMPADDING", (0, -1), (0, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6, 6, 0, 0]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))

    def _make_signal_card(signal, is_sotw=False):
        """Build a Table representing a single signal action card."""
        sig_type_id = signal.get("signal_type", "")
        type_info = SIGNAL_TYPE_COLORS.get(sig_type_id, _DEFAULT_TYPE)
        type_color = colors.HexColor(type_info["color"])
        type_bg = colors.HexColor(type_info["bg"])
        type_label = type_info["label"]

        headline = _clean_html(signal.get("headline", "Untitled"))
        score = signal.get("composite_score", 0)
        sc = colors.HexColor(_score_color(score))

        # Row 1: type badge + headline + score
        badge_tbl = Table(
            [[Paragraph(type_label, s_badge)]],
            colWidths=[1.3 * inch],
        )
        badge_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), type_color),
            ("TOPPADDING", (0, 0), (0, 0), 3),
            ("BOTTOMPADDING", (0, 0), (0, 0), 3),
            ("LEFTPADDING", (0, 0), (0, 0), 6),
            ("RIGHTPADDING", (0, 0), (0, 0), 6),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
            ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ]))

        score_tbl = Table(
            [[Paragraph(f"{score:.1f}", s_score_badge)]],
            colWidths=[0.5 * inch],
        )
        score_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), sc),
            ("TOPPADDING", (0, 0), (0, 0), 3),
            ("BOTTOMPADDING", (0, 0), (0, 0), 3),
            ("LEFTPADDING", (0, 0), (0, 0), 4),
            ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
            ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ]))

        head_row = Table(
            [[badge_tbl, Paragraph(f"<b>{headline}</b>", s_card_head), score_tbl]],
            colWidths=[1.4 * inch, W - 2.3 * inch, 0.6 * inch],
        )
        head_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        # Build card body rows
        body_parts = []

        # WHAT — as bullets
        what = _clean_html(signal.get("what_summary", ""))
        if what:
            body_parts.append(Paragraph("WHAT", s_label))
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", what) if s.strip()]
            for sent in sentences[:5]:
                body_parts.append(Paragraph(sent, s_body_bullet, bulletText="\u2022"))

        # WHY IT MATTERS
        why = _clean_html(signal.get("why_it_matters", ""))
        if why:
            body_parts.append(Paragraph("WHY IT MATTERS", s_label))
            body_parts.append(Paragraph(why, s_body))

        # QUICK WIN
        qw = _clean_html(signal.get("quick_win", ""))
        if qw:
            body_parts.append(Paragraph("QUICK WIN", s_label))
            body_parts.append(Paragraph(qw, s_body))

        # Meta row: owner + impact
        meta_parts = []
        owner = signal.get("suggested_owner", "")
        impact = signal.get("estimated_impact", "")
        if owner:
            meta_parts.append(f"<b>Owner:</b> {_clean_html(owner)}")
        if impact:
            meta_parts.append(f"<b>Est. Impact:</b> {_clean_html(impact)}")
        if meta_parts:
            body_parts.append(Paragraph(" &bull; ".join(meta_parts), s_meta))

        # Source link
        url = signal.get("url", "")
        if url:
            short_url = url[:90] + ("..." if len(url) > 90 else "")
            body_parts.append(Paragraph(
                f'<a href="{url}" color="{BLUE}">{short_url}</a>', s_source
            ))

        # Wrap everything in a card table with colored left border
        card_rows = [[head_row]] + [[p] for p in body_parts]
        card_tbl = Table(card_rows, colWidths=[W - 0.15 * inch])

        border_color = type_color if not is_sotw else colors.HexColor(ACCENT)
        card_style = [
            ("BACKGROUND", (0, 0), (-1, -1), type_bg if not is_sotw else colors.HexColor("#FFF8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBEFORECOL", (0, 0), (0, -1), 3, border_color),
            ("ROUNDEDCORNERS", [0, 4, 4, 0]),
        ]
        card_tbl.setStyle(TableStyle(card_style))
        return card_tbl

    # ── Signal of the Week ─────────────────────────────────────────
    sotw = context.get("signal_of_week")
    if sotw:
        # SOTW banner
        sotw_banner = Table(
            [[Paragraph("\u2b50  SIGNAL OF THE WEEK", ParagraphStyle(
                "SOTWBanner", parent=s_badge, fontSize=10,
                textColor=colors.HexColor(WHITE), alignment=TA_LEFT))]],
            colWidths=[W],
        )
        sotw_banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(ACCENT)),
            ("TOPPADDING", (0, 0), (0, 0), 6),
            ("BOTTOMPADDING", (0, 0), (0, 0), 6),
            ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("ROUNDEDCORNERS", [4, 4, 0, 0]),
        ]))
        story.append(sotw_banner)
        story.append(_make_signal_card(sotw, is_sotw=True))
        story.append(Spacer(1, 10))

    # ── Executive Summary ──────────────────────────────────────────
    top_signals = context.get("top_signals", [])
    if top_signals:
        story.append(Paragraph("Executive Summary", s_section))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor(BLUE), spaceAfter=6))
        for sig in top_signals:
            score = sig.get("composite_score", 0)
            headline = _clean_html(sig.get("headline", ""))
            sig_type_id = sig.get("signal_type", "")
            type_info = SIGNAL_TYPE_COLORS.get(sig_type_id, _DEFAULT_TYPE)
            sc_hex = _score_color(score)
            story.append(Paragraph(
                f'<font color="{sc_hex}"><b>[{score:.1f}]</b></font> '
                f'{headline} '
                f'<font color="{type_info["color"]}" size="8"><i>({type_info["label"]})</i></font>',
                s_body,
            ))
        story.append(Spacer(1, 8))

    # ── BU Sections ────────────────────────────────────────────────
    for section in context.get("bu_sections", []):
        bu_name = section.get("bu_name", "Unknown")
        bu_color = section.get("bu_color", BLUE)

        # BU header bar
        bu_header = Table(
            [[Paragraph(bu_name, s_bu_head)]],
            colWidths=[W],
        )
        bu_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(bu_color)),
            ("TOPPADDING", (0, 0), (0, 0), 7),
            ("BOTTOMPADDING", (0, 0), (0, 0), 7),
            ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        story.append(bu_header)
        story.append(Spacer(1, 6))

        for signal in section.get("signals", []):
            story.append(_make_signal_card(signal))
            story.append(Spacer(1, 6))

    # ── Footer ─────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor(LIGHT_TEXT), spaceAfter=6))
    story.append(Paragraph(
        f"Powered by VPG Strategic Intelligence &bull; "
        f"Auto-generated from {total} validated industry signals &bull; "
        f"Week {week}, {year}",
        s_footer,
    ))

    doc.build(story)
    return output_path


def _generate_with_weasyprint(html: str, output_path: Path,
                              cid_images: dict | None = None) -> Path:
    """Generate PDF using weasyprint (full CSS support)."""
    from weasyprint import HTML
    pdf_html = html
    if cid_images:
        for cid, img_data in cid_images.items():
            data_uri = img_data.get("data_uri", "")
            if data_uri:
                pdf_html = pdf_html.replace(f"cid:{cid}", data_uri)
    HTML(string=pdf_html).write_pdf(str(output_path))
    return output_path


def generate_pdf(
    html: str,
    context: dict,
    output_dir: Path,
    filename: str | None = None,
    cid_images: dict | None = None,
) -> Path:
    """Generate a PDF version of the digest.

    Tries reportlab first (our custom professional layout), falls back
    to weasyprint (HTML-to-PDF) if reportlab is unavailable.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        week = context.get("week_number", 0)
        year = context.get("year", 0)
        filename = f"digest-{year}-W{week:02d}.pdf"

    output_path = output_dir / filename

    # Prefer reportlab (our custom designed layout)
    try:
        result = _generate_with_reportlab(context, output_path)
        logger.info("PDF generated with reportlab: %s", result)
        return result
    except ImportError:
        logger.info("reportlab not available, trying weasyprint")
    except Exception as e:
        logger.warning("reportlab failed: %s — trying weasyprint", e)

    # Fall back to weasyprint (HTML rendering)
    try:
        result = _generate_with_weasyprint(html, output_path, cid_images)
        logger.info("PDF generated with weasyprint: %s", result)
        return result
    except ImportError:
        logger.error("Neither reportlab nor weasyprint available")
        raise RuntimeError(
            "PDF generation requires reportlab or weasyprint. "
            "Install with: pip install reportlab"
        )
    except Exception as e:
        logger.error("PDF generation failed: %s", e)
        raise
