"""Tests for the signal scoring module."""

from src.analyzer.scorer import calculate_composite_score, match_signal_to_bus, score_signal


class TestScoring:
    def test_composite_score_calculation(self):
        scores = {
            "revenue_impact": 8.0,
            "time_sensitivity": 6.0,
            "strategic_alignment": 7.0,
            "competitive_pressure": 5.0,
        }
        composite = calculate_composite_score(scores)
        # 8*0.35 + 6*0.25 + 7*0.25 + 5*0.15 = 2.8 + 1.5 + 1.75 + 0.75 = 6.8
        assert abs(composite - 6.8) < 0.01

    def test_match_signal_to_bus(self):
        signal = {
            "title": "New humanoid robot uses advanced force sensors for grip control",
            "summary": "A robotics company unveiled a cobot with load cell based force transducers",
        }
        matches = match_signal_to_bus(signal)
        assert len(matches) > 0
        # VPG Force Sensors should be the top match
        assert matches[0]["bu_id"] == "vpg-force-sensors"

    def test_no_match_for_irrelevant_signal(self):
        signal = {
            "title": "Weather forecast for next week",
            "summary": "Sunny skies expected across the region",
        }
        matches = match_signal_to_bus(signal)
        assert len(matches) == 0

    def test_score_signal_returns_required_fields(self):
        signal = {
            "title": "Steel mill modernization drives demand for thickness measurement",
            "summary": "Rolling mill operators invest in laser gauge technology",
        }
        result = score_signal(signal)
        assert "scores" in result
        assert "composite" in result
        assert "bu_matches" in result
        assert "signal_type" in result
        assert "headline" in result
        assert "quick_win" in result
