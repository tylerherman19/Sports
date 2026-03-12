"""
Bayesian Updating — System 3
Models each team's strength as a Normal distribution.
Uses Normal-Normal conjugate updates after each game.
"""

import logging
from typing import Dict, Tuple

import numpy as np

from config import (
    ELO_BASELINE,
    BAYESIAN_PRIOR_SIGMA,
    BAYESIAN_OBS_SIGMA,
    CURRENT_SEASON,
)

logger = logging.getLogger(__name__)


def _normal_conjugate_update(
    mu_prior: float,
    sigma_prior: float,
    observation: float,
    sigma_obs: float = BAYESIAN_OBS_SIGMA,
) -> Tuple[float, float]:
    """
    Normal-Normal conjugate Bayesian update.
    Returns (mu_posterior, sigma_posterior).
    """
    var_prior = sigma_prior ** 2
    var_obs = sigma_obs ** 2

    precision_prior = 1.0 / var_prior
    precision_obs = 1.0 / var_obs

    precision_post = precision_prior + precision_obs
    mu_post = (mu_prior * precision_prior + observation * precision_obs) / precision_post
    sigma_post = (1.0 / precision_post) ** 0.5

    return mu_post, sigma_post


def calculate_bayesian_ratings(
    df,
    elo_ratings: Dict[str, Dict],
    current_season: int = CURRENT_SEASON,
) -> Dict[str, Dict]:
    """
    Compute Bayesian posterior (mu, sigma) for every team using
    current-season game results as observations.

    The prior mu for each team is their season-start ELO (from elo_ratings).
    Sigma shrinks from BAYESIAN_PRIOR_SIGMA as more games are played.

    Parameters
    ----------
    df : pd.DataFrame  — FiveThirtyEight data
    elo_ratings : dict — output of calculate_elo_ratings()

    Returns
    -------
    dict keyed by team abbreviation:
        mu    — posterior mean (best estimate of team strength)
        sigma — posterior std dev (uncertainty band)
        games_played — games this season used for updating
    """
    import pandas as pd

    season_games = df[
        (df["season"] == current_season)
        & df["score1"].notna()
        & df["score2"].notna()
    ].sort_values("date")

    all_teams = set(elo_ratings.keys())
    from config import NFL_TEAMS
    all_teams.update(NFL_TEAMS.keys())

    # Initialise priors: mu = season-start ELO, sigma = BAYESIAN_PRIOR_SIGMA
    posteriors: Dict[str, Tuple[float, float]] = {}
    games_count: Dict[str, int] = {}

    for team in all_teams:
        prior_elo = elo_ratings.get(team, {}).get("elo_full", ELO_BASELINE)
        from models.elo import season_start_elo
        mu0 = season_start_elo(prior_elo)
        posteriors[team] = (mu0, float(BAYESIAN_PRIOR_SIGMA))
        games_count[team] = 0

    # Update after each completed current-season game
    for _, row in season_games.iterrows():
        t1 = row["team1_abbr"]
        t2 = row["team2_abbr"]
        s1 = float(row["score1"])
        s2 = float(row["score2"])

        if t1 not in posteriors or t2 not in posteriors:
            continue

        mu1, sig1 = posteriors[t1]
        mu2, sig2 = posteriors[t2]

        # Observation: winner's strength estimated as the ELO of winner
        # Use score margin as strength signal
        margin = s1 - s2  # positive = team1 won

        # team1 observation: posterior shifts based on performance vs expectation
        live_weight = min(1.0, games_count[t1] / 17.0)
        obs_mu1 = mu1 + margin * (1.0 - live_weight)
        mu1_new, sig1_new = _normal_conjugate_update(mu1, sig1, obs_mu1)
        posteriors[t1] = (mu1_new, sig1_new)
        games_count[t1] = games_count.get(t1, 0) + 1

        obs_mu2 = mu2 - margin * (1.0 - live_weight)
        mu2_new, sig2_new = _normal_conjugate_update(mu2, sig2, obs_mu2)
        posteriors[t2] = (mu2_new, sig2_new)
        games_count[t2] = games_count.get(t2, 0) + 1

    # Build results dict, merging with ELO ratings
    results: Dict[str, Dict] = {}
    for team in all_teams:
        mu, sigma = posteriors.get(team, (ELO_BASELINE, BAYESIAN_PRIOR_SIGMA))
        results[team] = {
            "mu":           mu,
            "sigma":        sigma,
            "lower_band":   mu - sigma,
            "upper_band":   mu + sigma,
            "games_played": games_count.get(team, 0),
        }

    return results
