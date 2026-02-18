"""Digest composer for VPG Intelligence Digest.

Generates responsive HTML email digests from scored signals.
Supports two image modes:
- CID mode (default): Images embedded as MIME attachments with Content-ID
  references. Works in Outlook, corporate Exchange, Gmail, Apple Mail.
- Data URI mode (fallback): Base64 inline images. Works in webmail/browsers
  but blocked by many corporate mail clients.
"""

import base64
import io
import logging
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape
from PIL import Image

from src.config import CONFIG_DIR, TEMPLATES_DIR

logger = logging.getLogger(__name__)

# Logo sizing — widths in pixels
HEADER_LOGO_WIDTH = 220
BU_LOGO_HEIGHT = 34

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

# Score threshold for highlighting
HIGH_SCORE_THRESHOLD = 9.0


def _process_logo(logo_filename: str, max_height: int | None = None,
                  max_width: int | None = None) -> dict | None:
    """Load a logo file from config dir, resize, and return image data.

    Returns a dict with 'bytes', 'cid', 'data_uri', and 'filename' keys,
    or None if the logo cannot be loaded.
    """
    if not logo_filename:
        return None
    logo_path = CONFIG_DIR / logo_filename
    if not logo_path.exists():
        logger.warning("Logo file not found: %s", logo_path)
        return None
    try:
        img = Image.open(logo_path)
        img = img.convert("RGB")
        # Resize proportionally
        w, h = img.size
        if max_width and w > max_width:
            ratio = max_width / w
            img = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
            w, h = img.size
        if max_height and h > max_height:
            ratio = max_height / h
            img = img.resize((int(w * ratio), max_height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        img_bytes = buf.getvalue()
        b64 = base64.b64encode(img_bytes).decode("ascii")
        # CID = sanitized filename without extension
        cid = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(logo_filename).stem).lower()
        return {
            "bytes": img_bytes,
            "cid": cid,
            "data_uri": f"data:image/jpeg;base64,{b64}",
            "cid_uri": f"cid:{cid}",
            "filename": logo_filename,
        }
    except Exception as e:
        logger.warning("Failed to process logo %s: %s", logo_filename, e)
        return None


def _logo_to_data_uri(logo_filename: str, max_height: int | None = None,
                      max_width: int | None = None) -> str:
    """Load a logo and return a base64 data URI (legacy compatibility)."""
    result = _process_logo(logo_filename, max_height, max_width)
    return result["data_uri"] if result else ""


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
    - CID image collection for MIME embedding
    """
    week_num, year = get_week_number()

    # Collect CID images for MIME attachment (used by delivery layer)
    cid_images: dict[str, dict] = {}

    # Sort all signals by composite score descending
    all_sorted = sorted(
        signals, key=lambda s: s.get("composite_score", 0), reverse=True
    )

    # Assign anchor IDs, pre-compute signal type colors, and flag high scores
    for i, signal in enumerate(all_sorted):
        signal["anchor_id"] = str(i)
        type_info = SIGNAL_TYPE_COLORS.get(
            signal.get("signal_type", ""), _DEFAULT_TYPE
        )
        signal["type_color"] = type_info["color"]
        signal["type_bg"] = type_info["bg"]
        signal["type_icon"] = type_info["icon"]
        signal["high_score"] = signal.get("composite_score", 0) >= HIGH_SCORE_THRESHOLD

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

    # Pre-process BU logos — collect both CID and data URI versions
    bu_logo_cache: dict[str, str] = {}
    for bu in bu_config.get("business_units", []):
        logo_file = bu.get("logo_file", "")
        if logo_file:
            logo_data = _process_logo(logo_file, max_height=BU_LOGO_HEIGHT)
            if logo_data:
                cid_images[logo_data["cid"]] = logo_data
                bu_logo_cache[bu["id"]] = logo_data["cid_uri"]

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
                "bu_logo_url": bu_logo_cache.get(bu_id, ""),
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

    # Branding config — process header logo
    branding = bu_config.get("branding", {
        "logo_url": "",
        "company_name": "VPG",
    })
    header_logo_file = branding.get("logo_file", "")
    if header_logo_file:
        logo_data = _process_logo(header_logo_file, max_width=HEADER_LOGO_WIDTH)
        if logo_data:
            cid_images[logo_data["cid"]] = logo_data
            branding["logo_url"] = logo_data["cid_uri"]

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
        "cid_images": cid_images,
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
