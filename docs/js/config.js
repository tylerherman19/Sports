// NFL Prediction Dashboard — Configuration
// Ported from config.py

const NFL_TEAMS = {
  ARI: { name: "Arizona Cardinals",    city: "Glendale",        color: "#97233F", lat: 33.5277,  lon: -112.2626, espnId: "22"  },
  ATL: { name: "Atlanta Falcons",       city: "Atlanta",         color: "#A71930", lat: 33.7553,  lon: -84.4006,  espnId: "1"   },
  BAL: { name: "Baltimore Ravens",      city: "Baltimore",       color: "#241773", lat: 39.2780,  lon: -76.6227,  espnId: "33"  },
  BUF: { name: "Buffalo Bills",         city: "Orchard Park",    color: "#00338D", lat: 42.7738,  lon: -78.7870,  espnId: "2"   },
  CAR: { name: "Carolina Panthers",     city: "Charlotte",       color: "#0085CA", lat: 35.2258,  lon: -80.8528,  espnId: "29"  },
  CHI: { name: "Chicago Bears",         city: "Chicago",         color: "#0B162A", lat: 41.8623,  lon: -87.6167,  espnId: "3"   },
  CIN: { name: "Cincinnati Bengals",    city: "Cincinnati",      color: "#FB4F14", lat: 39.0955,  lon: -84.5160,  espnId: "4"   },
  CLE: { name: "Cleveland Browns",      city: "Cleveland",       color: "#311D00", lat: 41.5061,  lon: -81.6995,  espnId: "5"   },
  DAL: { name: "Dallas Cowboys",        city: "Arlington",       color: "#003594", lat: 32.7473,  lon: -97.0945,  espnId: "6"   },
  DEN: { name: "Denver Broncos",        city: "Denver",          color: "#FB4F14", lat: 39.7439,  lon: -105.0201, espnId: "7"   },
  DET: { name: "Detroit Lions",         city: "Detroit",         color: "#0076B6", lat: 42.3400,  lon: -83.0456,  espnId: "8"   },
  GB:  { name: "Green Bay Packers",     city: "Green Bay",       color: "#203731", lat: 44.5013,  lon: -88.0622,  espnId: "9"   },
  HOU: { name: "Houston Texans",        city: "Houston",         color: "#03202F", lat: 29.6847,  lon: -95.4107,  espnId: "34"  },
  IND: { name: "Indianapolis Colts",    city: "Indianapolis",    color: "#002C5F", lat: 39.7601,  lon: -86.1639,  espnId: "11"  },
  JAX: { name: "Jacksonville Jaguars",  city: "Jacksonville",    color: "#006778", lat: 30.3239,  lon: -81.6373,  espnId: "30"  },
  KC:  { name: "Kansas City Chiefs",    city: "Kansas City",     color: "#E31837", lat: 39.0489,  lon: -94.4839,  espnId: "12"  },
  LAC: { name: "Los Angeles Chargers",  city: "Inglewood",       color: "#0080C6", lat: 33.9535,  lon: -118.3392, espnId: "24"  },
  LAR: { name: "Los Angeles Rams",      city: "Inglewood",       color: "#003594", lat: 33.9535,  lon: -118.3392, espnId: "14"  },
  LV:  { name: "Las Vegas Raiders",     city: "Las Vegas",       color: "#A5ACAF", lat: 36.0909,  lon: -115.1833, espnId: "13"  },
  MIA: { name: "Miami Dolphins",        city: "Miami Gardens",   color: "#008E97", lat: 25.9580,  lon: -80.2389,  espnId: "15"  },
  MIN: { name: "Minnesota Vikings",     city: "Minneapolis",     color: "#4F2683", lat: 44.9740,  lon: -93.2575,  espnId: "16"  },
  NE:  { name: "New England Patriots",  city: "Foxborough",      color: "#002244", lat: 42.0909,  lon: -71.2643,  espnId: "17"  },
  NO:  { name: "New Orleans Saints",    city: "New Orleans",     color: "#D3BC8D", lat: 29.9511,  lon: -90.0812,  espnId: "18"  },
  NYG: { name: "New York Giants",       city: "East Rutherford", color: "#0B2265", lat: 40.8128,  lon: -74.0742,  espnId: "19"  },
  NYJ: { name: "New York Jets",         city: "East Rutherford", color: "#125740", lat: 40.8128,  lon: -74.0742,  espnId: "20"  },
  PHI: { name: "Philadelphia Eagles",   city: "Philadelphia",    color: "#004C54", lat: 39.9008,  lon: -75.1675,  espnId: "21"  },
  PIT: { name: "Pittsburgh Steelers",   city: "Pittsburgh",      color: "#FFB612", lat: 40.4468,  lon: -80.0158,  espnId: "23"  },
  SEA: { name: "Seattle Seahawks",      city: "Seattle",         color: "#002244", lat: 47.5952,  lon: -122.3316, espnId: "26"  },
  SF:  { name: "San Francisco 49ers",   city: "Santa Clara",     color: "#AA0000", lat: 37.4032,  lon: -121.9697, espnId: "25"  },
  TB:  { name: "Tampa Bay Buccaneers",  city: "Tampa",           color: "#D50A0A", lat: 27.9758,  lon: -82.5033,  espnId: "27"  },
  TEN: { name: "Tennessee Titans",      city: "Nashville",       color: "#0C2340", lat: 36.1665,  lon: -86.7713,  espnId: "10"  },
  WAS: { name: "Washington Commanders", city: "Landover",        color: "#5A1414", lat: 38.9076,  lon: -76.8645,  espnId: "28"  },
};

// Map nflverse abbreviations → our standard abbreviations
const TEAM_MAP = {
  ARI:"ARI", ATL:"ATL", BAL:"BAL", BUF:"BUF", CAR:"CAR", CHI:"CHI",
  CIN:"CIN", CLE:"CLE", DAL:"DAL", DEN:"DEN", DET:"DET", GB:"GB",
  HOU:"HOU", IND:"IND", JAX:"JAX", KC:"KC",  LAC:"LAC", LV:"LV",
  MIA:"MIA", MIN:"MIN", NE:"NE",   NO:"NO",   NYG:"NYG", NYJ:"NYJ",
  PHI:"PHI", PIT:"PIT", SEA:"SEA", SF:"SF",   TB:"TB",   TEN:"TEN",
  WAS:"WAS",
  // ESPN alias
  WSH:"WAS",
  // Franchise relocations / old names
  LA:"LAR", STL:"LAR", OAK:"LV", SD:"LAC", JAC:"JAX",
};

const PARAMS = {
  k_factor:          20,
  mov_weight:        1.0,
  home_field:        65,
  recent_form_pct:   30,
  h2h_weight:        20,
  rest_travel_scale: 1.0,
  w_elo:             35,
  w_pyth:            25,
  w_bayes:           20,
  w_eff:             20,
};

const PYTHAGOREAN_EXP  = 2.37;
const ELO_BASELINE     = 1500;
const CURRENT_SEASON   = 2025;

const NFLVERSE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv";
const ESPN_SCOREBOARD  = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard";
const ESPN_STANDINGS   = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/standings";
const LOGO_URL = (abbr) => `https://a.espncdn.com/i/teamlogos/nfl/500/${abbr.toLowerCase()}.png`;

const AFC_TEAMS = new Set(["BAL","BUF","CIN","CLE","DEN","HOU","IND","JAX","KC","LAC","LV","MIA","NE","NYJ","PIT","TEN"]);
const NFC_TEAMS = new Set(["ARI","ATL","CAR","CHI","DAL","DET","GB","LAR","MIN","NO","NYG","NYJ","PHI","SEA","SF","TB","WAS"]);
