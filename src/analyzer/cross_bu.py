"""Cross-BU opportunity matching for VPG Intelligence Digest.

Identifies signals that span 2+ business units and generates "Did You Know?"
briefs showing how combined VPG solutions create differentiated value
propositions that no single competitor can match.
"""

import logging
from collections import defaultdict
from datetime import datetime

from src.config import get_business_units
from src.db import get_connection

logger = logging.getLogger(__name__)

# Cross-BU solution combinations with value propositions
CROSS_BU_SOLUTIONS = {
    frozenset(["vpg-force-sensors", "vpg-onboard-weighing"]): {
        "title": "Complete Vehicle Weighing & Force Measurement",
        "value_prop": "VPG is the only company offering both precision force sensors and integrated onboard weighing systems, enabling fleet operators to optimize payload accuracy from sensor to dashboard.",
    },
    frozenset(["micro-measurements", "pacific-instruments"]): {
        "title": "End-to-End Structural Test Solutions",
        "value_prop": "Combining Micro-Measurements strain gages with Pacific Instruments DAQ creates a turnkey test system that competitors can only replicate by stitching together multiple vendors.",
    },
    frozenset(["dts", "micro-measurements"]): {
        "title": "Complete Crash Test & Structural Analysis",
        "value_prop": "DTS miniature crash test DAQ paired with Micro-Measurements strain gages provides the most comprehensive crash test data acquisition solution available from a single vendor.",
    },
    frozenset(["kelk", "blh-nobel"]): {
        "title": "Integrated Metals Processing Measurement",
        "value_prop": "KELK rolling mill systems with BLH Nobel process weighing covers the complete metals processing measurement chain, from raw material to finished product.",
    },
    frozenset(["vpg-force-sensors", "vpg-foil-resistors"]): {
        "title": "Precision Sensing From Sensor to Circuit",
        "value_prop": "VPG's foil technology underpins both force sensors and precision resistors, offering unmatched consistency and precision across the entire measurement signal chain.",
    },
    frozenset(["vpg-force-sensors", "blh-nobel"]): {
        "title": "Full-Spectrum Weighing Solutions",
        "value_prop": "From individual load cells to complete process weighing systems, VPG covers every scale of industrial weighing with a single, integrated product family.",
    },
    frozenset(["dts", "pacific-instruments"]): {
        "title": "Defense & Aerospace Test Data Acquisition",
        "value_prop": "DTS miniature DAQ for field/ballistic testing combined with Pacific Instruments high-channel lab DAQ provides defense customers a complete test infrastructure from one supplier.",
    },
    frozenset(["micro-measurements", "gleeble"]): {
        "title": "Materials Research & Testing Ecosystem",
        "value_prop": "Gleeble thermal-mechanical simulation systems paired with Micro-Measurements strain gages create a comprehensive materials characterization platform for research institutions.",
    },
}


def find_cross_bu_opportunities(conn=None) -> dict:
    """Identify signals relevant to multiple BUs and generate cross-sell briefs.

    Returns:
        Dict with cross-BU opportunities, each containing the signal,
        affected BUs, and a 'Did You Know?' brief.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        bu_config = get_business_units()
        bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

        # Find signals mapped to 2+ BUs
        rows = conn.execute("""
            SELECT s.id, sa.headline, sa.signal_type, sa.score_composite,
                   sa.what_summary, sa.why_it_matters, sa.quick_win,
                   s.url, s.collected_at,
                   GROUP_CONCAT(sb.bu_id) as bu_ids
            FROM signals s
            JOIN signal_analysis sa ON s.id = sa.signal_id
            JOIN signal_bus sb ON s.id = sb.signal_id
            WHERE s.status IN ('scored', 'published')
            GROUP BY s.id
            HAVING COUNT(DISTINCT sb.bu_id) >= 2
            ORDER BY sa.score_composite DESC
            LIMIT 20
        """).fetchall()

        opportunities = []
        for row in rows:
            bu_ids = row[9].split(",") if row[9] else []
            bu_set = frozenset(bu_ids)

            # Find matching cross-BU solution
            solution = None
            for combo_key, combo_val in CROSS_BU_SOLUTIONS.items():
                if combo_key.issubset(bu_set):
                    solution = combo_val
                    break

            affected_bus = [{"id": bid, "name": bu_names.get(bid, bid)} for bid in bu_ids]

            opp = {
                "signal_id": row[0],
                "headline": row[1],
                "signal_type": row[2],
                "score": row[3],
                "summary": row[4],
                "why_it_matters": row[5],
                "quick_win": row[6],
                "url": row[7],
                "date": row[8],
                "affected_bus": affected_bus,
                "bu_count": len(bu_ids),
            }

            if solution:
                opp["did_you_know"] = {
                    "title": solution["title"],
                    "value_proposition": solution["value_prop"],
                    "combined_bus": [bu_names.get(bid, bid) for bid in bu_ids],
                }
            else:
                opp["did_you_know"] = {
                    "title": f"Cross-BU Opportunity: {' + '.join(bu_names.get(b, b) for b in bu_ids[:3])}",
                    "value_proposition": f"This signal spans {len(bu_ids)} VPG business units, presenting a combined solution opportunity that single-product competitors cannot match.",
                    "combined_bus": [bu_names.get(bid, bid) for bid in bu_ids],
                }

            opportunities.append(opp)

        return {
            "opportunities": opportunities,
            "total": len(opportunities),
            "analyzed_at": datetime.now().isoformat(),
        }

    finally:
        if close_conn:
            conn.close()


def get_cross_bu_for_digest(signals: list[dict], bu_config: dict) -> list[dict]:
    """Extract cross-BU opportunities from a list of signals for digest inclusion.

    This is called during digest composition to generate the Cross-BU section.
    """
    bu_names = {bu["id"]: bu["name"] for bu in bu_config.get("business_units", [])}

    cross_bu = []
    for sig in signals:
        bu_matches = sig.get("bu_matches", [])
        if len(bu_matches) < 2:
            continue

        bu_ids = [m["bu_id"] for m in bu_matches]
        bu_set = frozenset(bu_ids)

        solution = None
        for combo_key, combo_val in CROSS_BU_SOLUTIONS.items():
            if combo_key.issubset(bu_set):
                solution = combo_val
                break

        entry = {
            "headline": sig.get("headline", sig.get("title", "")),
            "score": sig.get("composite_score", 0),
            "bus": [bu_names.get(b, b) for b in bu_ids],
            "signal_type": sig.get("signal_type", ""),
        }

        if solution:
            entry["did_you_know"] = solution["title"]
            entry["value_prop"] = solution["value_prop"]
        else:
            entry["did_you_know"] = f"Spans {len(bu_ids)} BUs"
            entry["value_prop"] = f"Combined VPG solution opportunity across {', '.join(bu_names.get(b, b) for b in bu_ids[:3])}."

        cross_bu.append(entry)

    return sorted(cross_bu, key=lambda x: x.get("score", 0), reverse=True)[:5]
