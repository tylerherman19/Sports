"""
Rest and Travel Adjustments — System 7
Calculates ELO adjustments for rest days, travel distance,
back-to-back away games, short weeks, and bye weeks.
"""

import logging
import math
from typing import Dict, Any, Optional, Tuple

from models.features import haversine_miles
from config import NFL_TEAMS

logger = logging.getLogger(__name__)

# ── Adjustment constants ──────────────────────────────────────────────────────
REST_POINTS_PER_DAY   = 1.5   # ELO pts per extra day of rest beyond 7
TRAVEL_POINTS_PER_K   = -3.0  # ELO pts per 1,000 miles traveled (away team)
BACK_TO_BACK_AWAY     = -15.0 # ELO pts for consecutive away games
SHORT_WEEK_CUTOFF     = 6     # Days — fewer than this = short week
SHORT_WEEK_PENALTY    = -10.0 # ELO pts
BYE_WEEK_BONUS        = 25.0  # ELO pts for coming off a bye


def calculate_rest_adjustment(days_rest: int) -> float:
    """ELO adjustment for rest days relative to 7 (standard week)."""
    return (days_rest - 7) * REST_POINTS_PER_DAY


def calculate_travel_adjustment(
    traveling_team_abbr: str,
    home_team_abbr: str,
    is_neutral: bool = False,
) -> float:
    """ELO penalty for away-team travel distance."""
    if is_neutral:
        return 0.0

    t_info = NFL_TEAMS.get(traveling_team_abbr, {})
    h_info = NFL_TEAMS.get(home_team_abbr, {})

    if not t_info or not h_info:
        return 0.0

    distance = haversine_miles(
        t_info["lat"], t_info["lon"],
        h_info["lat"], h_info["lon"],
    )
    return (distance / 1000.0) * TRAVEL_POINTS_PER_K


def get_rest_travel_adjustments(
    home_abbr: str,
    away_abbr: str,
    home_rest_days: int,
    away_rest_days: int,
    is_neutral: bool = False,
    away_prev_was_away: bool = False,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """
    Compute all rest/travel ELO adjustments for a matchup.

    Returns a dict with the net ELO advantage for the home team.
    Positive = home team advantage, negative = away team advantage.
    """
    # Rest adjustments (applied to both teams relative to each other)
    home_rest_adj = calculate_rest_adjustment(home_rest_days)
    away_rest_adj = calculate_rest_adjustment(away_rest_days)

    # Bye week bonus
    home_bye = BYE_WEEK_BONUS if home_rest_days >= 13 else 0.0
    away_bye = BYE_WEEK_BONUS if away_rest_days >= 13 else 0.0

    # Short week penalty
    home_short = SHORT_WEEK_PENALTY if home_rest_days < SHORT_WEEK_CUTOFF else 0.0
    away_short = SHORT_WEEK_PENALTY if away_rest_days < SHORT_WEEK_CUTOFF else 0.0

    # Travel penalty (away team travels to home team's city)
    travel_penalty = calculate_travel_adjustment(away_abbr, home_abbr, is_neutral)

    # Back-to-back away
    b2b_penalty = BACK_TO_BACK_AWAY if (away_prev_was_away and not is_neutral) else 0.0

    # Net advantage for home team
    home_total = (home_rest_adj + home_bye + home_short) * scale
    away_total = (away_rest_adj + away_bye + away_short + travel_penalty + b2b_penalty) * scale

    net_home_advantage = home_total - away_total

    return {
        "home_rest_adj":    home_rest_adj * scale,
        "away_rest_adj":    away_rest_adj * scale,
        "home_bye":         home_bye * scale,
        "away_bye":         away_bye * scale,
        "home_short_week":  home_short * scale,
        "away_short_week":  away_short * scale,
        "travel_penalty":   travel_penalty * scale,
        "b2b_penalty":      b2b_penalty * scale,
        "net_home_adv":     net_home_advantage,
        "home_rest_days":   home_rest_days,
        "away_rest_days":   away_rest_days,
        "travel_miles":     abs(travel_penalty / TRAVEL_POINTS_PER_K * 1000) if not is_neutral else 0.0,
    }
