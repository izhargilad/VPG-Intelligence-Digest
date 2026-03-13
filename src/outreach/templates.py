"""One-click outreach template generator for VPG Intelligence Digest.

For 'Revenue Opportunity' and other actionable signals, generates
pre-drafted outreach messages (email + LinkedIn) that salespeople
can personalize and send directly.

Templates are tied to signal types and BU context.
"""

import logging
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)


# Signal type → outreach template mapping
OUTREACH_TEMPLATES = {
    "revenue-opportunity": {
        "email_subject": "VPG Solutions for {headline_short}",
        "email_body": """Hi {contact_name},

I noticed {signal_context}. At VPG's {bu_name} division, we've been helping companies in {industry} with {product_capabilities}.

Given your recent {trigger}, I thought it would be valuable to share how our {key_product} could support your objectives — particularly around {value_proposition}.

Would you have 15 minutes this week for a brief call?

Best regards,
{sender_name}
{bu_name} | Vishay Precision Group""",
        "linkedin_message": """Hi {contact_name} — I saw {signal_context}. At VPG {bu_name}, we specialize in {product_capabilities} for {industry}. Given {trigger}, I'd love to share how we could help. Open to a quick chat?""",
    },
    "customer-intelligence": {
        "email_subject": "Checking In — {headline_short}",
        "email_body": """Hi {contact_name},

I saw the news about {signal_context}. Congratulations on {trigger}.

As your VPG account team, we wanted to reach out to discuss how this development might impact your {product_area} requirements. We've recently enhanced our {key_product} capabilities and believe there may be an opportunity to support your expanded needs.

Shall we schedule a brief review call?

Best regards,
{sender_name}
{bu_name} | Vishay Precision Group""",
        "linkedin_message": """Hi {contact_name} — Great to see {signal_context}. As your VPG {bu_name} partner, I'd like to discuss how we can support your evolving needs. Time for a quick catch-up?""",
    },
    "partnership-signal": {
        "email_subject": "Partnership Opportunity — {headline_short}",
        "email_body": """Hi {contact_name},

I noticed {signal_context}. VPG's {bu_name} division has deep expertise in {product_capabilities}, and I see strong alignment with your {trigger}.

A combined solution leveraging our {key_product} alongside your capabilities could create a differentiated offering for {industry} customers.

Would you be open to an exploratory conversation?

Best regards,
{sender_name}
{bu_name} | Vishay Precision Group""",
        "linkedin_message": """Hi {contact_name} — Noticed {signal_context}. VPG {bu_name} has complementary capabilities in {product_capabilities}. I see potential for a compelling joint offering. Interested in exploring?""",
    },
    "competitive-threat": {
        "email_subject": "Why VPG for {headline_short}",
        "email_body": """Hi {contact_name},

As you evaluate options for {trigger}, I wanted to highlight some key advantages of VPG's {bu_name} solutions:

• {value_proposition}
• India-based manufacturing for supply chain resilience and competitive pricing
• {product_capabilities}

I'd welcome the chance to demonstrate our {key_product} capabilities and discuss how we compare.

Best regards,
{sender_name}
{bu_name} | Vishay Precision Group""",
        "linkedin_message": """Hi {contact_name} — As you consider {trigger}, I'd love to share how VPG {bu_name} compares. Our India manufacturing gives us strong pricing and delivery. Quick chat?""",
    },
}


def generate_outreach(signal_id: int, conn=None) -> dict:
    """Generate outreach templates for a specific signal.

    Args:
        signal_id: ID of the scored signal.
        conn: DB connection.

    Returns:
        Dict with email and LinkedIn templates, plus signal context.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        # Fetch signal and analysis
        row = conn.execute("""
            SELECT s.id, s.title, s.summary, s.url, s.source_name,
                   sa.signal_type, sa.headline, sa.what_summary,
                   sa.why_it_matters, sa.quick_win, sa.estimated_impact,
                   sa.suggested_owner,
                   GROUP_CONCAT(DISTINCT sb.bu_id) as bus
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            LEFT JOIN signal_bus sb ON s.id = sb.signal_id
            WHERE s.id = ?
            GROUP BY s.id
        """, (signal_id,)).fetchone()

        if not row:
            return {"error": f"Signal {signal_id} not found"}

        signal_data = dict(row)
        signal_type = signal_data["signal_type"]
        bus = (signal_data.get("bus") or "").split(",")
        primary_bu = bus[0] if bus else ""

        # Get BU details
        bu_config = get_business_units()
        bu_info = next(
            (bu for bu in bu_config.get("business_units", []) if bu["id"] == primary_bu),
            {},
        )

        # Build template variables
        template_vars = {
            "contact_name": "[Contact Name]",
            "sender_name": "[Your Name]",
            "headline_short": (signal_data.get("headline") or signal_data["title"])[:60],
            "signal_context": _summarize_for_outreach(signal_data),
            "bu_name": bu_info.get("short_name", bu_info.get("name", "VPG")),
            "industry": ", ".join(bu_info.get("core_industries", [])[:2]) or "your industry",
            "product_capabilities": ", ".join(bu_info.get("key_products", [])[:3]) or "precision measurement solutions",
            "key_product": bu_info.get("key_products", ["solutions"])[0],
            "value_proposition": _get_value_prop(signal_type, bu_info),
            "trigger": _extract_trigger(signal_data),
            "product_area": bu_info.get("key_products", ["measurement"])[0].lower(),
        }

        # Get the template set for this signal type
        template_set = OUTREACH_TEMPLATES.get(signal_type, OUTREACH_TEMPLATES["revenue-opportunity"])

        return {
            "signal_id": signal_id,
            "signal_type": signal_type,
            "headline": signal_data.get("headline", signal_data["title"]),
            "bu": primary_bu,
            "bu_name": template_vars["bu_name"],
            "templates": {
                "email": {
                    "subject": template_set["email_subject"].format(**template_vars),
                    "body": template_set["email_body"].format(**template_vars),
                },
                "linkedin": {
                    "message": template_set["linkedin_message"].format(**template_vars),
                },
            },
            "context": {
                "source_url": signal_data.get("url", ""),
                "source": signal_data.get("source_name", ""),
                "estimated_impact": signal_data.get("estimated_impact", ""),
                "quick_win": signal_data.get("quick_win", ""),
                "owner": signal_data.get("suggested_owner", ""),
            },
            "generated_at": datetime.now().isoformat(),
        }

    finally:
        if close_conn:
            conn.close()


def _summarize_for_outreach(signal_data: dict) -> str:
    """Create a brief, natural-sounding summary for outreach context."""
    headline = signal_data.get("headline", signal_data.get("title", ""))
    what = signal_data.get("what_summary", "")

    if what and len(what) > 50:
        # Use first sentence of what_summary
        first_sentence = what.split(".")[0].strip()
        if len(first_sentence) > 20:
            return first_sentence.lower()

    return headline.lower() if headline else "recent industry developments"


def _extract_trigger(signal_data: dict) -> str:
    """Extract the business trigger from the signal."""
    what = signal_data.get("what_summary", "")
    if what:
        first = what.split(".")[0].strip()
        if len(first) > 20:
            return first.lower()

    return signal_data.get("headline", "recent development").lower()


def _get_value_prop(signal_type: str, bu_info: dict) -> str:
    """Generate a value proposition based on signal type and BU."""
    props = {
        "revenue-opportunity": "Industry-leading precision and reliability backed by decades of innovation",
        "competitive-threat": "Superior precision, India-based manufacturing for cost-competitive pricing, and dedicated application engineering support",
        "customer-intelligence": "Expanded product range and dedicated technical support for growing accounts",
        "partnership-signal": "Deep domain expertise and a global distribution network",
        "technology-trend": "Cutting-edge sensor technology with proven reliability in demanding environments",
        "market-shift": "Agile response capabilities and diversified manufacturing footprint",
        "trade-tariff": "India-based production avoiding China tariff exposure, with competitive lead times",
    }
    return props.get(signal_type, "Industry-leading precision measurement solutions")


def generate_batch_outreach(signal_ids: list[int], conn=None) -> list[dict]:
    """Generate outreach templates for multiple signals."""
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        return [generate_outreach(sid, conn) for sid in signal_ids]
    finally:
        if close_conn:
            conn.close()
