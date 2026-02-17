"""Digest composer for VPG Intelligence Digest.

Generates responsive HTML email digests from scored signals.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

from src.config import TEMPLATES_DIR

logger = logging.getLogger(__name__)

# Signal type color scheme — professional, blue-centric, no orange/yellow
SIGNAL_TYPE_COLORS = {
    "competitive-threat": {"color": "#B71C1C", "bg": "#FDE8E8", "icon": "\u26a0"},
    "revenue-opportunity": {"color": "#1B5E20", "bg": "#E6F4EA", "icon": "\U0001f4b0"},
    "market-shift": {"color": "#0D47A1", "bg": "#E3F2FD", "icon": "\U0001f3af"},
    "partnership-signal": {"color": "#006064", "bg": "#E0F2F1", "icon": "\U0001f91d"},
    "customer-intelligence": {"color": "#4A148C", "bg": "#F3E5F5", "icon": "\U0001f4ca"},
    "technology-trend": {"color": "#01579B", "bg": "#E1F5FE", "icon": "\U0001f680"},
    "trade-tariff": {"color": "#263238", "bg": "#ECEFF1", "icon": "\U0001f30d"},
}

_DEFAULT_TYPE = {"color": "#2E75B6", "bg": "#E3F2FD", "icon": "\U0001f4cb"}


def _to_bullets(text):
    """Jinja2 filter: convert paragraph text to an HTML bullet list.

    Splits on sentence boundaries and renders as <ul> when there are
    multiple sentences. Returns escaped Markup for XSS safety.
    """
    if not text:
        return ""
    safe = str(escape(text))
    # Split on sentence-ending punctuation followed by whitespace
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", safe) if s.strip()]
    if len(parts) <= 1:
        return Markup(safe)
    items = "".join(f"<li>{s}</li>" for s in parts)
    return Markup(
        f'<ul style="margin:4px 0;padding-left:18px;">{items}</ul>'
    )


def get_template_env() -> Environment:
    """Create Jinja2 template environment with custom filters."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["to_bullets"] = _to_bullets
    return env


def get_week_number() -> tuple[int, int]:
    """Get current ISO week number and year."""
    now = datetime.now()
    iso = now.isocalendar()
    return iso[1], iso[0]


def build_digest_context(signals: list[dict], bu_config: dict) -> dict:
    """Build the template context for a digest.

    Handles:
    - Signal-of-the-week extraction (shown once at top, excluded from BU sections)
    - Cross-BU deduplication (signal shown once with "Also relevant to" tag)
    - Anchor IDs for in-email navigation from executive summary to detail cards
    - Signal type color assignment
    """
    week_num, year = get_week_number()

    # Sort all signals by composite score descending
    all_sorted = sorted(
        signals, key=lambda s: s.get("composite_score", 0), reverse=True
    )

    # Assign anchor IDs and pre-compute signal type colors
    for i, signal in enumerate(all_sorted):
        signal["anchor_id"] = str(i)
        type_info = SIGNAL_TYPE_COLORS.get(
            signal.get("signal_type", ""), _DEFAULT_TYPE
        )
        signal["type_color"] = type_info["color"]
        signal["type_bg"] = type_info["bg"]
        signal["type_icon"] = type_info["icon"]

    # Signal of the week = top signal (shown once, not repeated)
    signal_of_week = all_sorted[0] if all_sorted else None

    # Top signals for exec summary (exclude signal of the week)
    top_signals = all_sorted[1:6]

    # Group signals by BU
    bu_signals: dict[str, list[dict]] = {}
    for signal in signals:
        for bu_match in signal.get("bu_matches", []):
            bu_id = bu_match["bu_id"]
            bu_signals.setdefault(bu_id, []).append(signal)

    for bu_id in bu_signals:
        bu_signals[bu_id].sort(
            key=lambda s: s.get("composite_score", 0), reverse=True
        )

    bu_lookup = {bu["id"]: bu for bu in bu_config.get("business_units", [])}

    # Build BU sections with cross-BU deduplication
    seen_ids: set[int] = set()
    # Exclude signal of the week from BU sections
    if signal_of_week is not None:
        seen_ids.add(id(signal_of_week))

    bu_sections = []
    for bu_id, sigs in bu_signals.items():
        bu_info = bu_lookup.get(bu_id, {})
        deduped = []
        for sig in sigs:
            sig_identity = id(sig)
            if sig_identity in seen_ids:
                continue
            seen_ids.add(sig_identity)
            # Mark cross-BU relevance
            other_bus = [
                bu_lookup.get(m["bu_id"], {}).get("name", m["bu_id"])
                for m in sig.get("bu_matches", [])
                if m["bu_id"] != bu_id
            ]
            if other_bus:
                sig["also_relevant_to"] = other_bus
            deduped.append(sig)
        if deduped:
            bu_sections.append({
                "bu_id": bu_id,
                "bu_name": bu_info.get("name", bu_id),
                "bu_color": bu_info.get("color", "#2E75B6"),
                "bu_logo_url": bu_info.get("logo_url", ""),
                "signals": deduped,
            })

    # Sort BU sections by highest signal score
    bu_sections.sort(
        key=lambda s: max(
            (sig.get("composite_score", 0) for sig in s["signals"]),
            default=0,
        ),
        reverse=True,
    )

    # Branding config
    branding = bu_config.get("branding", {
        "logo_url": "",
        "company_name": "VPG",
    })

    # Subject line
    top_headline = (
        signal_of_week.get("headline", "Industry Update")
        if signal_of_week
        else "Industry Update"
    )
    remaining = max(len(signals) - 1, 0)
    subject = f"VPG Intel [Week {week_num}]: {top_headline}"
    if remaining > 0:
        subject += f" + {remaining} more signals"

    return {
        "subject": subject,
        "week_number": week_num,
        "year": year,
        "date_range": datetime.now().strftime("%B %d, %Y"),
        "total_signals": len(signals),
        "bu_count": len(bu_sections),
        "top_signals": top_signals,
        "signal_of_week": signal_of_week,
        "bu_sections": bu_sections,
        "branding": branding,
        "colors": {
            "navy": "#1B2A4A",
            "blue": "#2E75B6",
        },
    }


def render_digest(context: dict) -> str:
    """Render the digest HTML from the template context."""
    env = get_template_env()
    template = env.get_template("digest.html")
    return template.render(**context)


def save_digest_html(html: str, output_dir: Path, filename: str | None = None) -> Path:
    """Save rendered digest HTML to a file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        week_num, year = get_week_number()
        filename = f"digest-{year}-W{week_num:02d}.html"

    path = output_dir / filename
    path.write_text(html, encoding="utf-8")
    logger.info("Digest saved to %s", path)
    return path
