"""
NFL Prediction Dashboard — Configuration
Team colors, stadium coordinates, ESPN IDs, and constants.
"""

# ── NFL Team Data ─────────────────────────────────────────────────────────────
# Each entry: abbreviation → {name, city, primary_color, lat, lon, espn_id, pfr_abbr}
NFL_TEAMS = {
    "ARI": {"name": "Arizona Cardinals",     "city": "Glendale",       "color": "#97233F", "lat": 33.5277,  "lon": -112.2626, "espn_id": "22",  "pfr": "crd"},
    "ATL": {"name": "Atlanta Falcons",        "city": "Atlanta",        "color": "#A71930", "lat": 33.7553,  "lon": -84.4006,  "espn_id": "1",   "pfr": "atl"},
    "BAL": {"name": "Baltimore Ravens",       "city": "Baltimore",      "color": "#241773", "lat": 39.2780,  "lon": -76.6227,  "espn_id": "33",  "pfr": "rav"},
    "BUF": {"name": "Buffalo Bills",          "city": "Orchard Park",   "color": "#00338D", "lat": 42.7738,  "lon": -78.7870,  "espn_id": "2",   "pfr": "buf"},
    "CAR": {"name": "Carolina Panthers",      "city": "Charlotte",      "color": "#0085CA", "lat": 35.2258,  "lon": -80.8528,  "espn_id": "29",  "pfr": "car"},
    "CHI": {"name": "Chicago Bears",          "city": "Chicago",        "color": "#0B162A", "lat": 41.8623,  "lon": -87.6167,  "espn_id": "3",   "pfr": "chi"},
    "CIN": {"name": "Cincinnati Bengals",     "city": "Cincinnati",     "color": "#FB4F14", "lat": 39.0955,  "lon": -84.5160,  "espn_id": "4",   "pfr": "cin"},
    "CLE": {"name": "Cleveland Browns",       "city": "Cleveland",      "color": "#311D00", "lat": 41.5061,  "lon": -81.6995,  "espn_id": "5",   "pfr": "cle"},
    "DAL": {"name": "Dallas Cowboys",         "city": "Arlington",      "color": "#003594", "lat": 32.7473,  "lon": -97.0945,  "espn_id": "6",   "pfr": "dal"},
    "DEN": {"name": "Denver Broncos",         "city": "Denver",         "color": "#FB4F14", "lat": 39.7439,  "lon": -105.0201, "espn_id": "7",   "pfr": "den"},
    "DET": {"name": "Detroit Lions",          "city": "Detroit",        "color": "#0076B6", "lat": 42.3400,  "lon": -83.0456,  "espn_id": "8",   "pfr": "det"},
    "GB":  {"name": "Green Bay Packers",      "city": "Green Bay",      "color": "#203731", "lat": 44.5013,  "lon": -88.0622,  "espn_id": "9",   "pfr": "gnb"},
    "HOU": {"name": "Houston Texans",         "city": "Houston",        "color": "#03202F", "lat": 29.6847,  "lon": -95.4107,  "espn_id": "34",  "pfr": "htx"},
    "IND": {"name": "Indianapolis Colts",     "city": "Indianapolis",   "color": "#002C5F", "lat": 39.7601,  "lon": -86.1639,  "espn_id": "11",  "pfr": "clt"},
    "JAX": {"name": "Jacksonville Jaguars",   "city": "Jacksonville",   "color": "#006778", "lat": 30.3239,  "lon": -81.6373,  "espn_id": "30",  "pfr": "jax"},
    "KC":  {"name": "Kansas City Chiefs",     "city": "Kansas City",    "color": "#E31837", "lat": 39.0489,  "lon": -94.4839,  "espn_id": "12",  "pfr": "kan"},
    "LAC": {"name": "Los Angeles Chargers",   "city": "Inglewood",      "color": "#0080C6", "lat": 33.9535,  "lon": -118.3392, "espn_id": "24",  "pfr": "sdg"},
    "LAR": {"name": "Los Angeles Rams",       "city": "Inglewood",      "color": "#003594", "lat": 33.9535,  "lon": -118.3392, "espn_id": "14",  "pfr": "ram"},
    "LV":  {"name": "Las Vegas Raiders",      "city": "Las Vegas",      "color": "#000000", "lat": 36.0909,  "lon": -115.1833, "espn_id": "13",  "pfr": "rai"},
    "MIA": {"name": "Miami Dolphins",         "city": "Miami Gardens",  "color": "#008E97", "lat": 25.9580,  "lon": -80.2389,  "espn_id": "15",  "pfr": "mia"},
    "MIN": {"name": "Minnesota Vikings",      "city": "Minneapolis",    "color": "#4F2683", "lat": 44.9740,  "lon": -93.2575,  "espn_id": "16",  "pfr": "min"},
    "NE":  {"name": "New England Patriots",   "city": "Foxborough",     "color": "#002244", "lat": 42.0909,  "lon": -71.2643,  "espn_id": "17",  "pfr": "nwe"},
    "NO":  {"name": "New Orleans Saints",     "city": "New Orleans",    "color": "#D3BC8D", "lat": 29.9511,  "lon": -90.0812,  "espn_id": "18",  "pfr": "nor"},
    "NYG": {"name": "New York Giants",        "city": "East Rutherford","color": "#0B2265", "lat": 40.8128,  "lon": -74.0742,  "espn_id": "19",  "pfr": "nyg"},
    "NYJ": {"name": "New York Jets",          "city": "East Rutherford","color": "#125740", "lat": 40.8128,  "lon": -74.0742,  "espn_id": "20",  "pfr": "nyj"},
    "PHI": {"name": "Philadelphia Eagles",    "city": "Philadelphia",   "color": "#004C54", "lat": 39.9008,  "lon": -75.1675,  "espn_id": "21",  "pfr": "phi"},
    "PIT": {"name": "Pittsburgh Steelers",    "city": "Pittsburgh",     "color": "#FFB612", "lat": 40.4468,  "lon": -80.0158,  "espn_id": "23",  "pfr": "pit"},
    "SEA": {"name": "Seattle Seahawks",       "city": "Seattle",        "color": "#002244", "lat": 47.5952,  "lon": -122.3316, "espn_id": "26",  "pfr": "sea"},
    "SF":  {"name": "San Francisco 49ers",    "city": "Santa Clara",    "color": "#AA0000", "lat": 37.4032,  "lon": -121.9697, "espn_id": "25",  "pfr": "sfo"},
    "TB":  {"name": "Tampa Bay Buccaneers",   "city": "Tampa",          "color": "#D50A0A", "lat": 27.9758,  "lon": -82.5033,  "espn_id": "27",  "pfr": "tam"},
    "TEN": {"name": "Tennessee Titans",       "city": "Nashville",      "color": "#0C2340", "lat": 36.1665,  "lon": -86.7713,  "espn_id": "10",  "pfr": "oti"},
    "WAS": {"name": "Washington Commanders",  "city": "Landover",       "color": "#5A1414", "lat": 38.9076,  "lon": -76.8645,  "espn_id": "28",  "pfr": "was"},
}

# Map ESPN team abbreviations → our abbreviations (ESPN sometimes differs)
ESPN_ABBR_MAP = {
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB":  "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC":  "KC",
    "LAC": "LAC", "LAR": "LAR", "LV":  "LV",  "MIA": "MIA",
    "MIN": "MIN", "NE":  "NE",  "NO":  "NO",  "NYG": "NYG",
    "NYJ": "NYJ", "PHI": "PHI", "PIT": "PIT", "SEA": "SEA",
    "SF":  "SF",  "TB":  "TB",  "TEN": "TEN", "WSH": "WAS",
    "WAS": "WAS",
}

# Map nflverse abbreviations → our standard abbreviations
# nflverse uses: LA (Rams), OAK (Raiders), SD (old Chargers), STL (old Rams)
TEAM_538_MAP = {
    # Direct matches
    "ARI": "ARI", "ATL": "ATL", "BAL": "BAL", "BUF": "BUF",
    "CAR": "CAR", "CHI": "CHI", "CIN": "CIN", "CLE": "CLE",
    "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GB":  "GB",
    "HOU": "HOU", "IND": "IND", "JAX": "JAX", "KC":  "KC",
    "LAC": "LAC", "LV":  "LV",  "MIA": "MIA", "MIN": "MIN",
    "NE":  "NE",  "NO":  "NO",  "NYG": "NYG", "NYJ": "NYJ",
    "PHI": "PHI", "PIT": "PIT", "SEA": "SEA", "SF":  "SF",
    "TB":  "TB",  "TEN": "TEN", "WAS": "WAS",
    # Franchise relocations / old names
    "LA":  "LAR",   # Los Angeles Rams (current)
    "STL": "LAR",   # St. Louis Rams (pre-2016)
    "OAK": "LV",    # Oakland Raiders (pre-2020)
    "SD":  "LAC",   # San Diego Chargers (pre-2017)
    "JAC": "JAX",   # Jacksonville Jaguars alternate code
    "WSH": "WAS",   # Washington alternate
}

# ── Model Defaults ────────────────────────────────────────────────────────────
DEFAULT_PARAMS = {
    "k_factor":          20,
    "mov_weight":        1.0,
    "home_field":        65,
    "recent_form_pct":   30,
    "sos_weight":        1.0,
    "h2h_weight":        20,
    "turnover_impact":   1.0,
    "rest_travel_scale": 1.0,
    "time_decay_lambda": 0.05,
    "w_logistic":        30,
    "w_xgb":             25,
    "w_elo":             20,
    "w_pyth":            15,
    "w_eff":             10,
    "refresh_interval":  30,
    "injury_discounts":  {},
}

# ── Math Constants ────────────────────────────────────────────────────────────
PYTHAGOREAN_EXP  = 2.37
ELO_BASELINE     = 1500
ELO_SEASON_REGRESS_FACTOR = 0.75
BAYESIAN_PRIOR_SIGMA = 75.0
BAYESIAN_OBS_SIGMA   = 200.0
MONTE_CARLO_SIMS     = 10_000

# ── ESPN API Endpoints ────────────────────────────────────────────────────────
ESPN_SCOREBOARD_URL  = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
ESPN_STANDINGS_URL   = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/standings"
ESPN_SCHEDULE_URL    = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/schedule"
ESPN_INJURIES_URL    = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
ESPN_LOGO_URL        = "https://a.espncdn.com/i/teamlogos/nfl/500/{abbrev}.png"

# ── Historical NFL data (nflverse — replaces defunct FiveThirtyEight CSV) ─────
# Has: game_id, season, game_type, week, gameday, away_team, away_score, home_team,
#      home_score, result, location, away_rest, home_rest, away_moneyline,
#      home_moneyline, spread_line, temp, wind, stadium, etc.
FTE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# ── The Odds API ──────────────────────────────────────────────────────────────
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
ODDS_API_PARAMS = {
    "regions":  "us",
    "markets":  "h2h",
    "oddsFormat": "american",
}

# Current NFL season
CURRENT_SEASON = 2025

# Playoff seeds per conference
PLAYOFF_SEEDS = 7
