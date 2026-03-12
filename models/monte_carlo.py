"""
Monte Carlo Simulation — System 10
Runs 10,000 game simulations using Bayesian posterior distributions.
Also runs full-season playoff probability simulation.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from config import MONTE_CARLO_SIMS, NFL_TEAMS

logger = logging.getLogger(__name__)

# Typical NFL game total (points) and spread std dev based on historical data
TYPICAL_TOTAL    = 48.0
SPREAD_STD_DEV   = 13.5  # Historical std dev of NFL game margins


def simulate_matchup(
    home_mu: float,
    home_sigma: float,
    away_mu: float,
    away_sigma: float,
    ensemble_win_prob: float,
    n: int = MONTE_CARLO_SIMS,
    random_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run N Monte Carlo simulations for one game.

    Parameters
    ----------
    home_mu / home_sigma  : Bayesian posterior for home team
    away_mu / away_sigma  : Bayesian posterior for away team
    ensemble_win_prob     : calibrated home win probability from ensemble
    n                     : number of simulations

    Returns
    -------
    dict:
        win_prob           — simulated win probability (home team)
        median_margin      — median home-team point margin
        margin_mean        — mean home-team margin
        margin_std         — std dev of margins
        margin_ci_low      — 10th percentile
        margin_ci_high     — 90th percentile
        prob_win_by_7      — P(home wins by 7+)
        prob_win_by_14     — P(home wins by 14+)
        prob_win_by_21     — P(home wins by 21+)
        margin_distribution — sample of margins (for histogram)
    """
    rng = np.random.default_rng(random_seed)

    # Draw team strengths from Bayesian posteriors
    home_strengths = rng.normal(home_mu, home_sigma, n)
    away_strengths = rng.normal(away_mu, away_sigma, n)

    strength_diff = home_strengths - away_strengths

    # Convert strength diff to per-game win prob via logistic function
    # Calibrate so that 400 ELO pts → ~90% win prob
    sim_win_probs = 1.0 / (1.0 + np.exp(-strength_diff / 200.0))

    # Sample actual game outcomes from per-simulation win probabilities
    outcomes = rng.binomial(1, sim_win_probs)

    # Simulate point margins: mean = f(strength_diff), noise = SPREAD_STD_DEV
    # Rescale ELO diff to expected margin (≈1 point per 25 ELO)
    expected_margins = strength_diff / 25.0

    # Blend with ensemble win prob signal
    # ensemble_win_prob → implied margin via inverse normal CDF
    implied_margin = (ensemble_win_prob - 0.5) * 2.0 * SPREAD_STD_DEV
    blended_margins = 0.6 * expected_margins + 0.4 * implied_margin

    # Add game-day noise
    noise = rng.normal(0, SPREAD_STD_DEV, n)
    margins = blended_margins + noise

    # Make wins/losses consistent with margins
    # If we said home won (outcome=1), ensure margin is positive
    margins = np.where(outcomes == 1, np.abs(margins), -np.abs(margins))

    win_prob = outcomes.mean()
    median_margin = float(np.median(margins))
    margin_mean = float(margins.mean())
    margin_std = float(margins.std())

    return {
        "win_prob":         float(win_prob),
        "median_margin":    median_margin,
        "margin_mean":      margin_mean,
        "margin_std":       margin_std,
        "margin_ci_low":    float(np.percentile(margins, 10)),
        "margin_ci_high":   float(np.percentile(margins, 90)),
        "prob_win_by_7":    float((margins >= 7).mean()),
        "prob_win_by_14":   float((margins >= 14).mean()),
        "prob_win_by_21":   float((margins >= 21).mean()),
        "margin_distribution": margins[::10].tolist(),  # every 10th for efficiency
    }


def simulate_season(
    teams: List[str],
    remaining_schedule: List[Tuple[str, str, bool]],
    bayesian_ratings: Dict[str, Dict],
    ensemble_probs: Dict[str, Dict],
    n: int = MONTE_CARLO_SIMS,
    random_seed: Optional[int] = 42,
) -> Dict[str, Dict[str, Any]]:
    """
    Simulate the remaining NFL season N times and compute playoff probabilities.

    Parameters
    ----------
    teams : list of team abbreviations
    remaining_schedule : list of (home, away, is_neutral) tuples
    bayesian_ratings : dict from calculate_bayesian_ratings()
    ensemble_probs : dict — pre-computed win probs for each remaining game
                            keyed by f"{home}_vs_{away}"
    n : number of simulations

    Returns
    -------
    dict keyed by team abbreviation:
        playoff_prob        — probability of making playoffs (top 7 per conf)
        division_prob       — probability of winning division
        bye_prob            — probability of #1 seed (bye week)
        expected_wins       — expected wins in remaining games
    """
    rng = np.random.default_rng(random_seed)

    if not remaining_schedule:
        return {team: {"playoff_prob": 0.5, "division_prob": 0.25, "bye_prob": 0.1, "expected_wins": 0.0}
                for team in teams}

    from config import NFL_TEAMS as _NFL_TEAMS

    # Track conference info
    conf_divisions: Dict[str, str] = {}
    for team in teams:
        info = _NFL_TEAMS.get(team, {})
        from data.espn import load_standings
        # Use a simplified conference lookup from team name patterns
        conf_divisions[team] = "AFC" if team in AFC_TEAMS else "NFC"

    # Simulation
    playoff_counts = {t: 0 for t in teams}
    division_win_counts = {t: 0 for t in teams}
    bye_counts = {t: 0 for t in teams}
    total_wins = {t: 0.0 for t in teams}

    for sim in range(n):
        sim_wins = {t: 0 for t in teams}

        for home, away, is_neutral in remaining_schedule:
            game_key = f"{home}_vs_{away}"
            base_prob = ensemble_probs.get(game_key, {}).get("home_prob", 0.5)

            # Add slight variance per simulation draw
            h_mu = bayesian_ratings.get(home, {}).get("mu", 1500.0)
            h_sigma = bayesian_ratings.get(home, {}).get("sigma", 75.0)
            a_mu = bayesian_ratings.get(away, {}).get("mu", 1500.0)
            a_sigma = bayesian_ratings.get(away, {}).get("sigma", 75.0)

            h_str = rng.normal(h_mu, h_sigma)
            a_str = rng.normal(a_mu, a_sigma)
            str_diff = h_str - a_str
            sim_prob = 1.0 / (1.0 + np.exp(-str_diff / 200.0))
            # Blend with ensemble
            blended_prob = 0.7 * sim_prob + 0.3 * base_prob

            if rng.random() < blended_prob:
                sim_wins[home] = sim_wins.get(home, 0) + 1
            else:
                sim_wins[away] = sim_wins.get(away, 0) + 1

        # Accumulate
        for t in teams:
            total_wins[t] += sim_wins.get(t, 0)

        # Determine playoff qualifiers (simplified: top 7 per conference by wins)
        for conf in ("AFC", "NFC"):
            conf_teams = [t for t in teams if conf_divisions.get(t) == conf]
            if not conf_teams:
                continue

            sorted_conf = sorted(conf_teams, key=lambda t: sim_wins.get(t, 0), reverse=True)

            for rank, team in enumerate(sorted_conf):
                if rank < 7:
                    playoff_counts[team] += 1
                if rank == 0:
                    bye_counts[team] += 1

    results = {}
    for team in teams:
        results[team] = {
            "playoff_prob":  playoff_counts[team] / n,
            "bye_prob":      bye_counts[team] / n,
            "expected_wins": total_wins[team] / n,
        }

    return results


# Conference membership for playoff seeding
AFC_TEAMS = {
    "BAL", "BUF", "CIN", "CLE", "DEN", "HOU", "IND", "JAX",
    "KC", "LAC", "LV", "MIA", "NE", "NYJ", "PIT", "TEN"
}
NFC_TEAMS = {
    "ARI", "ATL", "CAR", "CHI", "DAL", "DET", "GB", "LAR",
    "MIN", "NO", "NYG", "PHI", "SEA", "SF", "TB", "WAS"
}
