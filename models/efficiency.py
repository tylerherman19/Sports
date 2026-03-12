"""
Offensive / Defensive Efficiency — System 5
Uses PFR YPP data when available, falls back to ESPN scoring proxy.
"""

import logging
from typing import Dict, Any, Optional

from config import ELO_BASELINE, NFL_TEAMS

logger = logging.getLogger(__name__)


def calculate_efficiency_ratings(
    pfr_stats: Optional[Dict[str, Dict]],
    elo_ratings: Dict[str, Dict],
    sos_weight: float = 1.0,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate offensive/defensive efficiency for all teams.

    Parameters
    ----------
    pfr_stats : dict or None — PFR scraped stats {team: {off_ypp, def_ypp, ...}}
    elo_ratings : dict       — current ELO ratings (used for SOS multiplier)
    sos_weight : float       — scale factor for SOS multiplier (slider)

    Returns
    -------
    dict keyed by team abbreviation:
        off_eff      — offensive efficiency (relative to league avg)
        def_eff      — defensive efficiency (relative to league avg)
        net_eff      — off_eff - def_eff
        eff_elo      — ELO equivalent (1500 + net_eff * 150)
        sos_mult     — strength of schedule multiplier
        data_source  — 'pfr' | 'proxy'
    """
    import numpy as np

    results: Dict[str, Dict[str, Any]] = {}

    # Build SOS multipliers using current ELO ratings
    all_elos = [v.get("elo", ELO_BASELINE) for v in elo_ratings.values()]
    league_avg_elo = float(np.mean(all_elos)) if all_elos else ELO_BASELINE

    # ── Try PFR data first ────────────────────────────────────────────────────
    if pfr_stats and len(pfr_stats) >= 20:
        off_ypps = [v["off_ypp"] for v in pfr_stats.values() if v.get("off_ypp")]
        def_ypps = [v["def_ypp"] for v in pfr_stats.values() if v.get("def_ypp")]

        league_avg_off_ypp = float(np.mean(off_ypps)) if off_ypps else 5.5
        league_avg_def_ypp = float(np.mean(def_ypps)) if def_ypps else 5.5

        for team in NFL_TEAMS:
            team_stats = pfr_stats.get(team, {})
            off_ypp = team_stats.get("off_ypp") or league_avg_off_ypp
            def_ypp = team_stats.get("def_ypp") or league_avg_def_ypp

            # SOS from opponent ELO — approximated from h2h records
            opp_elos = _get_opponent_elos(team, elo_ratings)
            avg_opp_elo = float(np.mean(opp_elos)) if opp_elos else league_avg_elo
            sos_mult = 1.0 + (avg_opp_elo / ELO_BASELINE - 1.0) * sos_weight

            off_eff = (off_ypp / league_avg_off_ypp) * sos_mult
            def_eff = (league_avg_def_ypp / def_ypp) * sos_mult
            net_eff = off_eff - def_eff

            results[team] = {
                "off_eff":     off_eff,
                "def_eff":     def_eff,
                "net_eff":     net_eff,
                "eff_elo":     ELO_BASELINE + net_eff * 150.0,
                "sos_mult":    sos_mult,
                "off_ypp":     off_ypp,
                "def_ypp":     def_ypp,
                "data_source": "pfr",
            }

        return results

    # ── Proxy from ELO (scoring-based) ───────────────────────────────────────
    # When PFR data unavailable, approximate efficiency from ELO scores
    for team in NFL_TEAMS:
        team_elo = elo_ratings.get(team, {}).get("elo", ELO_BASELINE)
        opp_elos = _get_opponent_elos(team, elo_ratings)
        avg_opp_elo = float(np.mean(opp_elos)) if opp_elos else league_avg_elo
        sos_mult = 1.0 + (avg_opp_elo / ELO_BASELINE - 1.0) * sos_weight

        # Proxy off/def efficiency from ELO relative to league
        elo_rel = (team_elo - ELO_BASELINE) / 200.0  # normalised
        off_eff = 1.0 + elo_rel * 0.5 * sos_mult
        def_eff = 1.0 + elo_rel * 0.5 * sos_mult
        net_eff = elo_rel * sos_mult

        results[team] = {
            "off_eff":     off_eff,
            "def_eff":     def_eff,
            "net_eff":     net_eff,
            "eff_elo":     ELO_BASELINE + net_eff * 150.0,
            "sos_mult":    sos_mult,
            "off_ypp":     None,
            "def_ypp":     None,
            "data_source": "proxy",
        }

    return results


def _get_opponent_elos(team: str, elo_ratings: Dict[str, Dict]) -> list:
    """Get ELOs of opponents from H2H records."""
    h2h = elo_ratings.get(team, {}).get("h2h_records", {})
    elos = []
    for opp in h2h:
        opp_elo = elo_ratings.get(opp, {}).get("elo", ELO_BASELINE)
        elos.append(opp_elo)
    return elos
