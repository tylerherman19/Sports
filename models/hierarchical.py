"""
Hierarchical Team Model — System 11
Models team strength hierarchically:
  Team_strength
  ├── Offensive_rating = pass_off × 0.6 + rush_off × 0.4
  └── Defensive_rating = pass_def × 0.6 + rush_def × 0.4

Uses Normal conjugate Bayesian updates (scipy.stats). No PyMC.
"""

import logging
from typing import Dict, Any

import numpy as np
from scipy import stats

from config import ELO_BASELINE, CURRENT_SEASON, NFL_TEAMS

logger = logging.getLogger(__name__)

# Hierarchical component weights
PASS_WEIGHT   = 0.6
RUSH_WEIGHT   = 0.4
OFF_WEIGHT    = 0.5
DEF_WEIGHT    = 0.5

# Prior parameters (league-average baseline)
PRIOR_MU    = 0.0   # Centered at league average
PRIOR_SIGMA = 1.5   # High initial uncertainty
OBS_SIGMA   = 2.0   # Observation noise

# ELO scaling: net_strength × scale → ELO deviation from 1500
ELO_SCALE   = 50.0


def _conjugate_update(mu_prior: float, sigma_prior: float,
                      observation: float, sigma_obs: float = OBS_SIGMA):
    """Normal-Normal conjugate update."""
    var_prior = sigma_prior ** 2
    var_obs   = sigma_obs ** 2
    precision_post = 1/var_prior + 1/var_obs
    mu_post   = (mu_prior/var_prior + observation/var_obs) / precision_post
    sigma_post = (1/precision_post) ** 0.5
    return mu_post, sigma_post


def calculate_hierarchical_ratings(
    df,
    pfr_stats: Dict = None,
    current_season: int = CURRENT_SEASON,
) -> Dict[str, Dict[str, Any]]:
    """
    Estimate hierarchical team ratings from game data.

    Pass/rush offense and defense are modelled as separate Normal distributions.
    Each completed game updates all four components.

    Returns
    -------
    dict keyed by team abbreviation:
        off_rating  — offensive strength (0-centred, higher = better)
        def_rating  — defensive strength (0-centred, higher = better)
        team_rating — combined (off × 0.5 + def × 0.5)
        pass_off, rush_off, pass_def, rush_def — component estimates
        pass_off_sigma, rush_off_sigma, pass_def_sigma, rush_def_sigma — uncertainties
        team_elo    — ELO equivalent
    """
    season_games = df[
        (df["season"] == current_season)
        & df["score1"].notna()
        & df["score2"].notna()
    ].sort_values("date")

    # Initialise priors for each team × 4 components
    components = ("pass_off", "rush_off", "pass_def", "rush_def")
    mu    = {team: {c: PRIOR_MU    for c in components} for team in NFL_TEAMS}
    sigma = {team: {c: PRIOR_SIGMA for c in components} for team in NFL_TEAMS}

    for _, row in season_games.iterrows():
        t1 = row["team1_abbr"]
        t2 = row["team2_abbr"]
        s1 = float(row["score1"])
        s2 = float(row["score2"])

        if t1 not in mu or t2 not in mu:
            continue

        margin = s1 - s2  # positive → t1 dominated

        # Approximate component observations from score margin
        # Pass offense: larger weight for scoring (proxy)
        pass_margin  = margin * PASS_WEIGHT
        rush_margin  = margin * RUSH_WEIGHT
        def_impact   = -margin  # better defense → negative opponent margin

        for team, sign in ((t1, 1.0), (t2, -1.0)):
            pm = sign * pass_margin
            rm = sign * rush_margin
            dm = sign * def_impact

            mu[team]["pass_off"], sigma[team]["pass_off"] = _conjugate_update(
                mu[team]["pass_off"], sigma[team]["pass_off"],
                pm / PRIOR_SIGMA
            )
            mu[team]["rush_off"], sigma[team]["rush_off"] = _conjugate_update(
                mu[team]["rush_off"], sigma[team]["rush_off"],
                rm / PRIOR_SIGMA
            )
            mu[team]["pass_def"], sigma[team]["pass_def"] = _conjugate_update(
                mu[team]["pass_def"], sigma[team]["pass_def"],
                dm / PRIOR_SIGMA
            )
            mu[team]["rush_def"], sigma[team]["rush_def"] = _conjugate_update(
                mu[team]["rush_def"], sigma[team]["rush_def"],
                dm * RUSH_WEIGHT / PRIOR_SIGMA
            )

    # Build results
    results = {}
    for team in NFL_TEAMS:
        off_rating = (mu[team]["pass_off"] * PASS_WEIGHT
                      + mu[team]["rush_off"] * RUSH_WEIGHT)
        def_rating = (mu[team]["pass_def"] * PASS_WEIGHT
                      + mu[team]["rush_def"] * RUSH_WEIGHT)
        team_rating = off_rating * OFF_WEIGHT + def_rating * DEF_WEIGHT

        results[team] = {
            "off_rating":      off_rating,
            "def_rating":      def_rating,
            "team_rating":     team_rating,
            "pass_off":        mu[team]["pass_off"],
            "rush_off":        mu[team]["rush_off"],
            "pass_def":        mu[team]["pass_def"],
            "rush_def":        mu[team]["rush_def"],
            "pass_off_sigma":  sigma[team]["pass_off"],
            "rush_off_sigma":  sigma[team]["rush_off"],
            "pass_def_sigma":  sigma[team]["pass_def"],
            "rush_def_sigma":  sigma[team]["rush_def"],
            "team_elo":        ELO_BASELINE + team_rating * ELO_SCALE,
        }

    return results
