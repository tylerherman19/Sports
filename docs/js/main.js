// Boot sequence: load all data, compute ratings, render dashboard

window.APP = {
  games:       null,
  scoreboard:  [],
  standings:   {},
  eloRatings:  {},
  pythagorean: {},
  bayesian:    {},
  efficiency:  {},
  calib:       null,
  loadedAt:    null,
};

async function boot() {
  showGlobalLoading(true, "Downloading NFL historical data (7,000+ games)…");

  try {
    // 1. Load historical data (the big one — nflverse CSV)
    const games = await loadHistoricalData();
    window.APP.games = games;

    updateLoadingMsg("Computing ELO ratings for all 32 teams…");

    // 2. Compute all ratings
    window.APP.eloRatings  = calculateEloRatings(games, PARAMS);
    window.APP.pythagorean = calculatePythagoreanRatings(games, {});
    window.APP.bayesian    = calculateBayesianRatings(window.APP.eloRatings);
    window.APP.efficiency  = calculateEfficiencyRatings(window.APP.eloRatings);

    updateLoadingMsg("Computing model calibration…");
    window.APP.calib = computeCalibration(games, window.APP.eloRatings);

    // 3. Load live ESPN data (non-blocking)
    updateLoadingMsg("Fetching live ESPN data…");
    [window.APP.scoreboard, window.APP.standings] = await Promise.all([
      loadScoreboard(),
      loadStandings(),
    ]);

    // Merge standings wins/losses into ELO ratings
    for (const [abbr, std] of Object.entries(window.APP.standings)) {
      if (window.APP.eloRatings[abbr]) {
        const er = window.APP.eloRatings[abbr];
        // Only override if standings has data and ELO doesn't (offseason)
        if ((er.wins + er.losses) === 0 && (std.wins + std.losses) > 0) {
          er.wins   = std.wins;
          er.losses = std.losses;
        }
      }
    }

    window.APP.loadedAt = new Date();
    showGlobalLoading(false);

    // 4. Initialize UI
    initTabs();
    initSidebar();

    // Render default tab (games)
    renderGamesTab();
    // Mark tab as rendered
    const firstBtn = document.querySelector(".tab-btn[data-tab='tab-games']");
    if (firstBtn) firstBtn.dataset.rendered = "1";

    updateLastUpdated();

    // 5. Start auto-refresh (live data every 30s)
    setInterval(async () => {
      [window.APP.scoreboard, window.APP.standings] = await Promise.all([
        loadScoreboard(),
        loadStandings(),
      ]);
      window.APP.loadedAt = new Date();
      updateLastUpdated();

      // Re-render active tab if it shows live data
      const activeTab = document.querySelector(".tab-btn.active");
      if (activeTab?.dataset.tab === "tab-games") {
        renderGamesTab();
      }
    }, 30_000);

  } catch (err) {
    showGlobalLoading(false);
    document.getElementById("content").innerHTML = `
      <div class="error-box">
        <b>Failed to load dashboard:</b> ${err.message}<br>
        <small style="color:#8b949e;margin-top:6px;display:block">
          This may be a temporary network issue. Try refreshing the page.
        </small>
      </div>`;
    console.error(err);
  }
}

function showGlobalLoading(show, msg) {
  const el = document.getElementById("global-loading");
  if (!el) return;
  el.style.display = show ? "flex" : "none";
  if (msg) el.querySelector(".loading-msg").textContent = msg;
}

function updateLoadingMsg(msg) {
  const el = document.getElementById("global-loading");
  if (el) el.querySelector(".loading-msg").textContent = msg;
}

function updateLastUpdated() {
  const el = document.getElementById("last-updated");
  if (!el || !window.APP.loadedAt) return;
  const secs = Math.round((Date.now() - window.APP.loadedAt.getTime()) / 1000);
  el.textContent = `Last updated: ${window.APP.loadedAt.toLocaleTimeString()} (${secs}s ago)`;
}

// Refresh button
window.manualRefresh = async function() {
  // Clear ESPN caches
  delete _cache["scoreboard"];
  delete _cache["standings"];
  [window.APP.scoreboard, window.APP.standings] = await Promise.all([
    loadScoreboard(),
    loadStandings(),
  ]);
  window.APP.loadedAt = new Date();
  updateLastUpdated();
  const activeTab = document.querySelector(".tab-btn.active");
  if (activeTab) renderTab(activeTab.dataset.tab);
};

// Update "X seconds ago" every 10s
setInterval(updateLastUpdated, 10_000);

// Start
document.addEventListener("DOMContentLoaded", boot);
