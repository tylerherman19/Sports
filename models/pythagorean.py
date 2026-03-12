"""
Pythagorean Win Expectation — System 4
Formula: PF^2.37 / (PF^2.37 + PA^2.37)
Flags teams deviating >0.10 from expectation.
"""

import logging
from typing import Dict, Any

from config import PYTHAGOREAN_EXP, ELO_BASELINE, CURRENT_SEASON

logger = logging.getLogger(__name__)

DEVIATION_THRESHOLD = 0.10


def pythagorean_expectation(pf: float, pa: float, exp: float = PYTHAGOREAN_EXP) -> float:
    """Pythagorean win expectation."""
    if pf + pa == 0:
        return 0.5
    pf_e = pf ** exp
    pa_e = pa ** exp
    return pf_e / (pf_e + pa_e)


def pyth_to_elo(pyth: float) -> float:
    """Convert Pythagorean expectation to ELO-equivalent."""
    return ELO_BASELINE + (pyth - 0.5) * 400.0


def calculate_pythagorean_ratings(
    df,
    standings: Dict[str, Dict],
    current_season: int = CURRENT_SEASON,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate Pythagorean ratings from current-season cumulative points.

    Parameters
    ----------
    df : pd.DataFrame — FiveThirtyEight historical data
    standings : dict  — ESPN standings (wins, losses, points_for, points_against)

    Returns
    -------
    dict keyed by team abbreviation:
        pyth_exp      — Pythagorean win expectation (0–1)
        pyth_elo      — ELO equivalent
        actual_wl_pct — Actual win percentage
        deviation     — actual - pyth_exp
        flag          — 'overperformer' | 'underperformer' | None
        pf            — cumulative points for
        pa            — cumulative points against
    """
    import numpy as np
    import pandas as pd

    from config import NFL_TEAMS

    results: Dict[str, Dict[str, Any]] = {}

    # Try to use ESPN standings data first (has points_for, points_against)
    for team in NFL_TEAMS:
        std = standings.get(team, {})
        wins = std.get("wins", 0)
        losses = std.get("losses", 0)
        ties = std.get("ties", 0)
        pf = std.get("points_for", 0.0)
        pa = std.get("points_against", 0.0)

        if pf == 0.0 and pa == 0.0:
            # Fall back to 538 historical current season cumulative
            season_completed = df[
                (df["season"] == current_season)
                & df["score1"].notna()
                & df["score2"].notna()
            ]

            team_games_home = season_completed[season_completed["team1_abbr"] == team]
            team_games_away = season_completed[season_completed["team2_abbr"] == team]

            pf = team_games_home["score1"].sum() + team_games_away["score2"].sum()
            pa = team_games_home["score2"].sum() + team_games_away["score1"].sum()
            games_played = len(team_games_home) + len(team_games_away)

            if games_played > 0 and wins == 0 and losses == 0:
                wins = int(
                    (team_games_home["score1"] > team_games_home["score2"]).sum()
                    + (team_games_away["score2"] > team_games_away["score1"]).sum()
                )
                losses = games_played - wins

        games = wins + losses + ties
        actual_pct = (wins + 0.5 * ties) / games if games > 0 else 0.5

        pyth = pythagorean_expectation(float(pf), float(pa))
        deviation = actual_pct - pyth

        flag = None
        if abs(deviation) > DEVIATION_THRESHOLD:
            flag = "overperformer" if deviation > 0 else "underperformer"

        results[team] = {
            "pyth_exp":     pyth,
            "pyth_elo":     pyth_to_elo(pyth),
            "actual_wl_pct": actual_pct,
            "deviation":    deviation,
            "flag":         flag,
            "pf":           float(pf),
            "pa":           float(pa),
            "wins":         wins,
            "losses":       losses,
        }

    return results
