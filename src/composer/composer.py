"""Digest composer for VPG Intelligence Digest.

Generates responsive HTML email digests from scored signals.
"""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import TEMPLATES_DIR

logger = logging.getLogger(__name__)


def get_template_env() -> Environment:
    """Create Jinja2 template environment."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )


def get_week_number() -> tuple[int, int]:
    """Get current ISO week number and year."""
    now = datetime.now()
    iso = now.isocalendar()
    return iso[1], iso[0]


def build_digest_context(signals: list[dict], bu_config: dict) -> dict:
    """Build the template context for a digest.

    Args:
        signals: List of scored signal dicts (with analysis attached).
        bu_config: Business units configuration.

    Returns:
        Template context dict.
    """
    week_num, year = get_week_number()

    # Group signals by BU
    bu_signals = {}
    for signal in signals:
        for bu_match in signal.get("bu_matches", []):
            bu_id = bu_match["bu_id"]
            if bu_id not in bu_signals:
                bu_signals[bu_id] = []
            bu_signals[bu_id].append(signal)

    # Sort signals within each BU by composite score
    for bu_id in bu_signals:
        bu_signals[bu_id].sort(
            key=lambda s: s.get("composite_score", 0), reverse=True
        )

    # Top signals for executive summary
    all_sorted = sorted(signals, key=lambda s: s.get("composite_score", 0), reverse=True)
    top_signals = all_sorted[:5]
    signal_of_week = all_sorted[0] if all_sorted else None

    # Build BU lookup
    bu_lookup = {bu["id"]: bu for bu in bu_config.get("business_units", [])}

    # Build BU sections (only BUs with signals)
    bu_sections = []
    for bu_id, sigs in bu_signals.items():
        bu_info = bu_lookup.get(bu_id, {})
        bu_sections.append({
            "bu_id": bu_id,
            "bu_name": bu_info.get("name", bu_id),
            "bu_color": bu_info.get("color", "#2E75B6"),
            "signals": sigs,
        })

    # Subject line
    top_headline = top_signals[0].get("headline", "Industry Update") if top_signals else "Industry Update"
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
        "top_signals": top_signals,
        "signal_of_week": signal_of_week,
        "bu_sections": bu_sections,
        "colors": {
            "navy": "#1B2A4A",
            "blue": "#2E75B6",
            "accent": "#E8792F",
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
