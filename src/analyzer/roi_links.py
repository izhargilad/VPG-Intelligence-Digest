"""ROI Quick-Calc link generator for VPG Intelligence Digest.

For signals where VPG can demonstrate quantifiable value, auto-generates
links to relevant ROI calculators, TCO comparison tools, and value
proposition assets.
"""

import logging

logger = logging.getLogger(__name__)

# ROI calculators and value tools per BU/product area
ROI_TOOLS = {
    "kelk": {
        "tools": [
            {
                "name": "KELK TCO Savings Calculator",
                "description": "Total cost of ownership comparison vs. X-ray thickness measurement",
                "url_template": "/tools/kelk-tco-calculator",
                "keywords": ["thickness", "x-ray", "laser", "nokra", "alpha.ti", "rolling mill", "tco"],
            },
            {
                "name": "Rolling Mill ROI Estimator",
                "description": "Estimate productivity gains from KELK measurement systems",
                "url_template": "/tools/rolling-mill-roi",
                "keywords": ["rolling mill", "productivity", "yield", "quality", "scrap"],
            },
        ],
    },
    "vpg-onboard-weighing": {
        "tools": [
            {
                "name": "Fleet Weighing ROI Calculator",
                "description": "Calculate savings from onboard weighing vs. static scales",
                "url_template": "/tools/fleet-weighing-roi",
                "keywords": ["fleet", "overload", "payload", "compliance", "fine", "weighbridge"],
            },
            {
                "name": "Payload Optimization Tool",
                "description": "Model revenue increase from optimized payload per trip",
                "url_template": "/tools/payload-optimizer",
                "keywords": ["payload", "optimization", "trip", "efficiency", "utilization"],
            },
        ],
    },
    "vpg-force-sensors": {
        "tools": [
            {
                "name": "Sensor Precision Cost-Benefit",
                "description": "Compare precision grades and their impact on measurement accuracy",
                "url_template": "/tools/precision-cost-benefit",
                "keywords": ["precision", "accuracy", "measurement", "calibration", "tolerance"],
            },
        ],
    },
    "vpg-foil-resistors": {
        "tools": [
            {
                "name": "Foil vs. Wirewound TCO Comparison",
                "description": "Long-term cost and performance comparison of resistor technologies",
                "url_template": "/tools/foil-vs-wirewound",
                "keywords": ["resistor", "wirewound", "drift", "stability", "mil-spec", "precision"],
            },
        ],
    },
    "blh-nobel": {
        "tools": [
            {
                "name": "Process Weighing Accuracy Calculator",
                "description": "Calculate yield improvement from higher weighing accuracy",
                "url_template": "/tools/process-weighing-accuracy",
                "keywords": ["process", "batch", "yield", "accuracy", "weighing", "dosing"],
            },
        ],
    },
    "dts": {
        "tools": [
            {
                "name": "Crash Test DAQ Cost Comparison",
                "description": "Compare miniature vs. traditional DAQ costs for crash testing",
                "url_template": "/tools/crash-test-daq-comparison",
                "keywords": ["crash test", "daq", "miniature", "channels", "data acquisition"],
            },
        ],
    },
    "micro-measurements": {
        "tools": [
            {
                "name": "Strain Gage Installation Cost Calculator",
                "description": "Calculate total cost per measurement point including installation",
                "url_template": "/tools/strain-gage-cost",
                "keywords": ["strain gage", "installation", "measurement point", "structural"],
            },
        ],
    },
}

# Base URL for ROI tools (configurable)
ROI_BASE_URL = ""  # Set when deployed, e.g., https://vpg-intel.example.com


def get_roi_links(signal: dict) -> list[dict]:
    """Find relevant ROI calculator links for a signal.

    Args:
        signal: Signal dict with bu_matches, headline, what_summary, etc.

    Returns:
        List of ROI tool links relevant to this signal.
    """
    text = f"{signal.get('headline', '')} {signal.get('what_summary', '')} {signal.get('title', '')}".lower()
    bu_ids = [m["bu_id"] for m in signal.get("bu_matches", [])]

    links = []
    seen = set()

    for bu_id in bu_ids:
        bu_tools = ROI_TOOLS.get(bu_id, {}).get("tools", [])
        for tool in bu_tools:
            if tool["name"] in seen:
                continue
            # Check if any keyword matches the signal text
            if any(kw in text for kw in tool["keywords"]):
                links.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "url": f"{ROI_BASE_URL}{tool['url_template']}",
                    "bu_id": bu_id,
                })
                seen.add(tool["name"])

    return links


def enrich_signals_with_roi(signals: list[dict]) -> list[dict]:
    """Add ROI links to signals where applicable.

    Modifies signals in-place, adding a 'roi_links' key where relevant.
    Returns the enriched signals list.
    """
    for sig in signals:
        roi = get_roi_links(sig)
        if roi:
            sig["roi_links"] = roi
    return signals
