"""
The Odds API client.
Converts American moneyline odds → vig-free implied probabilities.
Calculates model edge and Kelly criterion.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

from config import ODDS_API_URL, ODDS_API_PARAMS

logger = logging.getLogger(__name__)


@st.cache_data(ttl=60, show_spinner=False)
def load_odds(api_key: str) -> Dict[str, Any]:
    """
    Fetch current NFL odds from The Odds API.
    Returns dict: {game_key: {home_prob, away_prob, home_odds, away_odds, bookmaker}}
    fetched_at is also returned.
    """
    fetched_at = datetime.now(timezone.utc)

    if not api_key or api_key.strip() == "":
        return {"odds": {}, "fetched_at": fetched_at, "error": "No API key provided"}

    params = {**ODDS_API_PARAMS, "apiKey": api_key.strip()}

    try:
        resp = requests.get(ODDS_API_URL, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        logger.warning("Odds API request failed: %s", exc)
        return {"odds": {}, "fetched_at": fetched_at, "error": str(exc)}

    odds_dict: Dict[str, Dict] = {}

    for game in raw:
        home_team_raw = game.get("home_team", "")
        away_team_raw = game.get("away_team", "")

        # Use the best available bookmaker (first one returned)
        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        # Try to find a reputable bookmaker
        preferred = ["fanduel", "draftkings", "betmgm", "caesars", "pointsbet"]
        bm = None
        for pref in preferred:
            found = next((b for b in bookmakers if b.get("key", "") == pref), None)
            if found:
                bm = found
                break
        if not bm:
            bm = bookmakers[0]

        h2h = next((m for m in bm.get("markets", []) if m["key"] == "h2h"), None)
        if not h2h:
            continue

        outcomes = {o["name"]: o["price"] for o in h2h.get("outcomes", [])}
        home_american = outcomes.get(home_team_raw)
        away_american = outcomes.get(away_team_raw)

        if home_american is None or away_american is None:
            continue

        home_raw, away_raw = american_to_implied(home_american, away_american)
        home_prob, away_prob = remove_vig(home_raw, away_raw)

        # Build a key that can be matched to ESPN/538 teams
        game_key = f"{_normalize_team(home_team_raw)}_vs_{_normalize_team(away_team_raw)}"

        odds_dict[game_key] = {
            "home_team_raw":  home_team_raw,
            "away_team_raw":  away_team_raw,
            "home_odds":      home_american,
            "away_odds":      away_american,
            "home_prob":      home_prob,
            "away_prob":      away_prob,
            "bookmaker":      bm.get("title", ""),
            "commence_time":  game.get("commence_time", ""),
        }

    return {"odds": odds_dict, "fetched_at": fetched_at, "error": None}


def american_to_implied(home_american: float, away_american: float) -> Tuple[float, float]:
    """Convert American moneyline to raw implied probabilities (with vig)."""
    def convert(odds: float) -> float:
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)

    return convert(home_american), convert(away_american)


def remove_vig(home_raw: float, away_raw: float) -> Tuple[float, float]:
    """Normalize implied probabilities so they sum to 1.0."""
    total = home_raw + away_raw
    if total == 0:
        return 0.5, 0.5
    return home_raw / total, away_raw / total


def calculate_edge(model_prob: float, market_prob: float) -> float:
    """Model edge over the market. Positive = model sees value."""
    return model_prob - market_prob


def kelly_criterion(model_prob: float, american_odds: float) -> float:
    """
    Kelly criterion bet sizing (fraction of bankroll).
    f = (b*p - q) / b
    where b = decimal odds payout (profit per unit), p = model win prob, q = 1-p
    """
    if american_odds is None:
        return 0.0

    if american_odds > 0:
        b = american_odds / 100.0
    else:
        b = 100.0 / abs(american_odds)

    p = model_prob
    q = 1 - p

    if b <= 0:
        return 0.0

    f = (b * p - q) / b
    return max(0.0, f)


def _normalize_team(name: str) -> str:
    """Simple normalization for fuzzy team name matching."""
    return name.strip().lower().replace(" ", "_")


def find_odds_for_game(
    odds_data: Dict[str, Dict],
    home_abbr: str,
    away_abbr: str,
) -> Optional[Dict]:
    """
    Look up odds for a specific game by team abbreviations.
    Tries to match using team name fragments.
    """
    from config import NFL_TEAMS

    home_info = NFL_TEAMS.get(home_abbr, {})
    away_info = NFL_TEAMS.get(away_abbr, {})
    home_name = home_info.get("name", home_abbr).lower()
    away_name = away_info.get("name", away_abbr).lower()

    for key, game_odds in odds_data.items():
        raw_home = game_odds["home_team_raw"].lower()
        raw_away = game_odds["away_team_raw"].lower()

        # Check if team name fragments match
        home_match = any(w in raw_home for w in home_name.split()) or any(w in home_name for w in raw_home.split())
        away_match = any(w in raw_away for w in away_name.split()) or any(w in away_name for w in raw_away.split())

        if home_match and away_match:
            return game_odds

    return None
