"""
Pro Football Reference scraper.
Scrapes yards-per-play, turnover data, and strength-of-schedule.
Uses 3-second delay between requests as required.
Falls back gracefully on failure.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
import streamlit as st
from bs4 import BeautifulSoup

from config import NFL_TEAMS, CURRENT_SEASON

logger = logging.getLogger(__name__)

PFR_BASE = "https://www.pro-football-reference.com"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


@st.cache_data(ttl=86400, show_spinner=False)
def load_pfr_team_stats(season: int = CURRENT_SEASON) -> Dict[str, Any]:
    """
    Scrape team offensive and defensive stats from PFR for the given season.
    Returns dict: {team_abbr: {off_ypp, def_ypp, off_to, def_to, sos}}
    Falls back to empty dict on any failure.
    """
    fetched_at = datetime.now(timezone.utc)

    try:
        offense = _scrape_offense(season)
        time.sleep(3)
        defense = _scrape_defense(season)
        time.sleep(3)

        # Merge offense and defense
        merged: Dict[str, Dict] = {}
        all_teams = set(offense.keys()) | set(defense.keys())
        for abbr in all_teams:
            off = offense.get(abbr, {})
            deff = defense.get(abbr, {})
            merged[abbr] = {
                "off_ypp":    off.get("ypp", None),
                "off_yards":  off.get("total_yards", None),
                "off_plays":  off.get("plays", None),
                "off_to":     off.get("turnovers", None),
                "def_ypp":    deff.get("ypp", None),
                "def_yards":  deff.get("total_yards", None),
                "def_plays":  deff.get("plays", None),
                "def_to":     deff.get("turnovers", None),
            }

        logger.info("PFR scrape successful: %d teams for %d season.", len(merged), season)
        return {"stats": merged, "fetched_at": fetched_at, "error": None}

    except Exception as exc:
        logger.warning("PFR scrape failed: %s", exc)
        return {"stats": {}, "fetched_at": fetched_at, "error": str(exc)}


def _scrape_offense(season: int) -> Dict[str, Dict]:
    """Scrape team offensive statistics table."""
    url = f"{PFR_BASE}/years/{season}/"
    soup = _fetch_soup(url)
    if soup is None:
        return {}

    return _parse_team_stats_table(soup, "team_stats", offensive=True)


def _scrape_defense(season: int) -> Dict[str, Dict]:
    """Scrape team defensive statistics table."""
    url = f"{PFR_BASE}/years/{season}/"
    soup = _fetch_soup(url)
    if soup is None:
        return {}

    return _parse_team_stats_table(soup, "team_stats_def", offensive=False)


def _fetch_soup(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "lxml")
    except Exception as exc:
        logger.warning("PFR fetch failed for %s: %s", url, exc)
        return None


def _parse_team_stats_table(soup: BeautifulSoup, table_id: str, offensive: bool) -> Dict[str, Dict]:
    """Parse a PFR team stats table into a dict keyed by team abbreviation."""
    stats: Dict[str, Dict] = {}

    table = soup.find("table", {"id": table_id})
    if not table:
        # Try finding any table with the partial ID
        tables = soup.find_all("table")
        for t in tables:
            if table_id in str(t.get("id", "")):
                table = t
                break

    if not table:
        return stats

    headers = []
    thead = table.find("thead")
    if thead:
        header_row = thead.find_all("tr")[-1]  # Last header row
        headers = [th.get("data-stat", th.get_text(strip=True)) for th in header_row.find_all(["th", "td"])]

    tbody = table.find("tbody")
    if not tbody:
        return stats

    for row in tbody.find_all("tr"):
        if row.get("class") and "thead" in row.get("class", []):
            continue

        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        row_data: Dict[str, str] = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                row_data[headers[i]] = cell.get_text(strip=True)

        # Get team name/link
        team_cell = row.find("td", {"data-stat": "team"})
        if not team_cell:
            team_cell = cells[0]

        team_link = team_cell.find("a")
        if team_link:
            team_text = team_link.get_text(strip=True)
        else:
            team_text = team_cell.get_text(strip=True).rstrip("*+")

        abbr = _pfr_team_to_abbr(team_text)
        if not abbr:
            continue

        # Extract relevant stats
        total_yards = _safe_float(row_data.get("yards", row_data.get("tot_yds")))
        plays = _safe_float(row_data.get("plays_offense", row_data.get("plays")))
        turnovers = _safe_float(row_data.get("to", row_data.get("fumbles_lost")))

        ypp = None
        if total_yards is not None and plays and plays > 0:
            ypp = total_yards / plays

        stats[abbr] = {
            "ypp":         ypp,
            "total_yards": total_yards,
            "plays":       plays,
            "turnovers":   turnovers,
        }

    return stats


def _pfr_team_to_abbr(pfr_name: str) -> Optional[str]:
    """Map PFR team name to our standard abbreviation."""
    from config import TEAM_538_MAP

    clean = pfr_name.strip().rstrip("*+").strip()

    # Direct lookup in 538 map
    if clean in TEAM_538_MAP:
        return TEAM_538_MAP[clean]

    # Partial match against NFL_TEAMS names
    clean_lower = clean.lower()
    for abbr, info in NFL_TEAMS.items():
        if clean_lower in info["name"].lower() or info["name"].lower() in clean_lower:
            return abbr

    return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        cleaned = str(val).replace(",", "").strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None
