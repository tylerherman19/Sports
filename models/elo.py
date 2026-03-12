"""
ELO Rating System — System 2
Implements the full ELO calculation including:
  - MOV multiplier
  - Home field advantage
  - Recent form blend
  - Head-to-head adjustment
  - Season-start regression
  - Injury discount
"""

import logging
import math
from collections import defaultdict
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

from config import ELO_BASELINE, ELO_SEASON_REGRESS_FACTOR, CURRENT_SEASON

logger = logging.getLogger(__name__)


def elo_win_prob(team_elo: float, opp_elo: float) -> float:
    """Standard ELO win probability."""
    return 1.0 / (1.0 + 10.0 ** ((opp_elo - team_elo) / 400.0))


def mov_multiplier(point_diff: float, elo_diff: float, mov_weight: float = 1.0) -> float:
    """
    Margin of victory multiplier.
    MOV_mult = log(|point_diff| + 1) × (2.2 / (elo_diff × 0.001 + 2.2))
    """
    log_factor = math.log(abs(point_diff) + 1)
    autocorr_factor = 2.2 / (abs(elo_diff) * 0.001 + 2.2)
    return log_factor * autocorr_factor * mov_weight


def season_start_elo(prior_elo: float) -> float:
    """Regress ELO toward mean at season start."""
    return prior_elo * ELO_SEASON_REGRESS_FACTOR + ELO_BASELINE * (1.0 - ELO_SEASON_REGRESS_FACTOR)


def calculate_elo_ratings(
    df: pd.DataFrame,
    k: float = 20.0,
    mov_weight: float = 1.0,
    home_field: float = 65.0,
    recent_form_pct: float = 30.0,
    h2h_weight: float = 20.0,
    turnover_impact: float = 1.0,
    rest_travel_scale: float = 1.0,
    injury_discounts: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate ELO ratings for all teams by replaying historical games.

    Parameters
    ----------
    df : pd.DataFrame
        Full FiveThirtyEight DataFrame (sorted chronologically).
    k : float
        K-factor (sensitivity), default 20.
    mov_weight : float
        Multiplier on MOV factor.
    home_field : float
        ELO points added to home team pre-game.
    recent_form_pct : float
        0–100 — percentage blend of recent-5-game ELO vs full-season ELO.
    h2h_weight : float
        0–100 — how much H2H win rate affects ELO adjustment (max ±50 pts).
    turnover_impact : float
        Scale for turnover ELO adjustment.
    rest_travel_scale : float
        Scale for all rest/travel ELO adjustments.
    injury_discounts : dict, optional
        {team_abbr: points_to_subtract}

    Returns
    -------
    dict keyed by team abbreviation:
        elo           — final blended ELO
        elo_full      — full-season ELO (no recent-form blend)
        elo_recent    — ELO from last 5 games only
        sigma         — Bayesian uncertainty (computed in bayesian.py, placeholder here)
        games_played  — games in current season
        wins          — current season wins
        losses        — current season losses
        last5         — list of last-5 game results (W/L)
        elo_history   — list of (date, elo) tuples for sparklines
        h2h_records   — {opponent_abbr: [results]} — last 10 results per opponent
    """
    if injury_discounts is None:
        injury_discounts = {}

    recent_form_frac = recent_form_pct / 100.0

    # ── Initialise team state ─────────────────────────────────────────────────
    elos: Dict[str, float] = {}
    elos_recent: Dict[str, float] = {}   # ELO built from last-5-game window
    team_seasons: Dict[str, int] = {}
    team_games: Dict[str, int] = {}
    team_wins: Dict[str, int] = {}
    team_losses: Dict[str, int] = {}
    team_last5: Dict[str, list] = defaultdict(list)
    team_recent_games: Dict[str, list] = defaultdict(list)   # last 5 game ELO snapshots
    elo_history: Dict[str, list] = defaultdict(list)
    h2h_records: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))

    def get_elo(team: str) -> float:
        return elos.get(team, float(ELO_BASELINE))

    def get_elo_recent(team: str) -> float:
        return elos_recent.get(team, float(ELO_BASELINE))

    # ── Replay all games ──────────────────────────────────────────────────────
    completed = df[df["score1"].notna() & df["score2"].notna()].copy()
    completed = completed.sort_values("date").reset_index(drop=True)

    for _, row in completed.iterrows():
        t1 = row["team1_abbr"]
        t2 = row["team2_abbr"]
        s1 = float(row["score1"])
        s2 = float(row["score2"])
        neutral = int(row["neutral"])
        season = int(row["season"])
        date = row["date"]

        # Season boundary: regress ELOs
        for team in (t1, t2):
            prev_season = team_seasons.get(team)
            if prev_season is not None and prev_season != season:
                elos[team] = season_start_elo(get_elo(team))
                elos_recent[team] = season_start_elo(get_elo_recent(team))
                team_games[team] = 0
                team_wins[team] = 0
                team_losses[team] = 0
                team_recent_games[team] = []
            team_seasons[team] = season

        # Pre-game ELOs
        e1 = get_elo(t1)
        e2 = get_elo(t2)

        # Home field adjustment
        hfa = home_field if neutral == 0 else 0.0
        e1_adj = e1 + hfa
        e2_adj = e2

        # Expected outcome
        exp1 = elo_win_prob(e1_adj, e2_adj)
        exp2 = 1.0 - exp1

        # Actual outcome
        act1 = 1.0 if s1 > s2 else (0.0 if s1 < s2 else 0.5)
        act2 = 1.0 - act1

        # Margin of victory multiplier
        point_diff = s1 - s2
        elo_diff_pre = e1_adj - e2_adj
        mov1 = mov_multiplier(point_diff if act1 == 1 else -point_diff,
                              elo_diff_pre if act1 == 1 else -elo_diff_pre,
                              mov_weight)

        # ELO updates
        delta1 = k * mov1 * (act1 - exp1)
        delta2 = k * mov1 * (act2 - exp2)

        new_e1 = e1 + delta1
        new_e2 = e2 + delta2

        elos[t1] = new_e1
        elos[t2] = new_e2

        # Recent-form ELO (same formula, separate tracker)
        er1 = get_elo_recent(t1)
        er2 = get_elo_recent(t2)
        er1_adj = er1 + hfa
        exp_r1 = elo_win_prob(er1_adj, er2)
        mov_r = mov_multiplier(point_diff if act1 == 1 else -point_diff,
                               er1_adj - er2 if act1 == 1 else er2 - er1_adj,
                               mov_weight)
        delta_r1 = k * mov_r * (act1 - exp_r1)
        delta_r2 = k * mov_r * (act2 - (1 - exp_r1))
        elos_recent[t1] = er1 + delta_r1
        elos_recent[t2] = er2 + delta_r2

        # Update records
        for team, won in ((t1, act1 == 1.0), (t2, act2 == 1.0)):
            team_games[team] = team_games.get(team, 0) + 1
            if won:
                team_wins[team] = team_wins.get(team, 0) + 1
            else:
                team_losses[team] = team_losses.get(team, 0) + 1
            team_last5[team].append("W" if won else "L")

        # H2H tracking
        h2h_records[t1][t2].append(1 if act1 == 1 else 0)
        h2h_records[t2][t1].append(1 if act2 == 1 else 0)

        # ELO history for sparklines (current season only)
        if season == CURRENT_SEASON:
            elo_history[t1].append((date, new_e1))
            elo_history[t2].append((date, new_e2))

    # ── Build final output ────────────────────────────────────────────────────
    all_teams = set(list(elos.keys()))
    # Add any teams that never played (new franchises etc.)
    from config import NFL_TEAMS as _NFL_TEAMS
    all_teams.update(_NFL_TEAMS.keys())

    results: Dict[str, Dict[str, Any]] = {}

    for team in all_teams:
        full_elo = get_elo(team)
        recent_elo = get_elo_recent(team)

        # Blend full-season and recent-form ELO
        blended = full_elo * (1.0 - recent_form_frac) + recent_elo * recent_form_frac

        # H2H adjustment: last 10 games per opponent
        h2h_adj = 0.0
        for opp, results_list in h2h_records[team].items():
            last10 = results_list[-10:]
            if last10:
                h2h_wr = np.mean(last10)
                # ±50 ELO max, scaled by h2h_weight%
                h2h_adj += (h2h_wr - 0.5) * 100 * (h2h_weight / 100.0)

        # Apply injury discount
        injury_disc = injury_discounts.get(team, 0.0)

        final_elo = blended + h2h_adj - injury_disc

        results[team] = {
            "elo":           final_elo,
            "elo_full":      full_elo,
            "elo_recent":    recent_elo,
            "games_played":  team_games.get(team, 0),
            "wins":          team_wins.get(team, 0),
            "losses":        team_losses.get(team, 0),
            "last5":         team_last5[team][-5:],
            "elo_history":   elo_history[team],
            "h2h_records":   dict(h2h_records[team]),
        }

    return results


def elo_to_prob(elo_diff: float) -> float:
    """Convert ELO difference to win probability."""
    return 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
