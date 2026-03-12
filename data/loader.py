"""
NFL historical game data loader.
Uses nflverse/nfldata games.csv (replaces defunct FiveThirtyEight CSV).

Schema (key columns):
  game_id, season, game_type, week, gameday (date),
  away_team, away_score, home_team, home_score,
  result (home - away), location (home/neutral),
  away_rest, home_rest,
  away_moneyline, home_moneyline, spread_line
"""

import io
import logging

import pandas as pd
import requests
import streamlit as st

from config import FTE_URL, TEAM_538_MAP, CURRENT_SEASON

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner="Downloading NFL historical data…")
def load_538_data() -> pd.DataFrame:
    """
    Download and return the nflverse historical NFL games CSV as a clean DataFrame.
    Cached for the lifetime of the Streamlit session.

    The returned DataFrame uses a standardised schema compatible with the
    rest of the model code (team1/team2 orientation, neutral flag, etc.).
    """
    resp = requests.get(FTE_URL, timeout=30)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), low_memory=False)

    # ── Rename / derive columns to match internal schema ─────────────────────
    # nflverse is HOME-centric (home_team, away_team)
    # We keep "team1 = home, team2 = away" convention

    df = df.rename(columns={
        "gameday":    "date",
        "home_team":  "team1",
        "away_team":  "team2",
        "home_score": "score1",
        "away_score": "score2",
        "home_rest":  "rest1",
        "away_rest":  "rest2",
        "home_moneyline": "ml1",
        "away_moneyline": "ml2",
    })

    df["date"] = pd.to_datetime(df["date"])

    # neutral: location == 'neutral' in nflverse
    df["neutral"] = (df["location"].str.lower() == "neutral").astype(int)

    # Map franchise abbreviations to our standard set
    df["team1_abbr"] = df["team1"].map(TEAM_538_MAP).fillna(df["team1"])
    df["team2_abbr"] = df["team2"].map(TEAM_538_MAP).fillna(df["team2"])

    # Numeric scores
    df["score1"] = pd.to_numeric(df["score1"], errors="coerce")
    df["score2"] = pd.to_numeric(df["score2"], errors="coerce")

    # Rest days (nflverse provides them directly!)
    df["rest1"] = pd.to_numeric(df["rest1"], errors="coerce").fillna(7)
    df["rest2"] = pd.to_numeric(df["rest2"], errors="coerce").fillna(7)

    # Spread and moneyline
    df["spread_line"] = pd.to_numeric(df.get("spread_line"), errors="coerce")
    df["ml1"] = pd.to_numeric(df.get("ml1"), errors="coerce")
    df["ml2"] = pd.to_numeric(df.get("ml2"), errors="coerce")

    # Derive elo1_pre / elo2_pre placeholders (will be computed in ELO module)
    # We keep these columns as NaN until ELO is calculated
    if "elo1_pre" not in df.columns:
        df["elo1_pre"] = float("nan")
    if "elo2_pre" not in df.columns:
        df["elo2_pre"] = float("nan")

    # Sort chronologically
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(
        "Loaded %d historical NFL games (%d – %d) from nflverse.",
        len(df), int(df["season"].min()), int(df["season"].max()),
    )
    return df


def get_completed_games(df: pd.DataFrame, min_season: int = 2000) -> pd.DataFrame:
    """Return only completed games (both scores present) from min_season onwards."""
    mask = (
        df["score1"].notna()
        & df["score2"].notna()
        & (df["season"] >= min_season)
    )
    return df[mask].copy()


def get_current_season_games(df: pd.DataFrame) -> pd.DataFrame:
    """Return all games (complete + future) from the current season."""
    return df[df["season"] == CURRENT_SEASON].copy()


def get_future_games(df: pd.DataFrame) -> pd.DataFrame:
    """Return upcoming (unplayed) games — score fields are null."""
    return df[df["score1"].isna()].copy()
