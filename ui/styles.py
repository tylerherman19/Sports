"""
CSS injection for the NFL prediction dashboard.
FiveThirtyEight-inspired dark theme.
"""

import streamlit as st


def inject_styles():
    st.markdown("""
<style>
/* ── Base ───────────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    color: #e6edf3;
}

.stApp {
    background-color: #0d1117;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}

[data-testid="stSidebar"] .css-1d391kg {
    background-color: #161b22;
}

/* ── Headers ────────────────────────────────────────────────────────────── */
h1, h2, h3, h4 {
    color: #e6edf3 !important;
    font-weight: 700;
    letter-spacing: -0.02em;
}

h1 { font-size: 1.8rem; border-bottom: 2px solid #30363d; padding-bottom: 0.5rem; }
h2 { font-size: 1.3rem; }
h3 { font-size: 1.1rem; }

/* ── Tabs ────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    gap: 0;
}

.stTabs [data-baseweb="tab"] {
    color: #8b949e;
    background-color: transparent;
    border: none;
    padding: 0.75rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    color: #58a6ff !important;
    border-bottom: 2px solid #58a6ff !important;
    background-color: transparent;
}

.stTabs [data-baseweb="tab-panel"] {
    padding: 1.5rem 0;
}

/* ── Cards ───────────────────────────────────────────────────────────────── */
.game-card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
}

.game-card:hover {
    border-color: #58a6ff;
}

/* ── Probability bars ────────────────────────────────────────────────────── */
.prob-bar-container {
    width: 100%;
    height: 28px;
    background-color: #21262d;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
    margin: 0.4rem 0;
}

.prob-bar-fill {
    height: 100%;
    display: flex;
    align-items: center;
    padding-left: 8px;
    font-size: 0.8rem;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    border-radius: 4px;
}

/* ── Edge colors ─────────────────────────────────────────────────────────── */
.edge-positive { color: #3fb950 !important; font-weight: 700; }
.edge-negative { color: #f85149 !important; font-weight: 700; }
.edge-neutral  { color: #8b949e !important; }

/* ── Team name styles ────────────────────────────────────────────────────── */
.team-abbr {
    font-size: 1.2rem;
    font-weight: 800;
    letter-spacing: 0.05em;
}

.team-record {
    font-size: 0.8rem;
    color: #8b949e;
}

/* ── Metrics ─────────────────────────────────────────────────────────────── */
.metric-card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
}

.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #58a6ff;
}

.metric-label {
    font-size: 0.75rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.2rem;
}

/* ── Flags ───────────────────────────────────────────────────────────────── */
.flag-overperformer  { color: #3fb950; font-size: 0.75rem; font-weight: 600; }
.flag-underperformer { color: #f85149; font-size: 0.75rem; font-weight: 600; }

/* ── Last updated ────────────────────────────────────────────────────────── */
.last-updated {
    font-size: 0.72rem;
    color: #484f58;
    margin-bottom: 0.75rem;
}

/* ── Uncertainty band ────────────────────────────────────────────────────── */
.uncertainty-band {
    font-size: 0.78rem;
    color: #8b949e;
}

/* ── Kelly note ──────────────────────────────────────────────────────────── */
.kelly-note {
    font-size: 0.7rem;
    color: #484f58;
    font-style: italic;
}

/* ── Dataframe overrides ─────────────────────────────────────────────────── */
.stDataFrame {
    background-color: #161b22;
}

/* ── Input / Select ──────────────────────────────────────────────────────── */
.stSelectbox > div > div {
    background-color: #21262d;
    border-color: #30363d;
    color: #e6edf3;
}

.stSlider > div > div > div > div {
    background-color: #58a6ff;
}

/* ── Expander ────────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
}

/* ── Button ──────────────────────────────────────────────────────────────── */
.stButton > button {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-weight: 500;
}

.stButton > button:hover {
    background-color: #30363d;
    border-color: #58a6ff;
}

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr { border-color: #21262d; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }
</style>
""", unsafe_allow_html=True)


def prob_bar_html(prob: float, color: str, label: str = "") -> str:
    """Render a colored horizontal probability bar."""
    pct = int(prob * 100)
    text = label or f"{pct}%"
    return f"""
<div class="prob-bar-container">
  <div class="prob-bar-fill" style="width:{pct}%; background-color:{color};">
    {text}
  </div>
</div>"""


def team_logo_html(abbr: str, size: int = 48) -> str:
    """Return an <img> tag for a team's ESPN logo."""
    url = f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"
    return f'<img src="{url}" width="{size}" height="{size}" style="object-fit:contain;">'


def edge_html(edge: float) -> str:
    """Colored edge display."""
    if edge is None:
        return '<span class="edge-neutral">—</span>'
    sign = "+" if edge > 0 else ""
    cls = "edge-positive" if edge > 0 else ("edge-negative" if edge < 0 else "edge-neutral")
    return f'<span class="{cls}">{sign}{edge:.1%} edge</span>'


def last_updated_html(fetched_at) -> str:
    """Small grey 'last updated' timestamp."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if fetched_at:
        secs = int((now - fetched_at).total_seconds())
        if secs < 60:
            age = f"{secs}s ago"
        elif secs < 3600:
            age = f"{secs // 60}m ago"
        else:
            age = f"{secs // 3600}h ago"
        ts = fetched_at.strftime("%H:%M:%S UTC")
        return f'<p class="last-updated">Last updated: {ts} ({age})</p>'
    return ""
