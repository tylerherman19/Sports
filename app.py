"""
NFL Prediction Dashboard
Run with: streamlit run app.py
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import numpy as np
import streamlit as st

# ── Page config (MUST be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="NFL Prediction Dashboard",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_AVAILABLE = True
except ImportError:
    _AUTOREFRESH_AVAILABLE = False

# ── Internal imports ──────────────────────────────────────────────────────────
from config import DEFAULT_PARAMS, NFL_TEAMS, CURRENT_SEASON
from data.loader import load_538_data, get_completed_games
from data.espn import load_scoreboard, load_standings, load_injuries
from data.odds import load_odds
from data.pfr import load_pfr_team_stats
from models.features import build_training_features
from models.logistic_model import train_logistic_model
from models.xgboost_model import train_xgboost_model
from models.elo import calculate_elo_ratings, elo_to_prob
from models.bayesian import calculate_bayesian_ratings
from models.pythagorean import calculate_pythagorean_ratings
from models.efficiency import calculate_efficiency_ratings
from models.turnover import calculate_turnover_adjustments
from models.hierarchical import calculate_hierarchical_ratings
from models.monte_carlo import simulate_season, AFC_TEAMS, NFC_TEAMS
from models.ensemble import predict_matchup
from ui.styles import inject_styles
from ui.games_section import render_games_section
from ui.predictor_section import render_predictor_section
from ui.leaderboard_section import render_leaderboard_section
from ui.performance_section import render_performance_section


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — All control parameters
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> Dict[str, Any]:
    """Render sidebar sliders and return params dict."""
    with st.sidebar:
        st.markdown("# ⚙️ Model Controls")

        # ── Auto-refresh ──────────────────────────────────────────────────────
        st.markdown("### Live Data")
        refresh_options = {"15s": 15, "30s": 30, "60s": 60, "Off": 0}
        refresh_label = st.selectbox(
            "Auto-refresh interval",
            options=list(refresh_options.keys()),
            index=1,
        )
        refresh_interval = refresh_options[refresh_label]

        if st.button("⟳ Refresh Now"):
            st.cache_data.clear()
            st.rerun()

        # ── Odds API key ──────────────────────────────────────────────────────
        st.markdown("### Market Data")
        odds_api_key = st.secrets.get("ODDS_API_KEY", "") if hasattr(st, "secrets") else ""
        if not odds_api_key:
            odds_api_key = st.text_input(
                "Odds API Key (optional)",
                type="password",
                placeholder="Enter key from the-odds-api.com",
                help="Free tier: https://the-odds-api.com",
            )

        st.markdown("---")

        # ── ELO Parameters ────────────────────────────────────────────────────
        st.markdown("### ELO Parameters")
        k_factor = st.slider("K-Factor (sensitivity)", 10, 40, DEFAULT_PARAMS["k_factor"])
        mov_weight = st.slider("MOV Weight", 0.0, 2.0, float(DEFAULT_PARAMS["mov_weight"]), 0.1)
        home_field = st.slider("Home Field Advantage (ELO pts)", 0, 80, DEFAULT_PARAMS["home_field"])
        recent_form_pct = st.slider("Recent Form Blend %", 0, 100, DEFAULT_PARAMS["recent_form_pct"])
        h2h_weight = st.slider("Head-to-Head Weight %", 0, 100, DEFAULT_PARAMS["h2h_weight"])

        st.markdown("---")

        # ── Adjustment Scales ─────────────────────────────────────────────────
        st.markdown("### Adjustment Scales")
        sos_weight = st.slider("SOS Weight", 0.0, 2.0, float(DEFAULT_PARAMS["sos_weight"]), 0.1)
        turnover_impact = st.slider("Turnover Impact", 0.0, 2.0, float(DEFAULT_PARAMS["turnover_impact"]), 0.1)
        rest_travel_scale = st.slider("Rest & Travel Scale", 0.0, 2.0, float(DEFAULT_PARAMS["rest_travel_scale"]), 0.1)
        time_decay_lambda = st.slider("Time Decay λ", 0.01, 0.15, DEFAULT_PARAMS["time_decay_lambda"], 0.01)

        st.markdown("---")

        # ── Ensemble Weights ──────────────────────────────────────────────────
        st.markdown("### Ensemble Weights")
        st.caption("Weights are auto-normalised to sum to 100%.")
        w_logistic = st.slider("Logistic Regression", 0, 100, DEFAULT_PARAMS["w_logistic"])
        w_xgb      = st.slider("XGBoost",             0, 100, DEFAULT_PARAMS["w_xgb"])
        w_elo      = st.slider("ELO Rating",           0, 100, DEFAULT_PARAMS["w_elo"])
        w_pyth     = st.slider("Pythagorean",          0, 100, DEFAULT_PARAMS["w_pyth"])
        w_eff      = st.slider("Efficiency",           0, 100, DEFAULT_PARAMS["w_eff"])

        total_w = w_logistic + w_xgb + w_elo + w_pyth + w_eff
        if total_w > 0:
            st.caption(f"Total: {total_w} → normalized to 100%")
        else:
            st.warning("All weights are 0 — using defaults.")
            w_logistic, w_xgb, w_elo, w_pyth, w_eff = 30, 25, 20, 15, 10

        st.markdown("---")

        # ── Injury Discounts ──────────────────────────────────────────────────
        with st.expander("Injury Discounts (ELO pts subtracted)"):
            injury_discounts: Dict[str, float] = {}
            for abbr in sorted(NFL_TEAMS.keys()):
                disc = st.slider(abbr, 0, 200, 0, 5, key=f"inj_{abbr}")
                if disc > 0:
                    injury_discounts[abbr] = float(disc)

    return {
        "k_factor":          k_factor,
        "mov_weight":        mov_weight,
        "home_field":        home_field,
        "recent_form_pct":   recent_form_pct,
        "sos_weight":        sos_weight,
        "h2h_weight":        h2h_weight,
        "turnover_impact":   turnover_impact,
        "rest_travel_scale": rest_travel_scale,
        "time_decay_lambda": time_decay_lambda,
        "w_logistic":        w_logistic,
        "w_xgb":             w_xgb,
        "w_elo":             w_elo,
        "w_pyth":            w_pyth,
        "w_eff":             w_eff,
        "injury_discounts":  injury_discounts,
        "odds_api_key":      odds_api_key,
        "refresh_interval":  refresh_interval,
    }


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADING — Cached appropriately
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading historical NFL data and training models…")
def get_trained_models(time_decay_lambda: float = 0.05):
    """Train and cache logistic + XGBoost models. Runs once per session."""
    df = load_538_data()
    logistic = train_logistic_model(df, time_decay_lambda=time_decay_lambda)
    xgb = train_xgboost_model(df, time_decay_lambda=time_decay_lambda)
    return logistic, xgb


def load_all_live_data(odds_api_key: str) -> Dict[str, Any]:
    """Load all live/cached data sources."""
    scoreboard = load_scoreboard()
    standings_data = load_standings()
    injuries_data = load_injuries()
    pfr_data = load_pfr_team_stats(CURRENT_SEASON)
    odds_data = load_odds(odds_api_key) if odds_api_key else {"odds": {}, "fetched_at": None, "error": "No key"}

    return {
        "scoreboard":   scoreboard,
        "standings":    standings_data.get("standings", {}),
        "injuries":     injuries_data.get("injuries", {}),
        "pfr":          pfr_data.get("stats", {}),
        "odds":         odds_data,
        "fetched_at":   scoreboard.get("fetched_at"),
    }


def compute_team_stats(
    df,
    live_data: Dict,
    params: Dict,
) -> Dict[str, Any]:
    """
    Compute all current team statistics.
    ELO recalculates with every slider change (fast).
    """
    standings = live_data["standings"]
    pfr_stats = live_data["pfr"] if live_data["pfr"] else None

    # ── ELO ratings (parameterised — recalculates on slider change) ───────────
    elo_ratings = calculate_elo_ratings(
        df,
        k=params["k_factor"],
        mov_weight=params["mov_weight"],
        home_field=params["home_field"],
        recent_form_pct=params["recent_form_pct"],
        h2h_weight=params["h2h_weight"],
        turnover_impact=params["turnover_impact"],
        rest_travel_scale=params["rest_travel_scale"],
        injury_discounts=params["injury_discounts"],
    )

    # ── Bayesian ratings ──────────────────────────────────────────────────────
    bayesian_ratings = calculate_bayesian_ratings(df, elo_ratings, CURRENT_SEASON)

    # ── Pythagorean ───────────────────────────────────────────────────────────
    pythagorean_ratings = calculate_pythagorean_ratings(df, standings, CURRENT_SEASON)

    # ── Efficiency ────────────────────────────────────────────────────────────
    efficiency_ratings = calculate_efficiency_ratings(pfr_stats, elo_ratings, params["sos_weight"])

    # ── Turnover regression ───────────────────────────────────────────────────
    turnover_adjustments = calculate_turnover_adjustments(
        pfr_stats, elo_ratings, params["turnover_impact"], CURRENT_SEASON
    )

    # ── Hierarchical model ────────────────────────────────────────────────────
    hierarchical_ratings = calculate_hierarchical_ratings(df, pfr_stats, CURRENT_SEASON)

    # ── Merge into unified team_stats dict ────────────────────────────────────
    team_stats: Dict[str, Any] = {}
    for team in NFL_TEAMS:
        er = elo_ratings.get(team, {})
        bay = bayesian_ratings.get(team, {})
        pyth = pythagorean_ratings.get(team, {})
        eff = efficiency_ratings.get(team, {})
        to = turnover_adjustments.get(team, {})
        hier = hierarchical_ratings.get(team, {})
        std = standings.get(team, {})

        wins = er.get("wins", std.get("wins", 0))
        losses = er.get("losses", std.get("losses", 0))
        last5 = er.get("last5", [])
        last5_wr = sum(1 for r in last5 if r == "W") / len(last5) if last5 else 0.5

        team_stats[team] = {
            # ELO
            "elo":           er.get("elo", 1500.0),
            "elo_full":      er.get("elo_full", 1500.0),
            "elo_recent":    er.get("elo_recent", 1500.0),
            "games_played":  er.get("games_played", 0),
            "wins":          wins,
            "losses":        losses,
            "last5":         last5,
            "last5_wr":      last5_wr,
            "elo_history":   er.get("elo_history", []),
            "h2h_records":   er.get("h2h_records", {}),

            # Bayesian
            "bayesian_mu":   bay.get("mu", 1500.0),
            "bayesian_sigma": bay.get("sigma", 75.0),

            # Pythagorean
            "pyth_exp":      pyth.get("pyth_exp", 0.5),
            "pyth_elo":      pyth.get("pyth_elo", 1500.0),
            "pyth_flag":     pyth.get("flag"),

            # Efficiency
            "off_eff":       eff.get("off_eff", 1.0),
            "def_eff":       eff.get("def_eff", 1.0),
            "net_eff":       eff.get("net_eff", 0.0),
            "eff_elo":       eff.get("eff_elo", 1500.0),
            "sos_mult":      eff.get("sos_mult", 1.0),

            # Turnovers
            "adj_to_diff":   to.get("adj_to_diff", 0.0),

            # Hierarchical
            "hier_off":      hier.get("off_rating", 0.0),
            "hier_def":      hier.get("def_rating", 0.0),
            "hier_rating":   hier.get("team_rating", 0.0),
        }

    return team_stats, bayesian_ratings, pythagorean_ratings, efficiency_ratings, turnover_adjustments


def compute_season_simulations(
    team_stats: Dict,
    bayesian_ratings: Dict,
    df,
    params: Dict,
    logistic_bundle: Dict,
    xgb_bundle: Dict,
) -> Dict[str, Dict]:
    """Run Monte Carlo season simulations for playoff probabilities."""
    try:
        future = df[df["score1"].isna() & (df["season"] == CURRENT_SEASON)].copy()
        remaining_schedule = []
        ensemble_probs = {}

        for _, row in future.iterrows():
            h = row["team1_abbr"]
            a = row["team2_abbr"]
            neutral = int(row.get("neutral", 0))
            remaining_schedule.append((h, a, bool(neutral)))

            try:
                p = predict_matchup(
                    h, a, params=params,
                    logistic_bundle=logistic_bundle,
                    xgb_bundle=xgb_bundle,
                    team_stats=team_stats,
                    bayesian_ratings=bayesian_ratings,
                    pythagorean_ratings={},
                    efficiency_ratings={},
                    turnover_adjustments={},
                )
                ensemble_probs[f"{h}_vs_{a}"] = {"home_prob": p["home_win_prob"]}
            except Exception:
                ensemble_probs[f"{h}_vs_{a}"] = {"home_prob": 0.5}

        all_teams = list(NFL_TEAMS.keys())
        sim_results = simulate_season(
            teams=all_teams,
            remaining_schedule=remaining_schedule,
            bayesian_ratings=bayesian_ratings,
            ensemble_probs=ensemble_probs,
            n=1000,  # Use 1000 for speed in season sims; full 10k for single matchup
        )
        return sim_results
    except Exception as e:
        logger.warning("Season simulation failed: %s", e)
        return {team: {"playoff_prob": None, "bye_prob": None, "expected_wins": None}
                for team in NFL_TEAMS}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    inject_styles()

    # Auto-refresh (must happen early)
    # We do it after sidebar render so interval is correct
    params = render_sidebar()

    if _AUTOREFRESH_AVAILABLE and params["refresh_interval"] > 0:
        st_autorefresh(interval=params["refresh_interval"] * 1000, key="autorefresh")

    # ── Title bar ─────────────────────────────────────────────────────────────
    col_title, col_refresh_info = st.columns([4, 1])
    with col_title:
        st.markdown("# 🏈 NFL Prediction Dashboard")
        st.caption(f"Season {CURRENT_SEASON} · Model: Ensemble (Logistic + XGBoost + ELO + Pythagorean + Efficiency)")
    with col_refresh_info:
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        st.caption(f"Page loaded: {now_str}")
        if params["refresh_interval"] > 0:
            st.caption(f"Auto-refreshing every {params['refresh_interval']}s")

    # ── Load historical 538 data + train models ───────────────────────────────
    with st.spinner("Loading data and training models (first run only)…"):
        df_538 = load_538_data()
        logistic_bundle, xgb_bundle = get_trained_models(params["time_decay_lambda"])

    # ── Load live data ────────────────────────────────────────────────────────
    with st.spinner("Fetching live data…"):
        live_data = load_all_live_data(params["odds_api_key"])

    # ── Compute team stats (recalculates with slider changes) ─────────────────
    (
        team_stats,
        bayesian_ratings,
        pythagorean_ratings,
        efficiency_ratings,
        turnover_adjustments,
    ) = compute_team_stats(df_538, live_data, params)

    # ── Season simulations (run in background; 1k sims for speed) ────────────
    season_sim_results = compute_season_simulations(
        team_stats, bayesian_ratings, df_538, params, logistic_bundle, xgb_bundle
    )

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 This Week's Games",
        "🔍 Matchup Predictor",
        "📊 ELO Leaderboard",
        "📈 Model Performance",
    ])

    with tab1:
        render_games_section(
            scoreboard=live_data["scoreboard"],
            team_stats=team_stats,
            bayesian_ratings=bayesian_ratings,
            pythagorean_ratings=pythagorean_ratings,
            efficiency_ratings=efficiency_ratings,
            turnover_adjustments=turnover_adjustments,
            odds_data=live_data["odds"],
            params=params,
            logistic_bundle=logistic_bundle,
            xgb_bundle=xgb_bundle,
        )

    with tab2:
        render_predictor_section(
            team_stats=team_stats,
            bayesian_ratings=bayesian_ratings,
            pythagorean_ratings=pythagorean_ratings,
            efficiency_ratings=efficiency_ratings,
            turnover_adjustments=turnover_adjustments,
            odds_data=live_data["odds"],
            params=params,
            logistic_bundle=logistic_bundle,
            xgb_bundle=xgb_bundle,
        )

    with tab3:
        render_leaderboard_section(
            team_stats=team_stats,
            bayesian_ratings=bayesian_ratings,
            pythagorean_ratings=pythagorean_ratings,
            efficiency_ratings=efficiency_ratings,
            season_sim_results=season_sim_results,
            standings=live_data["standings"],
            fetched_at=live_data["fetched_at"],
        )

    with tab4:
        render_performance_section(
            logistic_bundle=logistic_bundle,
            xgb_bundle=xgb_bundle,
        )


if __name__ == "__main__":
    main()
