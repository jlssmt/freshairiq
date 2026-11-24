"""#31: a CO2 airing whose CO2 levels off above the release level is given up instead of running forever.

Pure rule (``co2_airing_given_up``) and slope (``co2_slope_ppm_min``); the coordinator releases the hold band with them.
"""
from __future__ import annotations

import pytest

from custom_components.freshairiq.const import DEFAULT_OPTIONS
from custom_components.freshairiq.co2_fall import co2_airing_given_up, co2_slope_ppm_min

OPTIONS = {**DEFAULT_OPTIONS, "co2_warn": 1000, "co2_critical": 1400, "co2_release": 600, "min_duration_min": 3}
ISSUE_SERIES = [(0, 1150), (60, 980), (180, 790), (300, 715), (360, 698), (480, 683), (720, 680)]


@pytest.mark.parametrize(("co2", "slope", "given_up"), [
    (700, None, False),    # slope unknown: keep airing
    (700, 11, False),      # climbing again
    (700, 5, True),        # stalled but not climbing hard
    (700, 0, True),        # flat
    (700, -21, False),     # clear fall
    (700, -50, False),     # clear fall
    (700, -50 / 3, True),  # 100 ppm at 16.7 ppm/min = 6 min
    (630, -20, False),     # 30 ppm at 20 ppm/min = 1.5 min: reachable
    (640, -20, False),     # exactly 2 min: still airing
    (641, -20, True),      # just over 2 min
    (600, -1, False),      # at the release level the normal release applies
    (1000, 0, False),      # above the warning threshold the rule does not apply
    (550, 0, False),       # below the release level there is nothing to hold
])
def test_rule_table(co2, slope, given_up):
    assert co2_airing_given_up(co2, OPTIONS, slope, 10.0) is given_up


def test_automatic_release_uses_the_warning_threshold_minus_50():
    options = {**OPTIONS, "co2_release": 0}
    assert co2_airing_given_up(960, options, 0, 10.0) is True
    assert co2_airing_given_up(940, options, 0, 10.0) is False


def test_min_duration_wins():
    assert co2_airing_given_up(700, OPTIONS, 0, 2.9) is False
    assert co2_airing_given_up(700, OPTIONS, 0, 3.0) is True


def test_slope_needs_two_samples_and_a_minute():
    assert co2_slope_ppm_min([]) is None
    assert co2_slope_ppm_min([(0, 800)]) is None
    assert co2_slope_ppm_min([(0, 800), (59, 790)]) is None
    assert co2_slope_ppm_min([(0, 800), (60, 790)]) == pytest.approx(-10)


def test_slope_uses_only_the_last_two_minutes_and_fits_the_line():
    assert co2_slope_ppm_min([(0, 2000), (60, 1500), (200, 900), (260, 880), (320, 860)]) == pytest.approx(-20)


def _walk(options=OPTIONS):
    """First sample time at which the issue's series is given up (hold released once, as the latch does)."""
    for i, (t, ppm) in enumerate(ISSUE_SERIES):
        slope = co2_slope_ppm_min([(float(s), float(p)) for s, p in ISSUE_SERIES[: i + 1]])
        if co2_airing_given_up(float(ppm), options, slope, t / 60.0):
            return t, ppm
    return None


def test_issue_example_is_silent_while_falling_fast_and_gives_up_at_360_s():
    assert _walk() == (360, 698)
    slopes = [co2_slope_ppm_min([(float(s), float(p)) for s, p in ISSUE_SERIES[: i + 1]]) for i in range(1, 7)]
    assert [None if s is None else round(s) for s in slopes] == [-170, -95, -38, -17, -8, None]  # 2-minute fit of sparse samples
