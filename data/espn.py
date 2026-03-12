"""
ESPN unofficial API client.
Pulls live scoreboard, standings, schedules, and injuries.
No API key required.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from config import (
    ESPN_INJURIES_URL,
    ESPN_SCOREBOARD_URL,
    ESPN_STANDINGS_URL,
    ESPN_SCHEDULE_URL,
    ESPN_ABBR_MAP,
    NFL_TEAMS,
)

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NFLDashboard/1.0)",
    "Accept": "application/json",
}


def _get(url: str, params: Optional[Dict] = None, timeout: int = 15) -> Optional[Dict]:
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("ESPN API request failed: %s — %s", url, exc)
        return None


# ─── Scoreboard ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def load_scoreboard() -> Dict[str, Any]:
    """
    Fetch the current NFL scoreboard.
    Returns a dict with keys:
      'games'          : list of game dicts
      'fetched_at'     : datetime (UTC)
      'week'           : current week number (or None)
      'season_type'    : 'pre' | 'regular' | 'post'
    """
    data = _get(ESPN_SCOREBOARD_URL)
    fetched_at = datetime.now(timezone.utc)

    if not data:
        return {"games": [], "fetched_at": fetched_at, "week": None, "season_type": None}

    games = []
    week = None
    season_type = None

    try:
        cal = data.get("leagues", [{}])[0].get("calendar", [])
        season_type_raw = data.get("season", {}).get("type", {}).get("name", "")
        season_type = _parse_season_type(season_type_raw)

        week_data = data.get("week", {})
        week = week_data.get("number")
    except Exception:
        pass

    for event in data.get("events", []):
        try:
            game = _parse_event(event)
            if game:
                games.append(game)
        except Exception as exc:
            logger.debug("Error parsing event: %s", exc)

    return {
        "games": games,
        "fetched_at": fetched_at,
        "week": week,
        "season_type": season_type,
    }


def _parse_season_type(raw: str) -> str:
    raw_lower = raw.lower()
    if "pre" in raw_lower:
        return "pre"
    if "post" in raw_lower or "playoff" in raw_lower:
        return "post"
    return "regular"


def _parse_event(event: Dict) -> Optional[Dict]:
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    if len(competitors) < 2:
        return None

    # Identify home and away
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    home_team = _parse_team(home)
    away_team = _parse_team(away)
    if not home_team or not away_team:
        return None

    status = competition.get("status", {})
    status_type = status.get("type", {})
    game_status = status_type.get("name", "")  # 'STATUS_FINAL', 'STATUS_IN_PROGRESS', 'STATUS_SCHEDULED'
    display_clock = status.get("displayClock", "")
    period = status.get("period", 0)

    # Odds embedded in competition
    odds_raw = competition.get("odds", [{}])
    spread = None
    over_under = None
    if odds_raw:
        spread = odds_raw[0].get("details")
        over_under = odds_raw[0].get("overUnder")

    game_date = event.get("date", "")
    venue = competition.get("venue", {})
    venue_name = venue.get("fullName", "")
    venue_city = venue.get("address", {}).get("city", "")

    home_score = _safe_int(home.get("score"))
    away_score = _safe_int(away.get("score"))

    return {
        "game_id":       event.get("id", ""),
        "date":          game_date,
        "venue":         venue_name,
        "city":          venue_city,
        "status":        game_status,
        "clock":         display_clock,
        "period":        period,
        "home":          home_team,
        "away":          away_team,
        "home_score":    home_score,
        "away_score":    away_score,
        "spread":        spread,
        "over_under":    over_under,
        "is_final":      game_status == "STATUS_FINAL",
        "is_live":       game_status == "STATUS_IN_PROGRESS",
        "is_scheduled":  game_status == "STATUS_SCHEDULED",
    }


def _parse_team(competitor: Dict) -> Optional[Dict]:
    team = competitor.get("team", {})
    raw_abbr = team.get("abbreviation", "").upper()
    abbr = ESPN_ABBR_MAP.get(raw_abbr, raw_abbr)
    info = NFL_TEAMS.get(abbr, {})

    return {
        "abbr":        abbr,
        "name":        team.get("displayName", info.get("name", abbr)),
        "short_name":  team.get("shortDisplayName", abbr),
        "color":       info.get("color", "#666666"),
        "logo":        f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png",
        "record":      competitor.get("records", [{}])[0].get("summary", "0-0"),
        "score":       _safe_int(competitor.get("score")),
    }


def _safe_int(val) -> Optional[int]:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ─── Standings ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_standings() -> Dict[str, Any]:
    """
    Fetch current NFL standings.
    Returns dict: {team_abbr: {wins, losses, ties, pct, conference, division}}
    """
    data = _get(ESPN_STANDINGS_URL)
    fetched_at = datetime.now(timezone.utc)
    standings: Dict[str, Dict] = {}

    if not data:
        return {"standings": standings, "fetched_at": fetched_at}

    try:
        for conf in data.get("children", []):
            conf_name = conf.get("name", "")
            for div in conf.get("children", []):
                div_name = div.get("name", "")
                for entry in div.get("standings", {}).get("entries", []):
                    team = entry.get("team", {})
                    raw_abbr = team.get("abbreviation", "").upper()
                    abbr = ESPN_ABBR_MAP.get(raw_abbr, raw_abbr)
                    stats_raw = {s["name"]: s["value"] for s in entry.get("stats", [])}
                    standings[abbr] = {
                        "wins":        int(stats_raw.get("wins", 0)),
                        "losses":      int(stats_raw.get("losses", 0)),
                        "ties":        int(stats_raw.get("ties", 0)),
                        "pct":         float(stats_raw.get("winPercent", 0.0)),
                        "points_for":  float(stats_raw.get("pointsFor", 0.0)),
                        "points_against": float(stats_raw.get("pointsAgainst", 0.0)),
                        "conference":  conf_name,
                        "division":    div_name,
                    }
    except Exception as exc:
        logger.warning("Error parsing standings: %s", exc)

    return {"standings": standings, "fetched_at": fetched_at}


# ─── Team Schedule ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_team_schedule(team_abbr: str) -> List[Dict]:
    """Return the full schedule for one team (current season)."""
    team_info = NFL_TEAMS.get(team_abbr)
    if not team_info:
        return []

    url = ESPN_SCHEDULE_URL.format(team_id=team_info["espn_id"])
    data = _get(url)
    if not data:
        return []

    games = []
    try:
        for event in data.get("events", []):
            game = _parse_schedule_event(event, team_abbr)
            if game:
                games.append(game)
    except Exception as exc:
        logger.warning("Error parsing schedule for %s: %s", team_abbr, exc)

    return games


def _parse_schedule_event(event: Dict, team_abbr: str) -> Optional[Dict]:
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    if len(competitors) < 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    home_abbr = ESPN_ABBR_MAP.get(home.get("team", {}).get("abbreviation", "").upper(), "")
    away_abbr = ESPN_ABBR_MAP.get(away.get("team", {}).get("abbreviation", "").upper(), "")

    opponent_abbr = away_abbr if home_abbr == team_abbr else home_abbr
    is_home = home_abbr == team_abbr

    status_type = competition.get("status", {}).get("type", {})
    is_final = status_type.get("name") == "STATUS_FINAL"

    team_comp = home if is_home else away
    opp_comp = away if is_home else home

    result = None
    if is_final:
        my_score = _safe_int(team_comp.get("score"))
        opp_score = _safe_int(opp_comp.get("score"))
        if my_score is not None and opp_score is not None:
            result = "W" if my_score > opp_score else ("L" if my_score < opp_score else "T")

    return {
        "game_id":   event.get("id", ""),
        "date":      event.get("date", ""),
        "week":      event.get("week", {}).get("number"),
        "opponent":  opponent_abbr,
        "is_home":   is_home,
        "is_final":  is_final,
        "result":    result,
        "team_score": _safe_int(team_comp.get("score")),
        "opp_score":  _safe_int(opp_comp.get("score")),
    }


# ─── Injuries ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_injuries() -> Dict[str, List[Dict]]:
    """
    Fetch injury report.
    Returns dict: {team_abbr: [{player, position, status}, ...]}
    """
    data = _get(ESPN_INJURIES_URL)
    fetched_at = datetime.now(timezone.utc)
    injuries: Dict[str, List[Dict]] = {}

    if not data:
        return {"injuries": injuries, "fetched_at": fetched_at}

    try:
        for item in data.get("injuries", []):
            team_raw = item.get("team", {}).get("abbreviation", "").upper()
            abbr = ESPN_ABBR_MAP.get(team_raw, team_raw)
            player = item.get("athlete", {})
            injuries.setdefault(abbr, []).append({
                "player":   player.get("displayName", ""),
                "position": player.get("position", {}).get("abbreviation", ""),
                "status":   item.get("status", {}).get("type", {}).get("description", ""),
            })
    except Exception as exc:
        logger.warning("Error parsing injuries: %s", exc)

    return {"injuries": injuries, "fetched_at": fetched_at}


def get_rest_days(team_abbr: str, before_date: str) -> Optional[int]:
    """
    Estimate days of rest before `before_date` for a team by looking at
    their most recent completed game.
    """
    schedule = load_team_schedule(team_abbr)
    before_dt = pd.to_datetime(before_date) if before_date else datetime.now(timezone.utc)

    import pandas as pd
    completed = [
        g for g in schedule
        if g["is_final"] and pd.to_datetime(g["date"]) < pd.to_datetime(str(before_dt))
    ]
    if not completed:
        return 7  # Default full week

    last_game = max(completed, key=lambda g: g["date"])
    last_dt = pd.to_datetime(last_game["date"])
    before_dt_naive = pd.to_datetime(str(before_dt)).tz_localize(None) if pd.to_datetime(str(before_dt)).tzinfo else pd.to_datetime(str(before_dt))
    last_dt_naive = last_dt.tz_localize(None) if last_dt.tzinfo else last_dt

    return max(0, (before_dt_naive - last_dt_naive).days)
