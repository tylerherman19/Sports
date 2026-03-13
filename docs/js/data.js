// Data fetching: nflverse CSV and ESPN live APIs

// ── Cache ──────────────────────────────────────────────────────────────────
const _cache = {};
const _cacheExpiry = {};

function cacheGet(key) {
  if (_cache[key] && _cacheExpiry[key] > Date.now()) return _cache[key];
  return null;
}
function cacheSet(key, val, ttlMs) {
  _cache[key] = val;
  _cacheExpiry[key] = Date.now() + ttlMs;
}

// ── Haversine distance (miles) ─────────────────────────────────────────────
function haversineMiles(lat1, lon1, lat2, lon2) {
  const R = 3958.8;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2 +
            Math.cos(lat1 * Math.PI/180) * Math.cos(lat2 * Math.PI/180) * Math.sin(dLon/2)**2;
  return R * 2 * Math.asin(Math.sqrt(a));
}

function getTravelDistance(homeAbbr, awayAbbr, isNeutral) {
  if (isNeutral) return 0;
  const h = NFL_TEAMS[homeAbbr], a = NFL_TEAMS[awayAbbr];
  if (!h || !a) return 0;
  return haversineMiles(a.lat, a.lon, h.lat, h.lon);
}

// ── nflverse historical CSV ────────────────────────────────────────────────
async function loadHistoricalData() {
  const cached = cacheGet("nflverse");
  if (cached) return cached;

  const resp = await fetch(NFLVERSE_URL);
  if (!resp.ok) throw new Error(`Failed to load historical data: ${resp.status}`);
  const text = await resp.text();

  const parsed = Papa.parse(text, { header: true, skipEmptyLines: true, dynamicTyping: true });
  const rows = parsed.data;

  // Normalise columns to internal schema
  const games = rows.map(r => ({
    date:    r.gameday || r.date || "",
    season:  +r.season,
    week:    r.week,
    gameType: r.game_type || "REG",
    home:    TEAM_MAP[r.home_team] || r.home_team,
    away:    TEAM_MAP[r.away_team] || r.away_team,
    score1:  r.home_score != null ? +r.home_score : null,   // home
    score2:  r.away_score != null ? +r.away_score : null,   // away
    neutral: (r.location || "").toLowerCase() === "neutral" ? 1 : 0,
    rest1:   r.home_rest != null ? +r.home_rest : 7,
    rest2:   r.away_rest != null ? +r.away_rest : 7,
  }))
  .filter(g => g.date && g.home && g.away && g.season >= 1999)
  .sort((a, b) => a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

  cacheSet("nflverse", games, 3600_000); // 1-hour cache
  return games;
}

// ── ESPN Scoreboard ────────────────────────────────────────────────────────
async function loadScoreboard() {
  const cached = cacheGet("scoreboard");
  if (cached) return cached;

  try {
    const resp = await fetch(ESPN_SCOREBOARD);
    if (!resp.ok) throw new Error("ESPN scoreboard unavailable");
    const data = await resp.json();

    const games = (data.events || []).map(ev => {
      const comp   = ev.competitions?.[0] || {};
      const comps  = comp.competitors || [];
      const home   = comps.find(c => c.homeAway === "home") || {};
      const away   = comps.find(c => c.homeAway === "away") || {};
      const status = comp.status?.type || {};

      const homeAbbr = TEAM_MAP[home.team?.abbreviation] || home.team?.abbreviation || "?";
      const awayAbbr = TEAM_MAP[away.team?.abbreviation] || away.team?.abbreviation || "?";

      // Spread/total from odds
      const odds = comp.odds?.[0] || {};

      return {
        id:        ev.id,
        name:      ev.name || "",
        date:      comp.date || ev.date || "",
        week:      data.week?.number || 0,
        home:      homeAbbr,
        away:      awayAbbr,
        homeScore: home.score != null ? +home.score : null,
        awayScore: away.score != null ? +away.score : null,
        status:    status.name || "scheduled",    // STATUS_FINAL, STATUS_IN_PROGRESS, STATUS_SCHEDULED
        clock:     comp.status?.displayClock || "",
        period:    comp.status?.period || 0,
        neutral:   comp.neutralSite ? 1 : 0,
        spread:    odds.spread != null ? +odds.spread : null,
        overUnder: odds.overUnder != null ? +odds.overUnder : null,
        venue:     comp.venue?.fullName || "",
        city:      comp.venue?.address?.city || "",
      };
    });

    cacheSet("scoreboard", games, 30_000); // 30s cache
    return games;
  } catch (e) {
    console.warn("ESPN scoreboard error:", e.message);
    return [];
  }
}

// ── ESPN Standings ─────────────────────────────────────────────────────────
async function loadStandings() {
  const cached = cacheGet("standings");
  if (cached) return cached;

  try {
    const resp = await fetch(ESPN_STANDINGS);
    if (!resp.ok) throw new Error("ESPN standings unavailable");
    const data = await resp.json();

    const standings = {};
    (data.children || []).forEach(conf => {
      (conf.children || []).forEach(div => {
        (div.standings?.entries || []).forEach(entry => {
          const abbr = TEAM_MAP[entry.team?.abbreviation] || entry.team?.abbreviation;
          if (!abbr) return;
          const stats = {};
          (entry.stats || []).forEach(s => { stats[s.name] = s.value; });
          standings[abbr] = {
            wins:   stats.wins   || 0,
            losses: stats.losses || 0,
            ties:   stats.ties   || 0,
            pf:     stats.pointsFor     || 0,
            pa:     stats.pointsAgainst || 0,
            conf:   conf.name || "",
            div:    div.name  || "",
          };
        });
      });
    });

    cacheSet("standings", standings, 300_000); // 5-min cache
    return standings;
  } catch (e) {
    console.warn("ESPN standings error:", e.message);
    return {};
  }
}

// Expose travel distance to other modules
window.getTravelDistance = getTravelDistance;
