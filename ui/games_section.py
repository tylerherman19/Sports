"""
Section 1 — This Week's Games
Shows every current-week matchup with predictions, probability bars,
market edge, ELO, rest/travel, and Monte Carlo margin.
"""

import streamlit as st
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from config import NFL_TEAMS
from ui.styles import prob_bar_html, team_logo_html, edge_html, last_updated_html
from models.ensemble import predict_matchup
from data.espn import get_rest_days


def render_games_section(
    scoreboard: Dict[str, Any],
    team_stats: Dict[str, Any],
    bayesian_ratings: Dict[str, Dict],
    pythagorean_ratings: Dict[str, Dict],
    efficiency_ratings: Dict[str, Dict],
    turnover_adjustments: Dict[str, Dict],
    odds_data: Dict[str, Any],
    params: Dict[str, Any],
    logistic_bundle: Dict,
    xgb_bundle: Dict,
):
    games = scoreboard.get("games", [])
    fetched_at = scoreboard.get("fetched_at")
    week = scoreboard.get("week")

    # Header
    header = f"Week {week}" if week else "Current Week"
    st.markdown(f"## {header} — NFL Games")
    st.markdown(last_updated_html(fetched_at), unsafe_allow_html=True)

    if not games:
        st.info("No games scheduled this week or data unavailable. The NFL season may be in the offseason.")
        return

    odds_dict = odds_data.get("odds", {}) if odds_data else {}

    for game in games:
        _render_game_card(
            game, team_stats, bayesian_ratings, pythagorean_ratings,
            efficiency_ratings, turnover_adjustments, odds_dict,
            params, logistic_bundle, xgb_bundle,
        )


def _render_game_card(
    game: Dict,
    team_stats: Dict[str, Any],
    bayesian_ratings: Dict,
    pythagorean_ratings: Dict,
    efficiency_ratings: Dict,
    turnover_adjustments: Dict,
    odds_dict: Dict,
    params: Dict,
    logistic_bundle: Dict,
    xgb_bundle: Dict,
):
    home = game["home"]
    away = game["away"]
    home_abbr = home["abbr"]
    away_abbr = away["abbr"]

    # Get rest days
    game_date = game.get("date", "")
    home_rest = get_rest_days(home_abbr, game_date) or 7
    away_rest = get_rest_days(away_abbr, game_date) or 7

    # Run ensemble prediction
    try:
        pred = predict_matchup(
            home_abbr, away_abbr,
            params=params,
            logistic_bundle=logistic_bundle,
            xgb_bundle=xgb_bundle,
            team_stats=team_stats,
            bayesian_ratings=bayesian_ratings,
            pythagorean_ratings=pythagorean_ratings,
            efficiency_ratings=efficiency_ratings,
            turnover_adjustments=turnover_adjustments,
            odds_data=odds_dict,
            home_rest_days=home_rest,
            away_rest_days=away_rest,
        )
    except Exception as e:
        st.warning(f"Prediction error for {home_abbr} vs {away_abbr}: {e}")
        return

    home_prob = pred["home_win_prob"]
    away_prob = pred["away_win_prob"]
    winner_abbr = pred["predicted_winner"]
    mc = pred["monte_carlo"]
    edge = pred["edge"]
    market = pred["market"]

    home_color = NFL_TEAMS.get(home_abbr, {}).get("color", "#444")
    away_color = NFL_TEAMS.get(away_abbr, {}).get("color", "#444")
    winner_color = home_color if winner_abbr == home_abbr else away_color

    # Game status label
    status_label = ""
    if game["is_final"]:
        h_sc = game["home_score"] or 0
        a_sc = game["away_score"] or 0
        status_label = f"**FINAL** {home_abbr} {h_sc} — {a_sc} {away_abbr}"
    elif game["is_live"]:
        status_label = f"🔴 **LIVE** Q{game['period']} {game['clock']}"
    else:
        try:
            dt = datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
            status_label = dt.strftime("%a %b %-d, %I:%M %p ET")
        except Exception:
            status_label = game.get("date", "TBD")

    # ── Card HTML ─────────────────────────────────────────────────────────────
    with st.container():
        st.markdown(f'<div class="game-card">', unsafe_allow_html=True)

        # Status row
        st.caption(status_label)

        col_away, col_vs, col_home = st.columns([3, 1, 3])

        # Away team
        with col_away:
            away_info = NFL_TEAMS.get(away_abbr, {})
            away_bay = bayesian_ratings.get(away_abbr, {})
            away_elo = team_stats.get(away_abbr, {}).get("elo", 1500)
            away_sigma = away_bay.get("sigma", 75)
            st.markdown(
                f'{team_logo_html(away_abbr, 52)}'
                f'<div class="team-abbr" style="color:{away_color}">{away_abbr}</div>'
                f'<div class="team-record">{away.get("record","")}</div>'
                f'<div class="uncertainty-band">ELO: {away_elo:.0f} ±{away_sigma:.0f}</div>'
                f'<div class="team-record">Rest: {away_rest}d | '
                f'Travel: {pred["rest_travel"]["travel_miles"]:.0f}mi</div>',
                unsafe_allow_html=True
            )

        # Middle — VS / predicted winner
        with col_vs:
            st.markdown(
                f'<div style="text-align:center;padding-top:12px;">'
                f'<div style="color:#484f58;font-size:0.85rem;font-weight:600">@</div>'
                f'<div style="color:{winner_color};font-size:0.75rem;font-weight:700;margin-top:4px">'
                f'▶ {winner_abbr}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Home team
        with col_home:
            home_info = NFL_TEAMS.get(home_abbr, {})
            home_bay = bayesian_ratings.get(home_abbr, {})
            home_elo = team_stats.get(home_abbr, {}).get("elo", 1500)
            home_sigma = home_bay.get("sigma", 75)
            st.markdown(
                f'{team_logo_html(home_abbr, 52)}'
                f'<div class="team-abbr" style="color:{home_color}">{home_abbr}</div>'
                f'<div class="team-record">{home.get("record","")}</div>'
                f'<div class="uncertainty-band">ELO: {home_elo:.0f} ±{home_sigma:.0f}</div>'
                f'<div class="team-record">Rest: {home_rest}d | Home</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Probability bars
        col_p1, col_p2 = st.columns([1, 1])
        with col_p1:
            st.markdown(
                prob_bar_html(away_prob, away_color, f"{away_abbr} {away_prob:.0%}"),
                unsafe_allow_html=True
            )
        with col_p2:
            st.markdown(
                prob_bar_html(home_prob, home_color, f"{home_abbr} {home_prob:.0%}"),
                unsafe_allow_html=True
            )

        # Monte Carlo margin + edge row
        col_mc, col_edge, col_kelly = st.columns([2, 2, 2])
        with col_mc:
            margin = mc["median_margin"]
            margin_team = home_abbr if margin > 0 else away_abbr
            st.caption(
                f"📊 MC Margin: **{margin_team} +{abs(margin):.1f}** "
                f"(80% CI: {mc['margin_ci_low']:.0f}–{mc['margin_ci_high']:.0f})"
            )
        with col_edge:
            if edge is not None:
                st.markdown(
                    f"Market edge: {edge_html(edge)}",
                    unsafe_allow_html=True
                )
            elif market is None:
                st.caption("🔑 Add Odds API key for market edge")
            else:
                st.caption("No odds available")
        with col_kelly:
            kelly = pred.get("kelly")
            if kelly is not None and kelly > 0:
                st.markdown(
                    f'<span class="kelly-note">Kelly: {kelly:.1%} (ref only)</span>',
                    unsafe_allow_html=True
                )

        st.markdown('</div>', unsafe_allow_html=True)
