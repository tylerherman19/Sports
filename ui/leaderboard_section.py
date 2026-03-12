"""
Section 4 — ELO Leaderboard
All 32 teams, sortable, with logos, ELO ± uncertainty, Pythagorean, efficiency,
playoff probability, trend, and regression flags.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any

from config import NFL_TEAMS
from ui.styles import last_updated_html


def render_leaderboard_section(
    team_stats: Dict[str, Any],
    bayesian_ratings: Dict[str, Dict],
    pythagorean_ratings: Dict[str, Dict],
    efficiency_ratings: Dict[str, Dict],
    season_sim_results: Dict[str, Dict],
    standings: Dict[str, Dict],
    fetched_at=None,
):
    st.markdown("## ELO Leaderboard — All 32 Teams")
    st.markdown(last_updated_html(fetched_at), unsafe_allow_html=True)

    rows = []
    for abbr in NFL_TEAMS:
        ts = team_stats.get(abbr, {})
        bay = bayesian_ratings.get(abbr, {})
        pyth = pythagorean_ratings.get(abbr, {})
        eff = efficiency_ratings.get(abbr, {})
        sim = season_sim_results.get(abbr, {})
        std = standings.get(abbr, {})
        info = NFL_TEAMS[abbr]

        wins = ts.get("wins", std.get("wins", 0))
        losses = ts.get("losses", std.get("losses", 0))
        record = f"{wins}-{losses}"

        elo = ts.get("elo", 1500.0)
        sigma = bay.get("sigma", 75.0)
        elo_display = f"{elo:.0f} ±{sigma:.0f}"

        # Trend: ELO change over last 3 weeks
        history = ts.get("elo_history", [])
        trend = _elo_trend(history)
        trend_arrow = "▲" if trend > 5 else ("▼" if trend < -5 else "→")
        trend_color = "#3fb950" if trend > 5 else ("#f85149" if trend < -5 else "#8b949e")

        pyth_exp = pyth.get("pyth_exp", 0.5)
        flag = pyth.get("flag")
        flag_str = "⬆ Over" if flag == "overperformer" else ("⬇ Under" if flag == "underperformer" else "—")

        playoff_prob = sim.get("playoff_prob", None)
        playoff_str = f"{playoff_prob:.0%}" if playoff_prob is not None else "—"

        net_eff = eff.get("net_eff", 0.0)

        rows.append({
            "Team":        abbr,
            "Name":        info["name"],
            "Record":      record,
            "ELO ±σ":      elo_display,
            "_elo_raw":    elo,
            "_sigma_raw":  sigma,
            "Pyth Exp":    f"{pyth_exp:.1%}",
            "Net Eff":     f"{net_eff:+.3f}",
            "Playoff %":   playoff_str,
            "Trend":       f"{trend_arrow} {abs(trend):.0f}",
            "_trend_val":  trend,
            "Flag":        flag_str,
            "_flag_raw":   flag or "",
        })

    df = pd.DataFrame(rows)

    # Sort selector
    sort_col = st.selectbox(
        "Sort by",
        options=["ELO ±σ", "Record", "Pyth Exp", "Net Eff", "Playoff %"],
        index=0,
    )

    if sort_col == "ELO ±σ":
        df = df.sort_values("_elo_raw", ascending=False)
    elif sort_col == "Record":
        df["_wins"] = df["Record"].apply(lambda r: int(r.split("-")[0]) if "-" in r else 0)
        df = df.sort_values("_wins", ascending=False)
    elif sort_col == "Pyth Exp":
        df = df.sort_values("Pyth Exp", ascending=False)
    elif sort_col == "Net Eff":
        df["_net_eff_raw"] = df["Net Eff"].apply(lambda x: float(x) if x else 0.0)
        df = df.sort_values("_net_eff_raw", ascending=False)
    elif sort_col == "Playoff %":
        df["_poff"] = df["Playoff %"].apply(
            lambda x: float(x.strip("%")) / 100 if x != "—" else -1.0
        )
        df = df.sort_values("_poff", ascending=False)

    df = df.reset_index(drop=True)
    df.index += 1  # 1-based ranking

    # Render using a styled HTML table for logo support
    st.markdown(_build_leaderboard_html(df), unsafe_allow_html=True)

    # ELO distribution chart
    st.markdown("### ELO Distribution")
    _render_elo_distribution(df)


def _elo_trend(history: list) -> float:
    """ELO change over approximately last 3 weeks (last 3 data points)."""
    if len(history) < 2:
        return 0.0
    recent = history[-3:]
    if len(recent) >= 2:
        return recent[-1][1] - recent[0][1]
    return 0.0


def _build_leaderboard_html(df: pd.DataFrame) -> str:
    rows_html = ""
    for rank, row in df.iterrows():
        abbr = row["Team"]
        info = NFL_TEAMS.get(abbr, {})
        color = info.get("color", "#666")
        logo = f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"
        flag_raw = row.get("_flag_raw", "")
        flag_class = f"flag-{flag_raw}" if flag_raw else ""
        trend_val = row.get("_trend_val", 0)
        trend_color = "#3fb950" if trend_val > 5 else ("#f85149" if trend_val < -5 else "#8b949e")

        rows_html += f"""
        <tr>
          <td style="color:#484f58;text-align:center">{rank}</td>
          <td>
            <img src="{logo}" width="28" height="28" style="vertical-align:middle;margin-right:6px">
            <span style="color:{color};font-weight:700">{abbr}</span>
          </td>
          <td style="color:#8b949e;font-size:0.85rem">{row["Record"]}</td>
          <td><span style="color:{color};font-weight:600">{row["ELO ±σ"]}</span></td>
          <td>{row["Pyth Exp"]}</td>
          <td>{row["Net Eff"]}</td>
          <td><b>{row["Playoff %"]}</b></td>
          <td style="color:{trend_color}">{row["Trend"]}</td>
          <td class="{flag_class}">{row["Flag"]}</td>
        </tr>"""

    return f"""
<style>
.lb-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    color: #e6edf3;
}}
.lb-table th {{
    background: #161b22;
    color: #8b949e;
    padding: 8px 10px;
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #30363d;
}}
.lb-table td {{
    padding: 7px 10px;
    border-bottom: 1px solid #21262d;
    vertical-align: middle;
}}
.lb-table tr:hover td {{ background: #161b22; }}
.flag-overperformer {{ color: #3fb950; font-size: 0.75rem; font-weight: 600; }}
.flag-underperformer {{ color: #f85149; font-size: 0.75rem; font-weight: 600; }}
</style>
<table class="lb-table">
  <thead>
    <tr>
      <th>#</th><th>Team</th><th>Record</th>
      <th>ELO ±σ</th><th>Pyth Exp</th><th>Net Eff</th>
      <th>Playoff %</th><th>Trend</th><th>Flag</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>"""


def _render_elo_distribution(df: pd.DataFrame):
    """Bar chart of team ELOs sorted by rating."""
    df_sorted = df.sort_values("_elo_raw", ascending=True)
    colors = [NFL_TEAMS.get(a, {}).get("color", "#444") for a in df_sorted["Team"]]
    labels = df_sorted["Team"].tolist()
    elos = df_sorted["_elo_raw"].tolist()
    sigmas = df_sorted["_sigma_raw"].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels,
        x=elos,
        orientation="h",
        marker_color=colors,
        error_x=dict(type="data", array=sigmas, visible=True, color="#484f58"),
        hovertemplate="%{y}: %{x:.0f} ELO<extra></extra>",
    ))
    fig.add_vline(x=1500, line_color="#30363d", line_dash="dash", line_width=1)
    fig.update_layout(
        plot_bgcolor="#0d1117",
        paper_bgcolor="#0d1117",
        font_color="#e6edf3",
        xaxis_title="ELO Rating",
        yaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=0, r=0, t=10, b=0),
        height=700,
    )
    st.plotly_chart(fig, use_container_width=True)
