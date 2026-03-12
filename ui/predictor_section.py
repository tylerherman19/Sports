"""
Section 3 — Matchup Predictor
Two team dropdowns → full prediction breakdown.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, Any

from config import NFL_TEAMS
from ui.styles import prob_bar_html, team_logo_html, edge_html
from models.ensemble import predict_matchup
from data.espn import get_rest_days


def render_predictor_section(
    team_stats: Dict[str, Any],
    bayesian_ratings: Dict,
    pythagorean_ratings: Dict,
    efficiency_ratings: Dict,
    turnover_adjustments: Dict,
    odds_data: Dict,
    params: Dict,
    logistic_bundle: Dict,
    xgb_bundle: Dict,
):
    st.markdown("## Matchup Predictor")
    st.markdown("Select any two teams for a full prediction breakdown.")

    teams_sorted = sorted(NFL_TEAMS.keys())
    team_options = [f"{abbr} — {NFL_TEAMS[abbr]['name']}" for abbr in teams_sorted]

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        away_sel = st.selectbox(
            "Away Team",
            options=team_options,
            index=team_options.index("SF — San Francisco 49ers") if "SF — San Francisco 49ers" in team_options else 0,
            key="pred_away",
        )
        away_abbr = away_sel.split(" — ")[0]

    with col2:
        st.markdown("<div style='text-align:center;padding-top:32px;font-size:1.2rem;color:#484f58'>@</div>",
                    unsafe_allow_html=True)

    with col3:
        home_sel = st.selectbox(
            "Home Team",
            options=team_options,
            index=team_options.index("KC — Kansas City Chiefs") if "KC — Kansas City Chiefs" in team_options else 1,
            key="pred_home",
        )
        home_abbr = home_sel.split(" — ")[0]

    if home_abbr == away_abbr:
        st.warning("Select two different teams.")
        return

    # Rest days
    home_rest = params.get("_home_rest_days", {}).get(home_abbr, 7)
    away_rest = params.get("_away_rest_days", {}).get(away_abbr, 7)

    # Manual rest override
    with st.expander("Override rest days"):
        c1, c2 = st.columns(2)
        with c1:
            home_rest = st.number_input(f"{home_abbr} rest days", 1, 21, value=int(home_rest), key="h_rest")
        with c2:
            away_rest = st.number_input(f"{away_abbr} rest days", 1, 21, value=int(away_rest), key="a_rest")

    odds_dict = odds_data.get("odds", {}) if odds_data else {}

    # Run prediction
    with st.spinner("Running prediction…"):
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
                home_rest_days=int(home_rest),
                away_rest_days=int(away_rest),
            )
        except Exception as e:
            st.error(f"Prediction error: {e}")
            return

    home_prob = pred["home_win_prob"]
    away_prob = pred["away_win_prob"]
    home_color = NFL_TEAMS.get(home_abbr, {}).get("color", "#444")
    away_color = NFL_TEAMS.get(away_abbr, {}).get("color", "#444")
    home_name = NFL_TEAMS.get(home_abbr, {}).get("name", home_abbr)
    away_name = NFL_TEAMS.get(away_abbr, {}).get("name", away_abbr)

    st.markdown("---")

    # ── Win probability bar ───────────────────────────────────────────────────
    st.markdown("### Win Probability")
    col_a, col_h = st.columns(2)
    with col_a:
        st.markdown(
            team_logo_html(away_abbr, 40)
            + f'<div class="team-abbr" style="color:{away_color}">{away_abbr}</div>',
            unsafe_allow_html=True
        )
        st.markdown(prob_bar_html(away_prob, away_color, f"{away_abbr} {away_prob:.1%}"), unsafe_allow_html=True)
    with col_h:
        st.markdown(
            team_logo_html(home_abbr, 40)
            + f'<div class="team-abbr" style="color:{home_color}">{home_abbr}</div>',
            unsafe_allow_html=True
        )
        st.markdown(prob_bar_html(home_prob, home_color, f"{home_abbr} {home_prob:.1%}"), unsafe_allow_html=True)

    # ── ELO breakdown ─────────────────────────────────────────────────────────
    st.markdown("### ELO Breakdown by System")
    systems = {
        "Logistic": pred["logistic_prob"],
        "XGBoost":  pred["xgb_prob"],
        "ELO":      pred["elo_prob"],
        "Pythagorean": pred["pyth_prob"],
        "Efficiency": pred["eff_prob"],
        "**Ensemble**": pred["home_win_prob"],
    }

    _render_elo_bars(home_abbr, home_color, away_abbr, away_color, systems)

    # ── Rest & travel ─────────────────────────────────────────────────────────
    st.markdown("### Rest & Travel Adjustments")
    rt = pred["rest_travel"]
    rt_data = {
        f"{home_abbr} rest":    f"+{rt['home_rest_adj']:.1f} ELO",
        f"{away_abbr} rest":    f"+{rt['away_rest_adj']:.1f} ELO (applied to away)",
        f"{home_abbr} bye":     f"+{rt['home_bye']:.0f}" if rt["home_bye"] else "—",
        f"{away_abbr} bye":     f"+{rt['away_bye']:.0f}" if rt["away_bye"] else "—",
        "Travel penalty":       f"{rt['travel_penalty']:.1f} ELO ({rt['travel_miles']:.0f} mi)",
        "Away short week":      f"{rt['away_short_week']:.0f}" if rt["away_short_week"] else "—",
        "B2B away penalty":     f"{rt['b2b_penalty']:.0f}" if rt["b2b_penalty"] else "—",
        "**Net home advantage**": f"**{rt['net_home_adv']:+.1f} ELO**",
    }
    for label, value in rt_data.items():
        c1, c2 = st.columns([3, 1])
        c1.markdown(label)
        c2.markdown(value)

    # ── Market edge ───────────────────────────────────────────────────────────
    st.markdown("### Market Comparison")
    if pred["market"]:
        market = pred["market"]
        edge = pred["edge"]
        kelly = pred["kelly"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Market (home)", f"{market['home_prob']:.1%}",
                  delta=f"Model: {home_prob:.1%}")
        c2.markdown(f"**Model edge:** {edge_html(edge)}", unsafe_allow_html=True)
        if kelly and kelly > 0:
            c3.metric("Kelly % (ref only)", f"{kelly:.1%}")
            c3.caption("⚠️ For reference only. Not betting advice.")
        else:
            c3.caption("Kelly = 0 (no positive edge)")
    else:
        st.info("Enter your Odds API key in the sidebar to see market comparison.")

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    st.markdown("### Monte Carlo Margin Distribution (10,000 sims)")
    mc = pred["monte_carlo"]
    _render_mc_histogram(mc, home_abbr, home_color, away_abbr, away_color)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Median Margin", f"{'+' if mc['median_margin']>0 else ''}{mc['median_margin']:.1f}")
    col_m2.metric("P(Win by 7+)",  f"{mc['prob_win_by_7']:.0%}")
    col_m3.metric("P(Win by 14+)", f"{mc['prob_win_by_14']:.0%}")
    col_m1.metric("80% CI Low",    f"{mc['margin_ci_low']:.0f}")
    col_m2.metric("80% CI High",   f"{mc['margin_ci_high']:.0f}")
    col_m3.metric("P(Win by 21+)", f"{mc['prob_win_by_21']:.0%}")

    # ── Pythagorean flags ─────────────────────────────────────────────────────
    st.markdown("### Pythagorean Regression Flags")
    c1, c2 = st.columns(2)
    for col, abbr in ((c1, home_abbr), (c2, away_abbr)):
        pyth = pred["home_pyth"] if abbr == home_abbr else pred["away_pyth"]
        flag = pyth.get("flag")
        with col:
            st.markdown(f"**{abbr}**")
            st.markdown(f"Actual W%: {pyth.get('actual_wl_pct', 0):.1%}")
            st.markdown(f"Pythagorean exp: {pyth.get('pyth_exp', 0.5):.1%}")
            st.markdown(f"Deviation: {pyth.get('deviation', 0):+.3f}")
            if flag == "overperformer":
                st.markdown('<span class="flag-overperformer">⬆ Overperformer — may regress</span>', unsafe_allow_html=True)
            elif flag == "underperformer":
                st.markdown('<span class="flag-underperformer">⬇ Underperformer — may improve</span>', unsafe_allow_html=True)
            else:
                st.caption("✓ Performing near expectation")

    # ── Bayesian uncertainty ──────────────────────────────────────────────────
    st.markdown("### Bayesian Uncertainty Bands")
    c1, c2 = st.columns(2)
    for col, abbr in ((c1, home_abbr), (c2, away_abbr)):
        bay = pred["home_bayesian"] if abbr == home_abbr else pred["away_bayesian"]
        with col:
            mu = bay.get("mu", 1500)
            sigma = bay.get("sigma", 75)
            st.markdown(f"**{abbr}** rating: **{mu:.0f}** ± {sigma:.0f}")
            st.markdown(
                f'<div class="uncertainty-band">'
                f'Band: [{mu - sigma:.0f}, {mu + sigma:.0f}]'
                f' | Games: {bay.get("games_played", 0)}</div>',
                unsafe_allow_html=True
            )

    # ── 5-Sentence explanation ────────────────────────────────────────────────
    st.markdown("### Plain-English Summary")
    st.markdown(
        f'<div style="background:#161b22;border:1px solid #30363d;border-radius:6px;'
        f'padding:1rem;line-height:1.7;color:#e6edf3;">'
        f'{pred["explanation"]}</div>',
        unsafe_allow_html=True
    )


def _render_elo_bars(home_abbr, home_color, away_abbr, away_color, systems):
    for system, prob in systems.items():
        bold = "**" in system
        label = system.replace("**", "")
        away_prob = 1.0 - prob
        home_prob_val = prob

        c_label, c_away, c_pct, c_home = st.columns([1.5, 3, 1, 3])
        c_label.caption(label if not bold else f"**{label}**")
        c_away.markdown(
            f'<div style="background:{away_color};height:16px;width:{away_prob*100:.0f}%;'
            f'border-radius:3px;margin-top:4px;"></div>',
            unsafe_allow_html=True
        )
        c_pct.caption(f"{home_prob_val:.0%}")
        c_home.markdown(
            f'<div style="background:{home_color};height:16px;width:{home_prob_val*100:.0f}%;'
            f'border-radius:3px;margin-top:4px;"></div>',
            unsafe_allow_html=True
        )


def _render_mc_histogram(mc, home_abbr, home_color, away_abbr, away_color):
    margins = mc.get("margin_distribution", [])
    if not margins:
        st.caption("No margin data available.")
        return

    fig = go.Figure()
    home_margins = [m for m in margins if m >= 0]
    away_margins = [m for m in margins if m < 0]

    fig.add_trace(go.Histogram(
        x=home_margins,
        nbinsx=30,
        name=f"{home_abbr} wins",
        marker_color=home_color,
        opacity=0.8,
    ))
    fig.add_trace(go.Histogram(
        x=away_margins,
        nbinsx=30,
        name=f"{away_abbr} wins",
        marker_color=away_color,
        opacity=0.8,
    ))
    fig.add_vline(x=0, line_color="#ffffff", line_dash="dash", line_width=1)
    fig.add_vline(x=mc["median_margin"], line_color="#f0c040", line_dash="dot",
                  annotation_text=f"Median {mc['median_margin']:+.1f}", line_width=1.5)

    fig.update_layout(
        barmode="overlay",
        plot_bgcolor="#161b22",
        paper_bgcolor="#0d1117",
        font_color="#e6edf3",
        xaxis_title="Point Margin (home perspective)",
        yaxis_title="Simulations",
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=0, r=0, t=20, b=0),
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True)
