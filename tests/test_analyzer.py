"""Tests for the AI analysis module.

Tests the Anthropic client, prompt generation, scoring, and validation
using mocked API responses.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.client import AnalysisClient
from src.analyzer.prompts import (
    VALID_SIGNAL_TYPES,
    build_signal_prompt,
    build_system_prompt,
    build_batch_prompt,
)
from src.analyzer.scorer import (
    _validate_ai_result,
    calculate_composite_score,
    match_signal_to_bus,
    score_batch_ai,
    score_signal,
    score_signal_ai,
    score_signal_heuristic,
)


# -- Sample data --

SAMPLE_SIGNAL = {
    "title": "Kistler launches new force sensor for humanoid robots",
    "summary": "Kistler Group announced a next-gen force transducer targeting the growing humanoid robotics market, directly competing with VPG Force Sensors.",
    "url": "https://example.com/kistler-robot-sensor",
    "source_id": "kistler-news",
    "source_name": "Kistler Newsroom",
    "source_tier": 2,
    "published_at": "2026-02-15T10:00:00",
}

SAMPLE_AI_RESPONSE = {
    "signal_type": "competitive-threat",
    "relevant_bus": [
        {"bu_id": "vpg-force-sensors", "relevance_score": 0.95},
    ],
    "scores": {
        "revenue_impact": 8,
        "time_sensitivity": 7,
        "strategic_alignment": 9,
        "competitive_pressure": 9,
    },
    "headline": "Kistler targets humanoid robotics with new force sensor",
    "what_summary": "Kistler Group launched a next-gen force transducer designed for humanoid robot applications. This directly competes with VPG Force Sensors' load cell and force transducer portfolio.",
    "why_it_matters": "VPG Force Sensors is a leader in precision force measurement for robotics. Kistler's entry into humanoid-specific sensors could erode VPG's position in this high-growth segment.",
    "quick_win": "Schedule a meeting with the VP Sales - Force Sensors to review VPG's humanoid robotics positioning and prepare a competitive response brief.",
    "suggested_owner": "VP Sales - Force Sensors",
    "estimated_impact": "$500K-$1M annual opportunity at risk",
    "outreach_template": None,
}


# -- Prompt Tests --

class TestPrompts:
    def test_system_prompt_contains_all_bus(self):
        prompt = build_system_prompt()
        assert "VPG Force Sensors" in prompt
        assert "VPG Foil Resistors" in prompt
        assert "Micro-Measurements" in prompt
        assert "VPG Onboard Weighing" in prompt
        assert "BLH Nobel" in prompt
        assert "KELK" in prompt
        assert "Gleeble" in prompt
        assert "Pacific Instruments" in prompt
        assert "DTS" in prompt

    def test_system_prompt_contains_strategic_context(self):
        prompt = build_system_prompt()
        assert "India" in prompt
        assert "Caterpillar" in prompt
        assert "Humanetics" in prompt
        assert "alpha.ti" in prompt

    def test_signal_prompt_contains_signal_data(self):
        prompt = build_signal_prompt(SAMPLE_SIGNAL)
        assert "Kistler" in prompt
        assert "humanoid" in prompt
        assert "revenue_impact" in prompt
        assert "signal_type" in prompt

    def test_signal_prompt_contains_scoring_criteria(self):
        prompt = build_signal_prompt(SAMPLE_SIGNAL)
        assert "revenue_impact" in prompt
        assert "time_sensitivity" in prompt
        assert "strategic_alignment" in prompt
        assert "competitive_pressure" in prompt

    def test_batch_prompt_contains_all_signals(self):
        signals = [SAMPLE_SIGNAL, {**SAMPLE_SIGNAL, "title": "Second signal about steel mills"}]
        prompt = build_batch_prompt(signals)
        assert "Signal 1" in prompt
        assert "Signal 2" in prompt
        assert "Kistler" in prompt
        assert "steel mills" in prompt


# -- Client Tests --

class TestAnalysisClient:
    def test_client_unavailable_without_key(self):
        with patch("src.analyzer.client._read_auth_token", return_value=None):
            client = AnalysisClient(api_key="")
            assert not client.available

    def test_client_available_with_key(self):
        with patch("src.analyzer.client.anthropic.Anthropic"):
            client = AnalysisClient(api_key="test-key")
            assert client.available

    def test_analyze_returns_none_when_unavailable(self):
        with patch("src.analyzer.client._read_auth_token", return_value=None):
            client = AnalysisClient(api_key="")
        result = client.analyze("system", "user")
        assert result is None

    def test_parse_json_from_plain_text(self):
        text = json.dumps({"key": "value"})
        result = AnalysisClient._parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_json_from_markdown_fence(self):
        text = '```json\n{"key": "value"}\n```'
        result = AnalysisClient._parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_json_invalid_returns_none(self):
        result = AnalysisClient._parse_json_response("not json at all")
        assert result is None

    def test_analyze_with_mocked_api(self):
        with patch("src.analyzer.client.anthropic.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps(SAMPLE_AI_RESPONSE))]
            mock_client.messages.create.return_value = mock_response

            client = AnalysisClient(api_key="test-key")
            result = client.analyze("system prompt", "user prompt")

            assert result is not None
            assert result["signal_type"] == "competitive-threat"
            mock_client.messages.create.assert_called_once()


# -- Validation Tests --

class TestValidation:
    def test_valid_result_passes(self):
        result = _validate_ai_result(SAMPLE_AI_RESPONSE.copy())
        assert result is not None
        assert result["signal_type"] == "competitive-threat"

    def test_invalid_signal_type_defaults(self):
        data = SAMPLE_AI_RESPONSE.copy()
        data["signal_type"] = "invalid-type"
        result = _validate_ai_result(data)
        assert result["signal_type"] == "market-shift"

    def test_missing_bus_returns_none(self):
        data = SAMPLE_AI_RESPONSE.copy()
        data["relevant_bus"] = []
        result = _validate_ai_result(data)
        assert result is None

    def test_scores_clamped_to_range(self):
        data = SAMPLE_AI_RESPONSE.copy()
        data["scores"] = {
            "revenue_impact": 15,  # Over max
            "time_sensitivity": -3,  # Under min
            "strategic_alignment": 5.7,  # Float
            "competitive_pressure": 0,  # Under min
        }
        result = _validate_ai_result(data)
        assert result["scores"]["revenue_impact"] == 10
        assert result["scores"]["time_sensitivity"] == 1
        assert result["scores"]["strategic_alignment"] == 6
        assert result["scores"]["competitive_pressure"] == 1

    def test_non_dict_returns_none(self):
        assert _validate_ai_result("not a dict") is None
        assert _validate_ai_result(None) is None
        assert _validate_ai_result([]) is None

    def test_missing_text_fields_get_defaults(self):
        data = {
            "signal_type": "revenue-opportunity",
            "relevant_bus": [{"bu_id": "kelk", "relevance_score": 0.8}],
            "scores": {
                "revenue_impact": 7,
                "time_sensitivity": 6,
                "strategic_alignment": 8,
                "competitive_pressure": 4,
            },
        }
        result = _validate_ai_result(data)
        assert result is not None
        assert result["headline"] == "Industry Signal Detected"
        assert result["quick_win"] == "Review signal and assess BU impact."


# -- Scorer Tests --

class TestScorer:
    def test_composite_score_calculation(self):
        scores = {
            "revenue_impact": 8,
            "time_sensitivity": 6,
            "strategic_alignment": 7,
            "competitive_pressure": 5,
        }
        composite = calculate_composite_score(scores)
        # 8*0.35 + 6*0.25 + 7*0.25 + 5*0.15 = 2.8 + 1.5 + 1.75 + 0.75 = 6.8
        assert abs(composite - 6.8) < 0.01

    def test_match_signal_to_bus_finds_force_sensors(self):
        matches = match_signal_to_bus(SAMPLE_SIGNAL)
        assert len(matches) > 0
        assert matches[0]["bu_id"] == "vpg-force-sensors"

    def test_heuristic_scoring_returns_all_fields(self):
        result = score_signal_heuristic(SAMPLE_SIGNAL)
        assert "scores" in result
        assert "composite" in result
        assert "bu_matches" in result
        assert "signal_type" in result
        assert "headline" in result
        assert "quick_win" in result
        assert result["analysis_method"] == "heuristic"

    def test_score_signal_falls_back_to_heuristic(self):
        """Without API key, score_signal should use heuristic fallback."""
        with patch("src.analyzer.scorer._get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.available = False
            mock_get.return_value = mock_client

            result = score_signal(SAMPLE_SIGNAL)
            assert result["analysis_method"] == "heuristic"

    def test_score_signal_uses_ai_when_available(self):
        """With a mocked API response, score_signal should use AI."""
        mock_client = MagicMock(spec=AnalysisClient)
        mock_client.available = True
        mock_client.analyze.return_value = SAMPLE_AI_RESPONSE.copy()

        result = score_signal_ai(SAMPLE_SIGNAL, client=mock_client)

        assert result is not None
        assert result["analysis_method"] == "ai"
        assert result["signal_type"] == "competitive-threat"
        assert result["composite"] > 0

    def test_score_batch_with_unavailable_client(self):
        """Batch scoring falls back to heuristic when API unavailable."""
        mock_client = MagicMock(spec=AnalysisClient)
        mock_client.available = False

        signals = [SAMPLE_SIGNAL, SAMPLE_SIGNAL]
        results = score_batch_ai(signals, client=mock_client)

        assert len(results) == 2
        assert all(r["analysis_method"] == "heuristic" for r in results)

    def test_all_valid_signal_types(self):
        expected = {
            "competitive-threat", "revenue-opportunity", "market-shift",
            "partnership-signal", "customer-intelligence", "technology-trend",
            "trade-tariff",
        }
        assert set(VALID_SIGNAL_TYPES) == expected
