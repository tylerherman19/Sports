"""
Ensemble Blend — System 12
Master predict_matchup() function combining all 12 prediction systems.
"""

import logging
import math
from typing import Dict, Any, Optional

import numpy as np

from config import ELO_BASELINE, NFL_TEAMS
from models.elo import elo_to_prob
from models.features import (
    pythagorean_exp,
    haversine_miles,
    get_travel_distance,
    FEATURE_NAMES,
)
from models.logistic_model import predict_logistic
from models.xgboost_model import predict_xgboost
from models.monte_carlo import simulate_matchup
from models.rest_travel import get_rest_travel_adjustments
from data.odds import find_odds_for_game, calculate_edge, kelly_criterion

logger = logging.getLogger(__name__)


def build_matchup_feature_vector(
    home_abbr: str,
    away_abbr: str,
    team_stats: Dict[str, Any],
    home_rest_days: int = 7,
    away_rest_days: int = 7,
    is_neutral: bool = False,
) -> np.ndarray:
    """
    Build the 10-feature vector for a matchup.

    Uses current-season team stats from team_stats dict.
    """
    def _get(team, key, default=0.0):
        return team_stats.get(team, {}).get(key, default)

    # x1 — offensive rating diff
    off1 = _get(home_abbr, "off_eff", 1.0)
    off2 = _get(away_abbr, "off_eff", 1.0)
    off_diff = (off1 - off2)

    # x2 — defensive rating diff
    def1 = _get(home_abbr, "def_eff", 1.0)
    def2 = _get(away_abbr, "def_eff", 1.0)
    def_diff = def1 - def2

    # x3 — home field advantage
    hfa = 0 if is_neutral else 1

    # x4 — rest days diff (normalised)
    rest_diff = (home_rest_days - away_rest_days) / 7.0

    # x5 — ELO diff (normalised)
    elo1 = _get(home_abbr, "elo", ELO_BASELINE)
    elo2 = _get(away_abbr, "elo", ELO_BASELINE)
    elo_diff_norm = (elo1 - elo2) / 400.0

    # x6 — Pythagorean diff
    pyth1 = _get(home_abbr, "pyth_exp", 0.5)
    pyth2 = _get(away_abbr, "pyth_exp", 0.5)
    pyth_diff = pyth1 - pyth2

    # x7 — net efficiency diff
    net1 = _get(home_abbr, "net_eff", 0.0)
    net2 = _get(away_abbr, "net_eff", 0.0)
    net_eff_diff = net1 - net2

    # x8 — turnover diff adjusted
    to1 = _get(home_abbr, "adj_to_diff", 0.0)
    to2 = _get(away_abbr, "adj_to_diff", 0.0)
    to_diff = (to1 - to2) / 5.0

    # x9 — travel distance diff
    travel_dist = get_travel_distance(home_abbr, away_abbr, 1 if is_neutral else 0)
    travel_diff = -travel_dist / 1000.0

    # x10 — last5 win rate diff
    last5_home = _get(home_abbr, "last5_wr", 0.5)
    last5_away = _get(away_abbr, "last5_wr", 0.5)
    wr_diff = last5_home - last5_away

    return np.array([
        off_diff, def_diff, hfa, rest_diff, elo_diff_norm,
        pyth_diff, net_eff_diff, to_diff, travel_diff, wr_diff,
    ])


def predict_matchup(
    home_abbr: str,
    away_abbr: str,
    params: Dict[str, Any],
    logistic_bundle: Dict,
    xgb_bundle: Dict,
    team_stats: Dict[str, Any],
    bayesian_ratings: Dict[str, Dict],
    pythagorean_ratings: Dict[str, Dict],
    efficiency_ratings: Dict[str, Dict],
    turnover_adjustments: Dict[str, Dict],
    odds_data: Optional[Dict] = None,
    home_rest_days: int = 7,
    away_rest_days: int = 7,
    is_neutral: bool = False,
    away_prev_was_away: bool = False,
) -> Dict[str, Any]:
    """
    Full ensemble prediction for a matchup.

    Returns comprehensive prediction dict used by all UI sections.
    """
    # ── Feature vector ────────────────────────────────────────────────────────
    fv = build_matchup_feature_vector(
        home_abbr, away_abbr, team_stats,
        home_rest_days, away_rest_days, is_neutral,
    )

    # ── Individual system probabilities ──────────────────────────────────────

    # System 1 — Logistic Regression
    logistic_prob = predict_logistic(logistic_bundle, fv)

    # System 9 — XGBoost
    xgb_prob = predict_xgboost(xgb_bundle, fv)

    # System 2 — ELO
    home_elo = team_stats.get(home_abbr, {}).get("elo", ELO_BASELINE)
    away_elo = team_stats.get(away_abbr, {}).get("elo", ELO_BASELINE)
    hfa = 0 if is_neutral else params.get("home_field", 65)
    elo_prob = elo_to_prob(home_elo + hfa - away_elo)

    # System 4 — Pythagorean
    home_pyth_elo = pythagorean_ratings.get(home_abbr, {}).get("pyth_elo", ELO_BASELINE)
    away_pyth_elo = pythagorean_ratings.get(away_abbr, {}).get("pyth_elo", ELO_BASELINE)
    pyth_prob = elo_to_prob(home_pyth_elo - away_pyth_elo)

    # System 5 — Efficiency
    home_eff_elo = efficiency_ratings.get(home_abbr, {}).get("eff_elo", ELO_BASELINE)
    away_eff_elo = efficiency_ratings.get(away_abbr, {}).get("eff_elo", ELO_BASELINE)
    eff_prob = elo_to_prob(home_eff_elo - away_eff_elo)

    # ── Rest / Travel adjustments ─────────────────────────────────────────────
    rt_adj = get_rest_travel_adjustments(
        home_abbr, away_abbr,
        home_rest_days, away_rest_days,
        is_neutral, away_prev_was_away,
        scale=params.get("rest_travel_scale", 1.0),
    )
    rt_elo_adj = rt_adj["net_home_adv"]

    # ── Turnover adjustment ───────────────────────────────────────────────────
    home_to = turnover_adjustments.get(home_abbr, {}).get("elo_adjustment", 0.0)
    away_to = turnover_adjustments.get(away_abbr, {}).get("elo_adjustment", 0.0)
    to_elo_adj = (home_to - away_to) * params.get("turnover_impact", 1.0)

    # Apply additive ELO adjustments before final blend
    adjusted_elo_diff = (home_elo + hfa) - away_elo + rt_elo_adj + to_elo_adj
    adjusted_elo_prob = elo_to_prob(adjusted_elo_diff)

    # ── Ensemble weights (normalized to sum=1) ────────────────────────────────
    w_raw = {
        "logistic": params.get("w_logistic", 30),
        "xgb":      params.get("w_xgb",      25),
        "elo":      params.get("w_elo",       20),
        "pyth":     params.get("w_pyth",      15),
        "eff":      params.get("w_eff",       10),
    }
    total_w = sum(w_raw.values()) or 1.0
    weights = {k: v / total_w for k, v in w_raw.items()}

    # ── Final ensemble probability ────────────────────────────────────────────
    final_prob = (
        logistic_prob     * weights["logistic"]
        + xgb_prob        * weights["xgb"]
        + adjusted_elo_prob * weights["elo"]
        + pyth_prob       * weights["pyth"]
        + eff_prob        * weights["eff"]
    )
    final_prob = float(np.clip(final_prob, 0.01, 0.99))

    # ── Monte Carlo simulation ────────────────────────────────────────────────
    home_bay = bayesian_ratings.get(home_abbr, {})
    away_bay = bayesian_ratings.get(away_abbr, {})
    mc = simulate_matchup(
        home_mu=home_bay.get("mu", ELO_BASELINE),
        home_sigma=home_bay.get("sigma", 75.0),
        away_mu=away_bay.get("mu", ELO_BASELINE),
        away_sigma=away_bay.get("sigma", 75.0),
        ensemble_win_prob=final_prob,
    )

    # ── Market comparison ─────────────────────────────────────────────────────
    market = None
    edge = None
    kelly = None
    if odds_data:
        game_odds = find_odds_for_game(odds_data, home_abbr, away_abbr)
        if game_odds:
            market_prob = game_odds["home_prob"]
            edge = calculate_edge(final_prob, market_prob)
            kelly_frac = kelly_criterion(final_prob, game_odds["home_odds"])
            market = {
                "home_prob":   market_prob,
                "away_prob":   game_odds["away_prob"],
                "home_odds":   game_odds["home_odds"],
                "away_odds":   game_odds["away_odds"],
                "bookmaker":   game_odds["bookmaker"],
            }
            kelly = kelly_frac

    # ── Plain-English explanation ─────────────────────────────────────────────
    explanation = _generate_explanation(
        home_abbr, away_abbr, final_prob, adjusted_elo_diff,
        rt_adj, to_elo_adj, mc, market, edge,
    )

    return {
        # Core prediction
        "home_abbr":        home_abbr,
        "away_abbr":        away_abbr,
        "home_win_prob":    final_prob,
        "away_win_prob":    1.0 - final_prob,
        "predicted_winner": home_abbr if final_prob >= 0.5 else away_abbr,

        # Individual system probabilities
        "logistic_prob":    logistic_prob,
        "xgb_prob":         xgb_prob,
        "elo_prob":         adjusted_elo_prob,
        "pyth_prob":        pyth_prob,
        "eff_prob":         eff_prob,

        # ELO values
        "home_elo":         home_elo,
        "away_elo":         away_elo,
        "home_elo_display": home_elo - params.get("injury_discounts", {}).get(home_abbr, 0),
        "away_elo_display": away_elo - params.get("injury_discounts", {}).get(away_abbr, 0),

        # Adjustments
        "rest_travel":      rt_adj,
        "turnover_elo_adj": to_elo_adj,
        "adjusted_elo_diff": adjusted_elo_diff,

        # Pythagorean
        "home_pyth":        pythagorean_ratings.get(home_abbr, {}),
        "away_pyth":        pythagorean_ratings.get(away_abbr, {}),

        # Bayesian bands
        "home_bayesian":    home_bay,
        "away_bayesian":    away_bay,

        # Monte Carlo
        "monte_carlo":      mc,

        # Market
        "market":           market,
        "edge":             edge,
        "kelly":            kelly,

        # Ensemble weights used
        "weights_used":     weights,

        # Explanation
        "explanation":      explanation,
    }


def _generate_explanation(
    home: str, away: str, prob: float, elo_diff: float,
    rt_adj: Dict, to_adj: float, mc: Dict,
    market: Optional[Dict], edge: Optional[float],
) -> str:
    """Generate a 5-sentence plain-English game summary."""
    home_name = NFL_TEAMS.get(home, {}).get("name", home)
    away_name = NFL_TEAMS.get(away, {}).get("name", away)
    winner = home_name if prob >= 0.5 else away_name
    winner_prob = max(prob, 1 - prob)

    sentences = []

    # 1. Overall prediction
    sentences.append(
        f"The model gives {winner} a {winner_prob:.0%} chance of winning this game."
    )

    # 2. ELO advantage
    if abs(elo_diff) > 30:
        adv_team = home_name if elo_diff > 0 else away_name
        sentences.append(
            f"{adv_team} holds a significant ELO advantage of {abs(elo_diff):.0f} points, "
            f"reflecting superior recent performance."
        )
    else:
        sentences.append(
            f"The teams are closely matched on ELO with only a {abs(elo_diff):.0f}-point gap, "
            f"making this a coin-flip at the model level."
        )

    # 3. Rest/travel
    rt_note = ""
    if rt_adj["away_bye"] > 0:
        rt_note = f"{away_name} is coming off a bye week (+{BYE_WEEK_BONUS:.0f} ELO pts)."
    elif rt_adj["home_bye"] > 0:
        rt_note = f"{home_name} is coming off a bye week (+{BYE_WEEK_BONUS:.0f} ELO pts)."
    elif abs(rt_adj["travel_miles"]) > 1500:
        rt_note = (f"{away_name} is traveling {rt_adj['travel_miles']:.0f} miles, "
                   f"applying a {abs(rt_adj['travel_penalty']):.1f}-ELO penalty.")
    elif rt_adj["away_short_week"] < 0:
        rt_note = f"{away_name} is on a short week, applying a fatigue penalty."
    else:
        home_rest = rt_adj["home_rest_days"]
        away_rest = rt_adj["away_rest_days"]
        rt_note = (f"{home_name} has {home_rest} days of rest versus "
                   f"{away_name}'s {away_rest} days.")
    sentences.append(rt_note)

    # 4. Monte Carlo margin
    margin = mc["median_margin"]
    sign = "by" if abs(margin) > 0.5 else "in a virtual tie"
    if abs(margin) > 0.5:
        margin_team = home_name if margin > 0 else away_name
        sentences.append(
            f"Monte Carlo simulations (10,000 runs) project {margin_team} winning "
            f"by a median margin of {abs(margin):.1f} points "
            f"(80% CI: {abs(mc['margin_ci_low']):.0f}–{abs(mc['margin_ci_high']):.0f} pts)."
        )
    else:
        sentences.append(
            "Monte Carlo simulations show this game is extremely close with the margin "
            "centered near zero."
        )

    # 5. Market edge
    if market and edge is not None:
        if abs(edge) > 0.03:
            value_team = home_name if edge > 0 else away_name
            direction = "above" if edge > 0 else "below"
            sentences.append(
                f"The model sees {abs(edge):.1%} of value on {value_team}, "
                f"placing our probability {direction} the market's implied odds — "
                f"suggesting potential betting value (reference only, not advice)."
            )
        else:
            sentences.append(
                "The model's probability is closely aligned with the betting market, "
                "indicating limited edge and a well-priced line."
            )
    else:
        conf_str = "high" if winner_prob > 0.70 else ("moderate" if winner_prob > 0.60 else "low")
        sentences.append(
            f"The model's confidence is {conf_str} — "
            f"historical games at this probability bucket have been correct approximately "
            f"{winner_prob:.0%} of the time when properly calibrated."
        )

    return " ".join(sentences)


# Import constant needed in explanation
from models.rest_travel import BYE_WEEK_BONUS
