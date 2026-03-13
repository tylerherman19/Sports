// ELO rating system — ported from models/elo.py
// Replays all historical games chronologically to produce current team ratings.

function eloWinProb(eloA, eloB) {
  return 1.0 / (1.0 + Math.pow(10, (eloB - eloA) / 400.0));
}

function movMultiplier(pointDiff, eloDiff, movWeight) {
  const absDiff = Math.abs(pointDiff);
  const autocorr = 2.2 / (Math.abs(eloDiff) * 0.001 + 2.2);
  return Math.log(absDiff + 1) * autocorr * movWeight;
}

function seasonStartElo(priorElo) {
  return priorElo * 0.75 + ELO_BASELINE * 0.25;
}

// ── Rest/travel adjustments ────────────────────────────────────────────────
const REST_PER_DAY    =  1.5;
const TRAVEL_PER_K   = -3.0;
const SHORT_WEEK_PEN = -10.0;
const BYE_BONUS      =  25.0;

function restTravelAdj(homeAbbr, awayAbbr, homeRest, awayRest, isNeutral, scale) {
  let adj = 0;
  // Rest differential
  const restDiff = (homeRest - awayRest) * REST_PER_DAY;
  adj += restDiff * scale;
  // Short week penalty (rest < 6)
  if (homeRest < 6) adj += SHORT_WEEK_PEN * scale;
  if (awayRest < 6) adj -= SHORT_WEEK_PEN * scale;
  // Bye week bonus (rest > 10)
  if (homeRest > 10) adj += BYE_BONUS * scale;
  if (awayRest > 10) adj -= BYE_BONUS * scale;
  // Travel distance (away team travels to home stadium)
  if (!isNeutral) {
    const dist = getTravelDistance(homeAbbr, awayAbbr, false);
    adj -= (dist / 1000) * TRAVEL_PER_K * scale;
  }
  return adj;
}

// ── Main ELO calculation ───────────────────────────────────────────────────
function calculateEloRatings(games, params) {
  const {
    k_factor         = 20,
    mov_weight       = 1.0,
    home_field       = 65,
    recent_form_pct  = 30,
    h2h_weight       = 20,
    rest_travel_scale = 1.0,
  } = params;

  const teamElo     = {};  // current full-season ELO
  const teamSeason  = {};  // which season each team was last updated
  const teamGames   = {};  // total games played
  const teamWins    = {};
  const teamLosses  = {};
  const eloHistory  = {};  // [{date, elo}]
  const h2hRecords  = {};  // "T1|T2" → {wins, total}
  const recentGames = {};  // last 5 results per team for recent-form ELO
  const teamStats   = {};  // rolling scoring stats

  function getElo(t) {
    if (!teamElo[t]) teamElo[t] = ELO_BASELINE;
    return teamElo[t];
  }

  function getStats(t) {
    if (!teamStats[t]) teamStats[t] = { recentPf: [], recentPa: [], pf: 0, pa: 0, games: 0 };
    return teamStats[t];
  }

  // Replay all completed historical games
  for (const g of games) {
    if (g.score1 == null || g.score2 == null) continue;

    const home = g.home, away = g.away;
    if (!NFL_TEAMS[home] || !NFL_TEAMS[away]) continue;

    // Season start regression
    if (teamSeason[home] !== g.season) {
      if (teamSeason[home]) teamElo[home] = seasonStartElo(getElo(home));
      teamSeason[home] = g.season;
      teamWins[home]   = teamWins[home]   || 0;
      teamLosses[home] = teamLosses[home] || 0;
    }
    if (teamSeason[away] !== g.season) {
      if (teamSeason[away]) teamElo[away] = seasonStartElo(getElo(away));
      teamSeason[away] = g.season;
      teamWins[away]   = teamWins[away]   || 0;
      teamLosses[away] = teamLosses[away] || 0;
    }

    const eloHome = getElo(home);
    const eloAway = getElo(away);
    const hfa     = g.neutral ? 0 : home_field;

    // Pre-game rest/travel
    const rtAdj = restTravelAdj(home, away, g.rest1, g.rest2, g.neutral === 1, rest_travel_scale);

    // H2H adjustment
    const h2hKey  = [home, away].sort().join("|");
    const h2h     = h2hRecords[h2hKey] || { wins: 0, total: 0 };
    const h2hWr   = h2h.total > 0 ? h2h.wins / h2h.total : 0.5;  // from home team perspective
    const h2hAdj  = (h2hWr - 0.5) * 100 * (h2h_weight / 100);   // ±50 pts max at weight=100

    const adjHomeElo = eloHome + hfa + rtAdj + h2hAdj;
    const expHome    = eloWinProb(adjHomeElo, eloAway);

    const homeScore = g.score1, awayScore = g.score2;
    const pointDiff = homeScore - awayScore;
    const homeWon   = pointDiff > 0;
    const actual    = homeWon ? 1 : (pointDiff === 0 ? 0.5 : 0);

    const mov = movMultiplier(pointDiff, adjHomeElo - eloAway, mov_weight);
    const k   = k_factor * mov;

    const newHomeElo = eloHome + k * (actual - expHome);
    const newAwayElo = eloAway + k * ((1 - actual) - (1 - expHome));

    teamElo[home] = newHomeElo;
    teamElo[away] = newAwayElo;

    // Track history for sparklines (current season only)
    if (g.season === CURRENT_SEASON) {
      if (!eloHistory[home]) eloHistory[home] = [];
      if (!eloHistory[away]) eloHistory[away] = [];
      eloHistory[home].push({ date: g.date, elo: newHomeElo });
      eloHistory[away].push({ date: g.date, elo: newAwayElo });
    }

    // Update win/loss
    if (!teamWins[home])   teamWins[home]   = 0;
    if (!teamLosses[home]) teamLosses[home] = 0;
    if (!teamWins[away])   teamWins[away]   = 0;
    if (!teamLosses[away]) teamLosses[away] = 0;
    if (!teamGames[home])  teamGames[home]  = 0;
    if (!teamGames[away])  teamGames[away]  = 0;

    if (g.season === CURRENT_SEASON) {
      if (homeWon) { teamWins[home]++; teamLosses[away]++; }
      else if (pointDiff < 0) { teamWins[away]++; teamLosses[home]++; }
    }
    teamGames[home]++;
    teamGames[away]++;

    // H2H update
    if (!h2hRecords[h2hKey]) h2hRecords[h2hKey] = { wins: 0, total: 0 };
    h2hRecords[h2hKey].total++;
    if (homeWon) h2hRecords[h2hKey].wins++;

    // Rolling scoring stats
    const sth = getStats(home), sta = getStats(away);
    sth.recentPf.push(homeScore); sth.recentPa.push(awayScore);
    sta.recentPf.push(awayScore); sta.recentPa.push(homeScore);
    sth.pf += homeScore; sth.pa += awayScore; sth.games++;
    sta.pf += awayScore; sta.pa += homeScore; sta.games++;

    // Recent form (last 5)
    if (!recentGames[home]) recentGames[home] = [];
    if (!recentGames[away]) recentGames[away] = [];
    recentGames[home].push(homeWon ? 1 : 0);
    recentGames[away].push(homeWon ? 0 : 1);
  }

  // ── Compute recent-form ELO blend ────────────────────────────────────────
  // Separate mini-ELO computed from only last 5 games, blended with full ELO
  const recentPct = recent_form_pct / 100;

  const result = {};
  for (const abbr of Object.keys(NFL_TEAMS)) {
    const elo     = teamElo[abbr]    || ELO_BASELINE;
    const wins    = teamWins[abbr]   || 0;
    const losses  = teamLosses[abbr] || 0;
    const games   = teamGames[abbr]  || 0;
    const last5   = (recentGames[abbr] || []).slice(-5);
    const last5Wr = last5.length ? last5.reduce((a,b) => a+b, 0) / last5.length : 0.5;

    // Recent-form ELO: offset full ELO based on last-5 win rate vs 0.5
    const recentEloAdj = (last5Wr - 0.5) * 100;
    const blendedElo   = elo * (1 - recentPct) + (elo + recentEloAdj) * recentPct;

    const st  = teamStats[abbr] || { recentPf: [], recentPa: [], pf: 0, pa: 0, games: 0 };
    const pf8 = st.recentPf.slice(-8);
    const pa8 = st.recentPa.slice(-8);
    const avgPf = pf8.length ? pf8.reduce((a,b) => a+b, 0) / pf8.length : 24;
    const avgPa = pa8.length ? pa8.reduce((a,b) => a+b, 0) / pa8.length : 24;

    result[abbr] = {
      elo:       blendedElo,
      eloRaw:    elo,
      wins,
      losses,
      games,
      last5,
      last5Wr,
      eloHistory: eloHistory[abbr] || [],
      avgPf,
      avgPa,
      netEff:    (avgPf - avgPa) / 10,
      totalPf:   st.pf,
      totalPa:   st.pa,
      totalGames: st.games,
    };
  }

  return result;
}
