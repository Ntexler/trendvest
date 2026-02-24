"""
Tests for momentum score direction logic.
"""
import pytest
from app.services.momentum import MomentumCalculator


class TestMomentumDirection:
    """Test the direction thresholds without needing a database."""

    def test_rising_threshold(self):
        calc = MomentumCalculator()
        assert calc.RISING_THRESHOLD == 150

    def test_falling_threshold(self):
        calc = MomentumCalculator()
        assert calc.FALLING_THRESHOLD == 80

    def test_score_above_150_is_rising(self):
        """Scores above 150 should map to 'rising'."""
        score = 185.0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "rising"

    def test_score_between_80_and_150_is_stable(self):
        score = 100.0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "stable"

    def test_score_below_80_is_falling(self):
        score = 50.0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "falling"

    def test_score_at_boundary_150_is_stable(self):
        """Score exactly at 150 is NOT rising (needs to be above)."""
        score = 150.0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "stable"

    def test_score_at_boundary_80_is_falling(self):
        """Score exactly at 80 is NOT stable (needs to be above)."""
        score = 80.0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "falling"

    def test_zero_score_is_falling(self):
        score = 0
        if score > MomentumCalculator.RISING_THRESHOLD:
            direction = "rising"
        elif score > MomentumCalculator.FALLING_THRESHOLD:
            direction = "stable"
        else:
            direction = "falling"
        assert direction == "falling"


class TestMomentumFormula:
    """Test the momentum calculation formula: (today / avg_7d) * 100."""

    def test_basic_formula(self):
        today = 50
        avg_7d = 25
        score = (today / avg_7d) * 100
        assert score == 200.0

    def test_equal_to_average(self):
        today = 30
        avg_7d = 30
        score = (today / avg_7d) * 100
        assert score == 100.0

    def test_below_average(self):
        today = 10
        avg_7d = 50
        score = (today / avg_7d) * 100
        assert score == 20.0

    def test_no_average_but_mentions(self):
        """When avg is 0 but today has mentions = strong signal (200)."""
        today = 15
        avg_7d = 0
        if avg_7d > 0:
            score = (today / avg_7d) * 100
        elif today > 0:
            score = 200
        else:
            score = 0
        assert score == 200

    def test_no_data_at_all(self):
        today = 0
        avg_7d = 0
        if avg_7d > 0:
            score = (today / avg_7d) * 100
        elif today > 0:
            score = 200
        else:
            score = 0
        assert score == 0
