// Prediction systems: Pythagorean, Bayesian, Monte Carlo, Ensemble
// Ported from models/pythagorean.py, bayesian.py, monte_carlo.py, ensemble.py

// ── Math helpers ──────────────────────────────────────────────────────────
function logistic(x) { return 1 / (1 + Math.exp(-x)); }
function randn() {
  // Box-Muller transform
  const u1 = Math.random(), u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

// ── Pythagorean ────────────────────────────────────────────────────────────
function pythagoreanExp(pf, pa) {
  if (pf + pa === 0) return 0.5;
  const pfE = Math.pow(pf, PYTHAGOREAN_EXP);
  const paE = Math.pow(pa, PYTHAGOREAN_EXP);
  return pfE / (pfE + paE);
}

function calculatePythagoreanRatings(games, standings) {
  // Build season-level PF/PA
  const seasonal = {};
  for (const g of games) {
    if (g.season !== CURRENT_SEASON || g.score1 == null) continue;
    if (!seasonal[g.home]) seasonal[g.home] = { pf: 0, pa: 0, wins: 0, losses: 0 };
    if (!seasonal[g.away]) seasonal[g.away] = { pf: 0, pa: 0, wins: 0, losses: 0 };
    seasonal[g.home].pf += g.score1; seasonal[g.home].pa += g.score2;
    seasonal[g.away].pf += g.score2; seasonal[g.away].pa += g.score1;
    if (g.score1 > g.score2) { seasonal[g.home].wins++; seasonal[g.away].losses++; }
    else if (g.score2 > g.score1) { seasonal[g.away].wins++; seasonal[g.home].losses++; }
  }

  const result = {};
  for (const abbr of Object.keys(NFL_TEAMS)) {
    const s = seasonal[abbr] || standings[abbr] || {};
    const pf = s.pf || 0, pa = s.pa || 0;
    const wins = s.wins || 0, losses = s.losses || 0;
    const totalGames = wins + losses;

    const pythExp  = pythagoreanExp(pf, pa);
    const pythElo  = ELO_BASELINE + (pythExp - 0.5) * 400;
    const actualWr = totalGames > 0 ? wins / totalGames : 0.5;

    let flag = null;
    if (totalGames >= 4) {
      const diff = actualWr - pythExp;
      if (diff > 0.10)  flag = "overperformer";
      if (diff < -0.10) flag = "underperformer";
    }

    result[abbr] = { pythExp, pythElo, actualWr, flag };
  }
  return result;
}

// ── Bayesian Normal conjugate ──────────────────────────────────────────────
const BAYES_PRIOR_SIGMA = 75.0;
const BAYES_OBS_SIGMA   = 200.0;

function calculateBayesianRatings(eloRatings) {
  const result = {};
  for (const [abbr, er] of Object.entries(eloRatings)) {
    const mu0    = er.eloRaw;
    const sigma0 = BAYES_PRIOR_SIGMA;
    const n      = er.games;

    // After n observations, posterior sigma shrinks
    const postVar = 1 / (1 / sigma0**2 + n / BAYES_OBS_SIGMA**2);
    const sigma   = Math.sqrt(postVar);

    result[abbr] = {
      mu:    er.elo,
      sigma: Math.max(sigma, 30),  // floor at 30 pts
      lower: er.elo - 1.65 * sigma,
      upper: er.elo + 1.65 * sigma,
    };
  }
  return result;
}

// ── Monte Carlo matchup simulation ────────────────────────────────────────
function simulateMatchup(homeElo, homeEloSigma, awayElo, awayEloSigma, baseProb, n = 5000) {
  const SPREAD_STD = 13.5;
  let wins = 0, margins = [];

  for (let i = 0; i < n; i++) {
    const hStrength = homeElo + randn() * homeEloSigma;
    const aStrength = awayElo + randn() * awayEloSigma;
    const probAdj = logistic((hStrength - aStrength) / 200);
    const finalProb = 0.5 * baseProb + 0.5 * probAdj;
    const win = Math.random() < finalProb;
    if (win) wins++;
    const margin = (finalProb - 0.5) * 14 + randn() * SPREAD_STD;
    margins.push(margin);
  }

  margins.sort((a, b) => a - b);
  const medianMargin = margins[Math.floor(n / 2)];
  const ci_lo = margins[Math.floor(n * 0.10)];
  const ci_hi = margins[Math.floor(n * 0.90)];
  const pWin7  = margins.filter(m => m > 7).length  / n;
  const pWin14 = margins.filter(m => m > 14).length / n;

  return {
    winProb: wins / n,
    medianMargin,
    ci_lo,
    ci_hi,
    pWin7,
    pWin14,
    marginDist: margins,
  };
}

// ── Efficiency ratings ─────────────────────────────────────────────────────
function calculateEfficiencyRatings(eloRatings) {
  // Compute league avg
  const pfVals = Object.values(eloRatings).map(r => r.avgPf).filter(v => v > 0);
  const leagueAvgPf = pfVals.reduce((a,b) => a+b, 0) / pfVals.length || 24;

  const result = {};
  for (const [abbr, er] of Object.entries(eloRatings)) {
    const avgOppElo = ELO_BASELINE; // simplified: league average opponents
    const sos = avgOppElo / ELO_BASELINE;

    const offEff = (er.avgPf / leagueAvgPf) * sos;
    const defEff = (leagueAvgPf / Math.max(er.avgPa, 1)) * sos;
    const netEff = (offEff - defEff);
    const effElo = ELO_BASELINE + netEff * 150;

    result[abbr] = { offEff, defEff, netEff, effElo };
  }
  return result;
}

// ── Ensemble prediction ────────────────────────────────────────────────────
function predictMatchup(homeAbbr, awayAbbr, eloRatings, pythagorean, bayesian, efficiency, params) {
  const {
    home_field       = 65,
    w_elo            = 35,
    w_pyth           = 25,
    w_bayes          = 20,
    w_eff            = 20,
    rest_travel_scale = 1.0,
  } = params;

  const hElo  = eloRatings[homeAbbr]  || { elo: ELO_BASELINE, eloRaw: ELO_BASELINE };
  const aElo  = eloRatings[awayAbbr]  || { elo: ELO_BASELINE, eloRaw: ELO_BASELINE };
  const hPyth = pythagorean[homeAbbr] || { pythElo: ELO_BASELINE };
  const aPyth = pythagorean[awayAbbr] || { pythElo: ELO_BASELINE };
  const hBay  = bayesian[homeAbbr]    || { mu: ELO_BASELINE, sigma: 75 };
  const aBay  = bayesian[awayAbbr]    || { mu: ELO_BASELINE, sigma: 75 };
  const hEff  = efficiency[homeAbbr]  || { effElo: ELO_BASELINE };
  const aEff  = efficiency[awayAbbr]  || { effElo: ELO_BASELINE };

  // 1. ELO win probability (with HFA)
  const eloProbRaw = eloWinProb(hElo.elo + home_field, aElo.elo);

  // 2. Pythagorean probability
  const pythProb = logistic((hPyth.pythElo - aPyth.pythElo) / 400);

  // 3. Bayesian probability
  const bayesProb = logistic((hBay.mu - aBay.mu) / 400);

  // 4. Efficiency probability
  const effProb = logistic((hEff.effElo - aEff.effElo) / 400);

  // Weighted ensemble (normalize weights)
  const totalW = w_elo + w_pyth + w_bayes + w_eff;
  const ensembleProb = (
    w_elo   * eloProbRaw +
    w_pyth  * pythProb   +
    w_bayes * bayesProb  +
    w_eff   * effProb
  ) / totalW;

  // Monte Carlo
  const mc = simulateMatchup(hBay.mu, hBay.sigma, aBay.mu, aBay.sigma, ensembleProb, 5000);

  // System breakdown
  const systems = {
    "ELO":         { prob: eloProbRaw, label: "ELO Rating" },
    "Pythagorean": { prob: pythProb,   label: "Pythagorean" },
    "Bayesian":    { prob: bayesProb,  label: "Bayesian" },
    "Efficiency":  { prob: effProb,    label: "Efficiency" },
  };

  // Pythagorean flags
  const hFlag = (pythagorean[homeAbbr] || {}).flag;
  const aFlag = (pythagorean[awayAbbr] || {}).flag;

  // 5-sentence explanation
  const pct = Math.round(ensembleProb * 100);
  const hInfo = NFL_TEAMS[homeAbbr] || { name: homeAbbr };
  const aInfo = NFL_TEAMS[awayAbbr] || { name: awayAbbr };
  const eloDiff = Math.round(hElo.elo - aElo.elo);
  const marginStr = mc.medianMargin > 0
    ? `${hInfo.name} by ${Math.abs(mc.medianMargin).toFixed(1)}`
    : `${aInfo.name} by ${Math.abs(mc.medianMargin).toFixed(1)}`;

  let explanation = `The model gives ${hInfo.name} a ${pct}% probability of winning this matchup. `;
  explanation += `${hInfo.name} currently holds an ELO rating of ${Math.round(hElo.elo)}, `;
  explanation += `${eloDiff > 0 ? eloDiff + " points higher" : Math.abs(eloDiff) + " points lower"} than ${aInfo.name}'s ${Math.round(aElo.elo)}. `;
  explanation += `Monte Carlo simulation (5,000 runs) projects the median result as ${marginStr} points. `;
  if (hFlag === "overperformer") {
    explanation += `${hInfo.name}'s win rate is significantly higher than their Pythagorean expectation suggests, indicating possible regression. `;
  } else if (aFlag === "underperformer") {
    explanation += `${aInfo.name} is underperforming their Pythagorean expectation and may be due for improvement. `;
  } else {
    explanation += `Both teams' records are roughly in line with their Pythagorean expectations. `;
  }
  explanation += `Confidence interval for margin: [${mc.ci_lo.toFixed(1)}, ${mc.ci_hi.toFixed(1)}] points.`;

  return {
    homeProb: ensembleProb,
    awayProb: 1 - ensembleProb,
    medianMargin: mc.medianMargin,
    ci_lo: mc.ci_lo,
    ci_hi: mc.ci_hi,
    pWin7:  mc.pWin7,
    pWin14: mc.pWin14,
    marginDist: mc.marginDist,
    systems,
    explanation,
    hElo: hElo.elo,
    aElo: aElo.elo,
    hSigma: hBay.sigma,
    aSigma: aBay.sigma,
    hFlag,
    aFlag,
  };
}

// ── Model calibration (historical accuracy) ───────────────────────────────
function computeCalibration(games, eloRatingsHistory) {
  // Use final ELO from games to compute predicted probs retroactively
  // Simplified: use post-game ELO for calibration curve
  const buckets = [
    { min: 0.50, max: 0.60, label: "50–60%", count: 0, correct: 0, totalProb: 0 },
    { min: 0.60, max: 0.70, label: "60–70%", count: 0, correct: 0, totalProb: 0 },
    { min: 0.70, max: 0.80, label: "70–80%", count: 0, correct: 0, totalProb: 0 },
    { min: 0.80, max: 1.01, label: "80%+",   count: 0, correct: 0, totalProb: 0 },
  ];

  // For calibration use only recent 3 seasons
  const recentGames = games.filter(g =>
    g.score1 != null && g.score2 != null &&
    g.season >= CURRENT_SEASON - 3 && g.season <= CURRENT_SEASON
  );

  // Track ELO as we go for more accurate calibration
  const elo = {};
  const getE = t => elo[t] || ELO_BASELINE;

  const calibData = [];

  for (const g of recentGames) {
    if (!NFL_TEAMS[g.home] || !NFL_TEAMS[g.away]) continue;
    const prob = eloWinProb(getE(g.home) + 65, getE(g.away));
    const homeWon = g.score1 > g.score2;

    // Use whichever side is predicted to win
    const predProb = Math.max(prob, 1 - prob);
    const predictedHome = prob > 0.5;
    const correct = predictedHome === homeWon;

    for (const b of buckets) {
      if (predProb >= b.min && predProb < b.max) {
        b.count++;
        if (correct) b.correct++;
        b.totalProb += predProb;
        break;
      }
    }

    calibData.push({ prob, homeWon });

    // Update elo
    const expHome = prob;
    const actual  = homeWon ? 1 : 0;
    const diff    = g.score1 - g.score2;
    const mov     = Math.log(Math.abs(diff) + 1) * (2.2 / (Math.abs(getE(g.home) - getE(g.away)) * 0.001 + 2.2));
    const k       = 20 * mov;
    elo[g.home] = getE(g.home) + k * (actual - expHome);
    elo[g.away] = getE(g.away) + k * ((1 - actual) - (1 - expHome));
  }

  // Build calibration curve (10 bins from 0.1 to 0.9)
  const calibCurve = [];
  for (let b = 0; b < 10; b++) {
    const lo = b / 10, hi = (b + 1) / 10;
    const bin = calibData.filter(d => d.prob >= lo && d.prob < hi);
    if (bin.length > 10) {
      calibCurve.push({
        predProb: (lo + hi) / 2,
        actualWr: bin.filter(d => d.homeWon).length / bin.length,
      });
    }
  }

  return {
    buckets: buckets.map(b => ({
      bucket:       b.label,
      count:        b.count,
      accuracy:     b.count > 0 ? b.correct / b.count : null,
      avgConf:      b.count > 0 ? b.totalProb / b.count : null,
    })),
    calibCurve,
  };
}
