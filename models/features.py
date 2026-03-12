"""
Feature engineering for model training.
Derives all 10 logistic regression features from nflverse historical data.

nflverse schema (team1 = home, team2 = away):
  date, season, game_type, week, team1_abbr, team2_abbr,
  score1 (home), score2 (away), neutral, rest1 (home), rest2 (away),
  ml1 (home moneyline), ml2 (away moneyline)
"""

import logging
import math
from typing import Tuple

import numpy as np
import pandas as pd

from config import PYTHAGOREAN_EXP, NFL_TEAMS, TEAM_538_MAP

logger = logging.getLogger(__name__)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points (miles)."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_travel_distance(team1_abbr: str, team2_abbr: str, neutral: int) -> float:
    """
    Travel distance (miles) that the away team (team2) travels.
    Returns 0 for neutral-site games.
    """
    if neutral == 1:
        return 0.0
    t2 = NFL_TEAMS.get(team2_abbr)
    t1 = NFL_TEAMS.get(team1_abbr)
    if not t2 or not t1:
        return 0.0
    return haversine_miles(t2["lat"], t2["lon"], t1["lat"], t1["lon"])


def pythagorean_exp(pf: float, pa: float, exp: float = PYTHAGOREAN_EXP) -> float:
    """Pythagorean win expectation."""
    if pf + pa == 0:
        return 0.5
    pf_e = pf ** exp
    pa_e = pa ** exp
    return pf_e / (pf_e + pa_e)


def build_training_features(
    df: pd.DataFrame,
    time_decay_lambda: float = 0.05,
    min_season: int = 2000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the feature matrix for logistic regression and XGBoost training.

    Parameters
    ----------
    df : pd.DataFrame   — nflverse historical data from load_538_data()
    time_decay_lambda   — exponential decay lambda (recent games weighted more)
    min_season          — exclude games before this season

    Returns
    -------
    X : np.ndarray (N, 10)
    y : np.ndarray (N,)   — 1 if home team (team1) won
    w : np.ndarray (N,)   — sample weights (exponential time decay)
    """
    completed = df[
        df["score1"].notna()
        & df["score2"].notna()
        & (df["season"] >= min_season)
    ].copy()

    if completed.empty:
        raise ValueError("No completed games found in dataset.")

    completed = completed.sort_values("date").reset_index(drop=True)

    # Build rolling per-team accumulators
    team_stats: dict = {}

    def get_state(abbr: str) -> dict:
        if abbr not in team_stats:
            team_stats[abbr] = {
                "pf": 0.0, "pa": 0.0,
                "games": 0,
                "recent_pf": [],
                "recent_pa": [],
                "wins_last5": [],
                "season_wins": 0,
                "season_losses": 0,
                "season": None,
            }
        return team_stats[abbr]

    rows = []
    max_date = pd.Timestamp(completed["date"].max())

    for _, row in completed.iterrows():
        t1 = row["team1_abbr"]   # home
        t2 = row["team2_abbr"]   # away
        s1 = float(row["score1"])
        s2 = float(row["score2"])
        neutral = int(row.get("neutral", 0))
        season = int(row["season"])
        date = row["date"]

        # Use actual rest days from nflverse
        rest1_raw = row.get("rest1")
        rest2_raw = row.get("rest2")
        rest1 = float(rest1_raw) if pd.notna(rest1_raw) else 7.0
        rest2 = float(rest2_raw) if pd.notna(rest2_raw) else 7.0

        st1 = get_state(t1)
        st2 = get_state(t2)

        # Season reset
        if st1["season"] != season:
            st1["season"] = season
            st1["season_wins"] = st1["season_losses"] = 0
        if st2["season"] != season:
            st2["season"] = season
            st2["season_wins"] = st2["season_losses"] = 0

        # x1 — offensive rating diff
        avg_pf_t1 = float(np.mean(st1["recent_pf"][-8:])) if st1["recent_pf"] else 24.0
        avg_pf_t2 = float(np.mean(st2["recent_pf"][-8:])) if st2["recent_pf"] else 24.0
        off_rating_diff = (avg_pf_t1 - avg_pf_t2) / 10.0

        # x2 — defensive rating diff
        avg_pa_t1 = float(np.mean(st1["recent_pa"][-8:])) if st1["recent_pa"] else 24.0
        avg_pa_t2 = float(np.mean(st2["recent_pa"][-8:])) if st2["recent_pa"] else 24.0
        def_rating_diff = (avg_pa_t2 - avg_pa_t1) / 10.0

        # x3 — home field advantage
        hfa = 1 if neutral == 0 else 0

        # x4 — rest days diff (actual rest days from nflverse!)
        rest_diff = (rest1 - rest2) / 7.0

        # x5 — ELO diff placeholder (ELO system handled separately in ensemble)
        elo_diff = 0.0

        # x6 — Pythagorean expectation diff
        pyth1 = pythagorean_exp(st1["pf"], st1["pa"]) if st1["games"] > 0 else 0.5
        pyth2 = pythagorean_exp(st2["pf"], st2["pa"]) if st2["games"] > 0 else 0.5
        pyth_diff = pyth1 - pyth2

        # x7 — net efficiency diff
        net_eff1 = (avg_pf_t1 - avg_pa_t1) / 10.0
        net_eff2 = (avg_pf_t2 - avg_pa_t2) / 10.0
        net_eff_diff = net_eff1 - net_eff2

        # x8 — turnover diff (not in games.csv — set to 0)
        to_diff = 0.0

        # x9 — travel distance diff
        travel = get_travel_distance(t1, t2, neutral)
        travel_diff = -travel / 1000.0

        # x10 — last5 win rate diff
        wr1 = float(np.mean(st1["wins_last5"][-5:])) if st1["wins_last5"] else 0.5
        wr2 = float(np.mean(st2["wins_last5"][-5:])) if st2["wins_last5"] else 0.5
        wr_diff = wr1 - wr2

        features = [
            off_rating_diff, def_rating_diff, hfa, rest_diff, elo_diff,
            pyth_diff, net_eff_diff, to_diff, travel_diff, wr_diff,
        ]

        label = 1 if s1 > s2 else 0

        # Exponential time decay
        weeks_ago = max(0.0, (max_date - date).days / 7.0)
        weight = math.exp(-time_decay_lambda * weeks_ago)

        rows.append(features + [label, weight])

        # Update state
        t1_won = s1 > s2
        st1["pf"] += s1; st1["pa"] += s2; st1["games"] += 1
        st1["recent_pf"].append(s1); st1["recent_pa"].append(s2)
        st1["wins_last5"].append(1 if t1_won else 0)
        if t1_won: st1["season_wins"] += 1
        else: st1["season_losses"] += 1

        st2["pf"] += s2; st2["pa"] += s1; st2["games"] += 1
        st2["recent_pf"].append(s2); st2["recent_pa"].append(s1)
        st2["wins_last5"].append(0 if t1_won else 1)
        if not t1_won: st2["season_wins"] += 1
        else: st2["season_losses"] += 1

    arr = np.array(rows, dtype=float)
    X = arr[:, :10]
    y = arr[:, 10].astype(int)
    w = arr[:, 11]

    if w.sum() > 0:
        w = w / w.mean()

    logger.info("Built training features: %d samples, %d features.", X.shape[0], X.shape[1])
    return X, y, w


FEATURE_NAMES = [
    "offensive_rating_diff",
    "defensive_rating_diff",
    "home_field_advantage",
    "rest_days_diff",
    "elo_diff_placeholder",
    "pythagorean_expectation_diff",
    "net_efficiency_diff",
    "turnover_diff_adjusted",
    "travel_distance_diff",
    "last5_win_rate_diff",
]
