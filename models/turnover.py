"""
Turnover Regression — System 6
Regresses turnover differentials toward mean as season progresses.
"""

import logging
from typing import Dict, Any, Optional

from config import CURRENT_SEASON

logger = logging.getLogger(__name__)

POINTS_PER_ADJUSTED_TO = 8.0  # ELO points per adjusted turnover differential


def calculate_turnover_adjustments(
    pfr_stats: Optional[Dict[str, Dict]],
    elo_ratings: Dict[str, Dict],
    turnover_impact: float = 1.0,
    current_season: int = CURRENT_SEASON,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate turnover regression adjustments for all teams.

    Parameters
    ----------
    pfr_stats : dict or None — PFR stats with turnover data
    elo_ratings : dict       — current ELO ratings (contains games_played)
    turnover_impact : float  — scale factor for turnover ELO impact

    Returns
    -------
    dict keyed by team abbreviation:
        actual_to_diff      — raw turnover differential (positive = more takeaways)
        regression_weight   — 1 - (games_played / 17)
        adj_to_diff         — regression-adjusted turnover differential
        elo_adjustment      — ELO adjustment from turnovers
    """
    from config import NFL_TEAMS

    results: Dict[str, Dict[str, Any]] = {}

    for team in NFL_TEAMS:
        games_played = elo_ratings.get(team, {}).get("games_played", 0)
        regression_weight = 1.0 - min(1.0, games_played / 17.0)

        # Get turnover data from PFR if available
        actual_to_diff = 0.0
        if pfr_stats and team in pfr_stats:
            off_to = pfr_stats[team].get("off_to") or 0.0
            def_to = pfr_stats[team].get("def_to") or 0.0
            # Defensive turnovers = takeaways (good), offensive = giveaways (bad)
            actual_to_diff = float(def_to) - float(off_to)

        # Regression-adjusted: pull toward zero as season progresses
        adj_to_diff = actual_to_diff * (1.0 - regression_weight)

        # ELO adjustment
        elo_adj = adj_to_diff * POINTS_PER_ADJUSTED_TO * turnover_impact

        results[team] = {
            "actual_to_diff":   actual_to_diff,
            "regression_weight": regression_weight,
            "adj_to_diff":      adj_to_diff,
            "elo_adjustment":   elo_adj,
            "games_played":     games_played,
        }

    return results


def get_turnover_elo_adjustment(
    team_adj: Dict[str, Any],
    opp_adj: Dict[str, Any],
) -> float:
    """
    Net ELO adjustment for a matchup based on turnover regression.
    Positive = advantage for team.
    """
    return team_adj.get("elo_adjustment", 0.0) - opp_adj.get("elo_adjustment", 0.0)
