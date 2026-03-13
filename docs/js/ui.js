// UI rendering — all 4 tabs plus sidebar
// State is held in window.APP (set by main.js)

// ── Utilities ──────────────────────────────────────────────────────────────
function fmtPct(p)   { return (p * 100).toFixed(1) + "%"; }
function fmtElo(e)   { return Math.round(e).toString(); }
function fmtNum(n,d) { return n.toFixed(d ?? 1); }

function logoUrl(abbr) {
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${(abbr||"nfl").toLowerCase()}.png`;
}

function teamColor(abbr) {
  return (NFL_TEAMS[abbr] || {}).color || "#58a6ff";
}

function probBarHtml(homeProb, homeAbbr, awayAbbr) {
  const hp = Math.round(homeProb * 100);
  const ap = 100 - hp;
  const hc = teamColor(homeAbbr);
  const ac = teamColor(awayAbbr);
  return `
    <div class="prob-bar-container">
      <div class="prob-bar-labels">
        <span style="color:${hc}">${hp}%</span>
        <span style="color:#8b949e;font-size:0.75rem">Win Probability</span>
        <span style="color:${ac}">${ap}%</span>
      </div>
      <div class="prob-bar">
        <div class="prob-bar-fill" style="width:${hp}%;background:linear-gradient(to right,${hc},${hc}aa)"></div>
      </div>
    </div>`;
}

function trendArrow(history) {
  if (!history || history.length < 2) return { arrow: "→", color: "#8b949e", delta: 0 };
  const recent = history.slice(-3);
  const delta = recent[recent.length-1].elo - recent[0].elo;
  return {
    arrow: delta > 5 ? "▲" : delta < -5 ? "▼" : "→",
    color: delta > 5 ? "#3fb950" : delta < -5 ? "#f85149" : "#8b949e",
    delta: Math.round(delta),
  };
}

// ── Tabs ───────────────────────────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === target));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.toggle("active", p.id === target));
      // Render on first visit
      if (!btn.dataset.rendered) {
        btn.dataset.rendered = "1";
        renderTab(target);
      }
    });
  });
}

function renderTab(id) {
  if (id === "tab-games")      renderGamesTab();
  if (id === "tab-predictor")  renderPredictorTab();
  if (id === "tab-leaderboard") renderLeaderboardTab();
  if (id === "tab-performance") renderPerformanceTab();
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function initSidebar() {
  const defs = [
    { id: "k_factor",          label: "K-Factor",        min: 10,   max: 40,  step: 1,   fmt: v => Math.round(v) },
    { id: "mov_weight",        label: "MOV Weight",       min: 0,    max: 2,   step: 0.1, fmt: v => v.toFixed(1)  },
    { id: "home_field",        label: "Home Field (ELO)", min: 0,    max: 100, step: 5,   fmt: v => Math.round(v) },
    { id: "recent_form_pct",   label: "Recent Form %",    min: 0,    max: 100, step: 5,   fmt: v => Math.round(v) + "%" },
    { id: "h2h_weight",        label: "H2H Weight",       min: 0,    max: 100, step: 5,   fmt: v => Math.round(v) },
    { id: "rest_travel_scale", label: "Rest/Travel Scale",min: 0,    max: 2,   step: 0.1, fmt: v => v.toFixed(1)  },
  ];
  const weightDefs = [
    { id: "w_elo",  label: "ELO Weight"   },
    { id: "w_pyth", label: "Pyth Weight"  },
    { id: "w_bayes",label: "Bayes Weight" },
    { id: "w_eff",  label: "Eff Weight"   },
  ];

  const container = document.getElementById("sidebar-sliders");
  if (!container) return;

  let html = '<div class="sidebar-title">Model Parameters</div>';
  for (const d of defs) {
    const val = PARAMS[d.id];
    html += `
      <div class="slider-group">
        <div class="slider-label">
          <span>${d.label}</span>
          <span id="val-${d.id}">${d.fmt(val)}</span>
        </div>
        <input type="range" id="sl-${d.id}" min="${d.min}" max="${d.max}" step="${d.step}" value="${val}">
      </div>`;
  }
  html += '<div class="sidebar-title" style="margin-top:16px">Ensemble Weights</div>';
  for (const d of weightDefs) {
    const val = PARAMS[d.id];
    html += `
      <div class="slider-group">
        <div class="slider-label">
          <span>${d.label}</span>
          <span id="val-${d.id}">${val}</span>
        </div>
        <input type="range" id="sl-${d.id}" min="0" max="100" step="5" value="${val}">
      </div>`;
  }

  container.innerHTML = html;

  // Bind events
  for (const d of [...defs, ...weightDefs]) {
    const el = document.getElementById(`sl-${d.id}`);
    if (!el) continue;
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      PARAMS[d.id] = v;
      const fmtEl = document.getElementById(`val-${d.id}`);
      if (fmtEl) fmtEl.textContent = d.fmt ? d.fmt(v) : Math.round(v);
      onParamsChange();
    });
  }
}

let _paramsChangeTimer = null;
function onParamsChange() {
  clearTimeout(_paramsChangeTimer);
  _paramsChangeTimer = setTimeout(() => {
    if (!window.APP || !window.APP.games) return;
    // Recompute ELO
    window.APP.eloRatings  = calculateEloRatings(window.APP.games, PARAMS);
    window.APP.pythagorean = calculatePythagoreanRatings(window.APP.games, window.APP.standings || {});
    window.APP.bayesian    = calculateBayesianRatings(window.APP.eloRatings);
    window.APP.efficiency  = calculateEfficiencyRatings(window.APP.eloRatings);
    // Re-render active tab
    const activeTab = document.querySelector(".tab-btn.active");
    if (activeTab) renderTab(activeTab.dataset.tab);
  }, 200);
}

// ── Tab 1: This Week's Games ───────────────────────────────────────────────
function renderGamesTab() {
  const el = document.getElementById("tab-games");
  if (!window.APP?.eloRatings) {
    el.innerHTML = '<div class="loading"><div class="spinner"></div>Loading game data…</div>';
    return;
  }

  const { scoreboard, eloRatings, pythagorean, bayesian, efficiency } = window.APP;

  // Last-updated
  const now = new Date();
  let html = `<div class="section-title">This Week's Games</div>
    <div class="section-sub" id="games-updated">Live data from ESPN · Last updated: ${now.toLocaleTimeString()}</div>`;

  if (!scoreboard?.length) {
    html += `<div class="empty-state"><div class="icon">🏈</div>
      <p>No games currently scheduled.<br><span style="font-size:0.8rem;color:#484f58">Check back during the NFL season.</span></p></div>`;
    el.innerHTML = html;
    return;
  }

  html += '<div class="game-grid">';
  for (const g of scoreboard) {
    const homeAbbr = g.home, awayAbbr = g.away;
    if (!NFL_TEAMS[homeAbbr] || !NFL_TEAMS[awayAbbr]) continue;

    const pred = predictMatchup(homeAbbr, awayAbbr, eloRatings, pythagorean, bayesian, efficiency, PARAMS);
    const hInfo = NFL_TEAMS[homeAbbr], aInfo = NFL_TEAMS[awayAbbr];
    const hEloR = eloRatings[homeAbbr] || {}, aEloR = eloRatings[awayAbbr] || {};
    const hBay  = bayesian[homeAbbr] || { sigma: 75 };
    const aBay  = bayesian[awayAbbr] || { sigma: 75 };
    const winner = pred.homeProb > 0.5 ? homeAbbr : awayAbbr;

    // Status
    let statusBadge = "";
    if (g.status === "STATUS_FINAL") {
      statusBadge = `<span style="color:#3fb950;font-weight:600">FINAL: ${g.homeScore}–${g.awayScore}</span>`;
    } else if (g.status === "STATUS_IN_PROGRESS") {
      statusBadge = `<span style="color:#d29922;font-weight:600">LIVE Q${g.period} ${g.clock} · ${g.homeScore}–${g.awayScore}</span>`;
    } else {
      const dt = new Date(g.date);
      statusBadge = `<span style="color:#8b949e">${dt.toLocaleDateString()} ${dt.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}</span>`;
    }

    const marginStr = pred.medianMargin > 0.5
      ? `${hInfo.name} −${Math.abs(pred.medianMargin).toFixed(1)}`
      : pred.medianMargin < -0.5
        ? `${aInfo.name} −${Math.abs(pred.medianMargin).toFixed(1)}`
        : "Pick'em";

    const travel = getTravelDistance(homeAbbr, awayAbbr, g.neutral === 1);

    html += `
    <div class="game-card">
      <div class="game-header">${statusBadge}${g.venue ? ` · ${g.venue}` : ""}</div>
      <div class="matchup-row">
        <div class="team-block home">
          <img class="team-logo" src="${logoUrl(homeAbbr)}" alt="${homeAbbr}" onerror="this.style.opacity=0.3">
          <div>
            <div class="team-abbr" style="color:${hInfo.color}">${homeAbbr}${winner === homeAbbr ? ' ★' : ''}</div>
            <div class="team-elo">${fmtElo(hEloR.elo || ELO_BASELINE)} ±${Math.round(hBay.sigma)} ELO</div>
          </div>
        </div>
        <div class="vs-block">VS</div>
        <div class="team-block away">
          <img class="team-logo" src="${logoUrl(awayAbbr)}" alt="${awayAbbr}" onerror="this.style.opacity=0.3">
          <div>
            <div class="team-abbr" style="color:${aInfo.color}">${winner === awayAbbr ? '★ ' : ''}${awayAbbr}</div>
            <div class="team-elo">${fmtElo(aEloR.elo || ELO_BASELINE)} ±${Math.round(aBay.sigma)} ELO</div>
          </div>
        </div>
      </div>
      ${probBarHtml(pred.homeProb, homeAbbr, awayAbbr)}
      <div class="margin-display">Projected: <b>${marginStr}</b> · CI [${pred.ci_lo.toFixed(1)}, ${pred.ci_hi.toFixed(1)}]</div>
      <div class="game-meta">
        <span>🏠 Rest: ${hEloR.rest1 ?? 7}d vs ${aEloR.rest2 ?? 7}d</span>
        ${travel > 50 ? `<span>✈ ${Math.round(travel)} mi</span>` : ""}
        ${g.spread != null ? `<span>📊 Spread: ${g.spread > 0 ? "+" : ""}${g.spread}</span>` : ""}
        <span>P(win 7+): ${fmtPct(pred.pWin7)}</span>
      </div>
    </div>`;
  }
  html += "</div>";
  el.innerHTML = html;
}

// ── Tab 2: Matchup Predictor ───────────────────────────────────────────────
function renderPredictorTab() {
  const el = document.getElementById("tab-predictor");
  const abbrs = Object.keys(NFL_TEAMS).sort();

  const teamOpts = abbrs.map(a =>
    `<option value="${a}">${a} — ${NFL_TEAMS[a].name}</option>`
  ).join("");

  el.innerHTML = `
    <div class="section-title">Matchup Predictor</div>
    <div class="section-sub">Select any two teams for a full prediction breakdown.</div>
    <div class="predictor-row">
      <div>
        <div style="font-size:0.75rem;color:#8b949e;margin-bottom:4px">HOME TEAM</div>
        <select class="team-select" id="pred-home">${teamOpts}</select>
      </div>
      <div class="vs-label">VS</div>
      <div>
        <div style="font-size:0.75rem;color:#8b949e;margin-bottom:4px">AWAY TEAM</div>
        <select class="team-select" id="pred-away">${teamOpts}</select>
      </div>
    </div>
    <div id="pred-result"></div>`;

  // Set defaults
  const homeEl = document.getElementById("pred-home");
  const awayEl = document.getElementById("pred-away");
  homeEl.value = "KC";
  awayEl.value = "PHI";

  function runPrediction() {
    const home = homeEl.value, away = awayEl.value;
    if (!home || !away || home === away) return;
    const { eloRatings, pythagorean, bayesian, efficiency } = window.APP || {};
    if (!eloRatings) return;
    const pred = predictMatchup(home, away, eloRatings, pythagorean, bayesian, efficiency, PARAMS);
    renderPredResult(pred, home, away);
  }

  homeEl.addEventListener("change", runPrediction);
  awayEl.addEventListener("change", runPrediction);
  runPrediction();
}

function renderPredResult(pred, homeAbbr, awayAbbr) {
  const el = document.getElementById("pred-result");
  if (!el) return;
  const hInfo = NFL_TEAMS[homeAbbr], aInfo = NFL_TEAMS[awayAbbr];
  const winner = pred.homeProb >= 0.5 ? hInfo.name : aInfo.name;
  const winnerColor = pred.homeProb >= 0.5 ? hInfo.color : aInfo.color;
  const winnerProb = Math.max(pred.homeProb, pred.awayProb);
  const hElo = (window.APP.eloRatings[homeAbbr] || {}).elo || ELO_BASELINE;
  const aElo = (window.APP.eloRatings[awayAbbr] || {}).elo || ELO_BASELINE;

  let html = `
    <div class="pred-result">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px">
        <img src="${logoUrl(homeAbbr)}" style="width:48px;height:48px;object-fit:contain">
        <div>
          <div class="big-prob" style="color:${winnerColor}">${fmtPct(winnerProb)}</div>
          <div class="big-prob-label">${winner} win probability</div>
        </div>
        <img src="${logoUrl(awayAbbr)}" style="width:48px;height:48px;object-fit:contain;margin-left:auto">
      </div>
      ${probBarHtml(pred.homeProb, homeAbbr, awayAbbr)}
    </div>

    <div class="breakdown-grid">
      ${Object.entries(pred.systems).map(([k, v]) => `
        <div class="breakdown-item">
          <div class="breakdown-label">${v.label}</div>
          <div class="breakdown-value" style="color:${v.prob >= 0.5 ? hInfo.color : aInfo.color}">${fmtPct(v.prob)}</div>
          <div style="font-size:0.72rem;color:#8b949e">${v.prob >= 0.5 ? homeAbbr : awayAbbr} favored</div>
        </div>`).join("")}
      <div class="breakdown-item">
        <div class="breakdown-label">ELO Ratings</div>
        <div class="breakdown-value">${fmtElo(hElo)} vs ${fmtElo(aElo)}</div>
        <div style="font-size:0.72rem;color:#8b949e">Diff: ${hElo > aElo ? "+" : ""}${Math.round(hElo - aElo)}</div>
      </div>
      <div class="breakdown-item">
        <div class="breakdown-label">Projected Margin</div>
        <div class="breakdown-value">${pred.medianMargin > 0 ? "+" : ""}${pred.medianMargin.toFixed(1)}</div>
        <div style="font-size:0.72rem;color:#8b949e">CI [${pred.ci_lo.toFixed(1)}, ${pred.ci_hi.toFixed(1)}]</div>
      </div>
      <div class="breakdown-item">
        <div class="breakdown-label">P(Win by 7+)</div>
        <div class="breakdown-value">${fmtPct(pred.pWin7)}</div>
      </div>
      <div class="breakdown-item">
        <div class="breakdown-label">P(Win by 14+)</div>
        <div class="breakdown-value">${fmtPct(pred.pWin14)}</div>
      </div>
    </div>`;

  // Pythagorean flags
  if (pred.hFlag || pred.aFlag) {
    html += `<div class="card" style="margin-bottom:12px">`;
    if (pred.hFlag) html += `<div class="${pred.hFlag === "overperformer" ? "flag-over" : "flag-under"}">
      ⬆ ${hInfo.name} is ${pred.hFlag === "overperformer" ? "overperforming" : "underperforming"} Pythagorean expectations</div>`;
    if (pred.aFlag) html += `<div class="${pred.aFlag === "overperformer" ? "flag-over" : "flag-under"}" style="margin-top:4px">
      ⬆ ${aInfo.name} is ${pred.aFlag === "overperformer" ? "overperforming" : "underperforming"} Pythagorean expectations</div>`;
    html += "</div>";
  }

  // System breakdown bar chart
  html += `<div class="chart-container">
    <div class="chart-title">System-by-System Win Probability (${homeAbbr})</div>
    <div id="chart-systems"></div>
  </div>`;

  // Monte Carlo histogram
  html += `<div class="chart-container">
    <div class="chart-title">Monte Carlo Margin Distribution (${homeAbbr} perspective)</div>
    <div id="chart-mc"></div>
  </div>`;

  // Explanation
  html += `<div class="explanation-box">${pred.explanation}</div>`;
  el.innerHTML = html;

  // Render Plotly charts
  requestAnimationFrame(() => {
    // Systems bar chart
    const sysLabels = Object.values(pred.systems).map(v => v.label);
    const sysProbs  = Object.values(pred.systems).map(v => Math.round(v.prob * 100));
    const sysColors = sysProbs.map(p => p >= 50 ? hInfo.color : aInfo.color);

    Plotly.newPlot("chart-systems", [{
      type: "bar", orientation: "h",
      y: sysLabels, x: sysProbs,
      marker: { color: sysColors },
      hovertemplate: "%{y}: %{x}%<extra></extra>",
    }], {
      plot_bgcolor: "#161b22", paper_bgcolor: "#0d1117",
      font: { color: "#e6edf3", size: 12 },
      xaxis: { title: "Win %", range: [0, 100], ticksuffix: "%" },
      margin: { l: 120, r: 20, t: 10, b: 40 },
      height: 220,
      shapes: [{ type: "line", x0: 50, x1: 50, y0: -0.5, y1: sysLabels.length - 0.5,
                 line: { color: "#484f58", dash: "dash", width: 1 } }],
    }, { responsive: true, displayModeBar: false });

    // MC histogram
    const binSize = 3;
    Plotly.newPlot("chart-mc", [{
      type: "histogram",
      x: pred.marginDist,
      xbins: { size: binSize },
      marker: { color: pred.marginDist.map(m => m > 0 ? hInfo.color + "99" : aInfo.color + "99"), line: { width: 0 } },
      hovertemplate: "Margin %{x}: %{y} sims<extra></extra>",
    }], {
      plot_bgcolor: "#161b22", paper_bgcolor: "#0d1117",
      font: { color: "#e6edf3", size: 12 },
      xaxis: { title: "Point Margin", zeroline: true, zerolinecolor: "#484f58" },
      yaxis: { title: "Simulations" },
      margin: { l: 50, r: 20, t: 10, b: 40 },
      height: 220,
    }, { responsive: true, displayModeBar: false });
  });
}

// ── Tab 3: ELO Leaderboard ────────────────────────────────────────────────
let _lbSortCol = "_elo", _lbSortAsc = false;

function renderLeaderboardTab() {
  const el = document.getElementById("tab-leaderboard");
  if (!window.APP?.eloRatings) {
    el.innerHTML = '<div class="loading"><div class="spinner"></div>Loading…</div>';
    return;
  }

  const { eloRatings, pythagorean, bayesian, efficiency, standings } = window.APP;

  const rows = Object.keys(NFL_TEAMS).map(abbr => {
    const er   = eloRatings[abbr]  || {};
    const pyth = pythagorean[abbr] || {};
    const bay  = bayesian[abbr]    || { sigma: 75 };
    const eff  = efficiency[abbr]  || { netEff: 0 };
    const std  = standings[abbr]   || {};
    const tr   = trendArrow(er.eloHistory);
    const wins   = er.wins   ?? std.wins   ?? 0;
    const losses = er.losses ?? std.losses ?? 0;

    return {
      abbr,
      _elo:    er.elo || ELO_BASELINE,
      _sigma:  bay.sigma,
      _pyth:   pyth.pythExp || 0.5,
      _netEff: eff.netEff || 0,
      _wins:   wins,
      record:  `${wins}–${losses}`,
      eloDisp: `${fmtElo(er.elo || ELO_BASELINE)} ±${Math.round(bay.sigma)}`,
      pythDisp: fmtPct(pyth.pythExp || 0.5),
      netEffDisp: (eff.netEff || 0).toFixed(3),
      flag:    pyth.flag,
      trend:   tr,
    };
  });

  // Sort
  rows.sort((a, b) => {
    const va = a[_lbSortCol], vb = b[_lbSortCol];
    return _lbSortAsc ? va - vb : vb - va;
  });

  const headers = [
    { key: null,     label: "#" },
    { key: null,     label: "Team" },
    { key: "_wins",  label: "Record" },
    { key: "_elo",   label: "ELO ±σ" },
    { key: "_pyth",  label: "Pyth Exp" },
    { key: "_netEff",label: "Net Eff" },
    { key: null,     label: "Trend" },
    { key: null,     label: "Flag" },
  ];

  let tableHtml = `<table class="lb-table"><thead><tr>`;
  for (const h of headers) {
    const sorted = h.key === _lbSortCol;
    tableHtml += `<th class="${sorted ? "sorted" : ""}" ${h.key ? `onclick="lbSort('${h.key}')"` : ""}>${h.label}${sorted ? (_lbSortAsc ? " ↑" : " ↓") : ""}</th>`;
  }
  tableHtml += "</tr></thead><tbody>";

  rows.forEach((row, i) => {
    const info = NFL_TEAMS[row.abbr];
    const flagHtml = row.flag
      ? `<span class="${row.flag === "overperformer" ? "flag-over" : "flag-under"}">
          ${row.flag === "overperformer" ? "⬆ Over" : "⬇ Under"}</span>`
      : `<span style="color:#484f58">—</span>`;

    tableHtml += `
      <tr>
        <td class="rank-cell">${i + 1}</td>
        <td>
          <div class="team-cell">
            <img src="${logoUrl(row.abbr)}" alt="${row.abbr}" onerror="this.style.opacity=0.3">
            <span style="color:${info.color};font-weight:700">${row.abbr}</span>
            <span style="color:#8b949e;font-size:0.8rem">${info.name}</span>
          </div>
        </td>
        <td style="color:#8b949e">${row.record}</td>
        <td style="color:${info.color};font-weight:600">${row.eloDisp}</td>
        <td>${row.pythDisp}</td>
        <td>${row.netEffDisp}</td>
        <td style="color:${row.trend.color}">${row.trend.arrow} ${Math.abs(row.trend.delta)}</td>
        <td>${flagHtml}</td>
      </tr>`;
  });
  tableHtml += "</tbody></table>";

  el.innerHTML = `
    <div class="section-title">ELO Leaderboard — All 32 Teams</div>
    <div class="section-sub">Sorted by ${_lbSortAsc ? "ascending" : "descending"} ${_lbSortCol.replace("_","").toUpperCase()}. Click headers to sort.</div>
    ${tableHtml}
    <div class="chart-container" style="margin-top:24px">
      <div class="chart-title">ELO Distribution</div>
      <div id="chart-elo-dist"></div>
    </div>`;

  // ELO distribution chart
  requestAnimationFrame(() => {
    const sorted = [...rows].sort((a,b) => a._elo - b._elo);
    Plotly.newPlot("chart-elo-dist", [{
      type: "bar", orientation: "h",
      y: sorted.map(r => r.abbr),
      x: sorted.map(r => r._elo),
      marker: { color: sorted.map(r => NFL_TEAMS[r.abbr].color) },
      error_x: { type: "data", array: sorted.map(r => r._sigma), visible: true, color: "#484f58" },
      hovertemplate: "%{y}: %{x:.0f} ELO<extra></extra>",
    }], {
      plot_bgcolor: "#0d1117", paper_bgcolor: "#0d1117",
      font: { color: "#e6edf3", size: 11 },
      xaxis: { title: "ELO Rating" },
      yaxis: { tickfont: { size: 10 } },
      margin: { l: 50, r: 20, t: 10, b: 40 },
      height: 700,
      shapes: [{ type: "line", x0: 1500, x1: 1500, y0: -0.5, y1: 31.5,
                 line: { color: "#30363d", dash: "dash", width: 1 } }],
    }, { responsive: true, displayModeBar: false });
  });
}

window.lbSort = function(col) {
  if (_lbSortCol === col) _lbSortAsc = !_lbSortAsc;
  else { _lbSortCol = col; _lbSortAsc = false; }
  renderLeaderboardTab();
};

// ── Tab 4: Model Performance ───────────────────────────────────────────────
function renderPerformanceTab() {
  const el = document.getElementById("tab-performance");
  if (!window.APP?.calib) {
    el.innerHTML = '<div class="loading"><div class="spinner"></div>Computing calibration…</div>';
    return;
  }

  const { calib, eloRatings } = window.APP;
  const topTeams = Object.entries(eloRatings)
    .sort((a,b) => b[1].elo - a[1].elo)
    .slice(0, 5);

  // Overall accuracy estimate
  const accuracy = calib.buckets.reduce((acc, b) => acc + (b.count * (b.accuracy || 0)), 0) /
                   calib.buckets.reduce((acc, b) => acc + b.count, 0);

  let html = `
    <div class="section-title">Model Performance</div>
    <div class="section-sub">Evaluated on nflverse historical data (seasons ${CURRENT_SEASON-3}–${CURRENT_SEASON}). Updated live as model parameters change.</div>

    <div class="metrics-row">
      <div class="metric-card">
        <div class="metric-value">${(accuracy * 100).toFixed(1)}%</div>
        <div class="metric-label">Accuracy</div>
        <div class="metric-note">↑ higher is better</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">${Object.values(eloRatings).reduce((s,r) => s + r.games, 0).toLocaleString()}</div>
        <div class="metric-label">Historical Games</div>
        <div class="metric-note">nflverse dataset</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">${topTeams[0]?.[0] || "—"}</div>
        <div class="metric-label">Top ELO Team</div>
        <div class="metric-note">${topTeams[0] ? fmtElo(topTeams[0][1].elo) + " ELO" : ""}</div>
      </div>
    </div>

    <div class="chart-container">
      <div class="chart-title">Calibration Curve (ELO model vs actual win rate)</div>
      <div id="chart-calib"></div>
    </div>

    <div style="margin-top:20px">
      <div class="chart-title">Confidence Bucket Accuracy</div>
      <table class="bucket-table">
        <thead><tr>
          <th>Confidence</th><th>Games</th><th>Accuracy</th><th>Avg Confidence</th>
        </tr></thead>
        <tbody>
          ${calib.buckets.map(b => {
            const acc = b.accuracy != null ? fmtPct(b.accuracy) : "—";
            const avgC = b.avgConf != null ? fmtPct(b.avgConf) : "—";
            const diff = b.accuracy != null && b.avgConf != null ? b.accuracy - b.avgConf : 0;
            const color = diff > -0.02 ? "#3fb950" : diff < -0.05 ? "#f85149" : "#e6edf3";
            return `<tr>
              <td><b>${b.bucket}</b></td>
              <td style="color:#8b949e">${b.count.toLocaleString()}</td>
              <td style="color:${color};font-weight:600">${acc}</td>
              <td style="color:#8b949e">${avgC}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>

    <div class="chart-container" style="margin-top:20px">
      <div class="chart-title">Current ELO Rankings — Top 16</div>
      <div id="chart-rankings"></div>
    </div>`;

  el.innerHTML = html;

  requestAnimationFrame(() => {
    // Calibration curve
    const cc = calib.calibCurve;
    Plotly.newPlot("chart-calib", [
      {
        type: "scatter", mode: "lines",
        x: [0, 1], y: [0, 1],
        line: { color: "#484f58", dash: "dash", width: 1 },
        name: "Perfect calibration",
        hoverinfo: "skip",
      },
      {
        type: "scatter", mode: "lines+markers",
        x: cc.map(d => d.predProb),
        y: cc.map(d => d.actualWr),
        line: { color: "#58a6ff", width: 2 },
        marker: { size: 8, color: "#58a6ff" },
        name: "ELO model",
        hovertemplate: "Predicted: %{x:.0%}<br>Actual: %{y:.0%}<extra></extra>",
      },
    ], {
      plot_bgcolor: "#161b22", paper_bgcolor: "#0d1117",
      font: { color: "#e6edf3", size: 12 },
      xaxis: { title: "Predicted Probability", tickformat: ".0%", range: [0, 1] },
      yaxis: { title: "Actual Win Rate",        tickformat: ".0%", range: [0, 1] },
      legend: { orientation: "h", y: 1.05 },
      margin: { l: 60, r: 20, t: 20, b: 50 },
      height: 300,
    }, { responsive: true, displayModeBar: false });

    // Rankings bar
    const top16 = Object.entries(eloRatings)
      .sort((a,b) => b[1].elo - a[1].elo)
      .slice(0, 16);
    Plotly.newPlot("chart-rankings", [{
      type: "bar", orientation: "h",
      y: top16.map(([a]) => a).reverse(),
      x: top16.map(([,r]) => r.elo).reverse(),
      marker: { color: top16.map(([a]) => NFL_TEAMS[a].color).reverse() },
      hovertemplate: "%{y}: %{x:.0f} ELO<extra></extra>",
    }], {
      plot_bgcolor: "#161b22", paper_bgcolor: "#0d1117",
      font: { color: "#e6edf3", size: 11 },
      xaxis: { title: "ELO Rating" },
      margin: { l: 50, r: 20, t: 10, b: 40 },
      height: 360,
    }, { responsive: true, displayModeBar: false });
  });
}
