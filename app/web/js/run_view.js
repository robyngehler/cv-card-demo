const STAR_SVG = '<svg viewBox="0 0 100 100"><path d="M50 6 L62 38 L96 38 L68 58 L79 92 L50 72 L21 92 L32 58 L4 38 L38 38 Z"/></svg>';
const RING_LEN = 194.78;
const TOTAL_COUNTDOWN_S = 3;

function clampScore(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.max(0, Math.min(1, value));
}

function scoreToStar(score) {
  if (score === null) return null;
  return Math.max(1, Math.min(5, Math.ceil(score * 5)));
}

function buildSections() {
  const container = document.getElementById("run-sections");
  if (!container) return;
  container.innerHTML = "";
  for (let s = 1; s <= 5; s++) {
    const div = document.createElement("div");
    div.className = "run-section";
    div.dataset.star = String(s);
    let starsHtml = "";
    for (let i = 0; i < s; i++) starsHtml += STAR_SVG;
    div.innerHTML =
      `<div class="run-section-ring"></div>` +
      `<div class="run-section-num">${s}</div>` +
      `<div class="run-section-stars">${starsHtml}</div>`;
    container.appendChild(div);
  }
}

function buildStars() {
  const container = document.getElementById("run-stars");
  if (!container) return;
  container.innerHTML = "";
  for (let i = 0; i < 5; i++) {
    const div = document.createElement("div");
    div.className = "run-star";
    div.innerHTML = STAR_SVG;
    container.appendChild(div);
  }
}

function buildQProgress(count) {
  const container = document.getElementById("run-q-progress");
  if (!container) return;
  container.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const div = document.createElement("div");
    div.className = "run-q-dot";
    container.appendChild(div);
  }
}

const PANELS = {
  idle: "run-pv-idle",
  greet: "run-pv-greet",
  question: "run-pv-question",
  thanks: "run-pv-thanks",
};

const BOOT_STATES = new Set(["BOOT", "INIT_CAM", "CALIBRATION", "RECOVERY", "ERROR_SAFE"]);
const IDLE_STATES = new Set(["IDLE_NO_CARD", "CANDIDATE_DETECTED"]);
const TRACKING_STATES = new Set(["TRACKING", "SNAPSHOT"]);

export function initRunView(store) {
  buildSections();
  buildStars();

  const sectionEls = document.querySelectorAll(".run-section");
  let lastQCount = 0;

  store.subscribe((state) => {
    const snap = state.snapshot || {};
    const q = snap.questionnaire || {};
    const session = snap.session || {};
    const live = state.live?.score || {};
    const appState = snap.app?.state || snap.state || "";

    const score = clampScore(live.score ?? q.score ?? snap.tracking?.score);
    const star = scoreToStar(score);
    const phase = live.question_phase || q.phase || "WAIT_FOR_MOVEMENT";
    // question_index / question_count live on the session payload, with the
    // live score stream as a faster-updating fallback.
    const questionIndex =
      typeof live.question_index === "number"
        ? live.question_index
        : typeof session.question_index === "number"
        ? session.question_index
        : typeof q.question_index === "number"
        ? q.question_index
        : 0;
    const questionCount =
      typeof session.question_count === "number"
        ? session.question_count
        : typeof q.question_count === "number"
        ? q.question_count
        : 0;
    const countdownRemaining =
      typeof live.countdown_remaining_s === "number"
        ? live.countdown_remaining_s
        : typeof q.countdown_remaining_s === "number"
        ? q.countdown_remaining_s
        : null;
    const questionText = live.question_label || q.question_label || "";
    const sessionName = q.session_name || q.name || q.identity?.name || "";
    const sessionMail = q.session_mail || q.email || q.identity?.email || "";

    // Determine which left panel to show.
    //
    // Drive this from the questionnaire SESSION, not the raw app state: card
    // detection can briefly bounce TRACKING -> IDLE -> TRACKING, but the
    // session (created once a card is confirmed) persists across those blips,
    // so the question panel stays put instead of flickering back to "Karte
    // auflegen".
    const isBooting = !appState || BOOT_STATES.has(appState);
    const isTracking = TRACKING_STATES.has(appState);
    const sessionId = session.session_id || q.session_id || live.session_id || null;
    const completed =
      session.completed === true ||
      phase === "DONE" ||
      phase === "THANKS" ||
      phase === "COMPLETE";
    const hasActiveSession = Boolean(sessionId) && !completed;

    let activePanel = "idle";
    if (!isBooting) {
      if (completed) {
        activePanel = "thanks";
      } else if (phase === "GREETING") {
        activePanel = "greet";
      } else if (hasActiveSession || isTracking) {
        activePanel = "question";
      }
    }

    // Show / hide left panels
    for (const [key, id] of Object.entries(PANELS)) {
      const el = document.getElementById(id);
      if (el) el.style.display = key === activePanel ? "" : "none";
    }

    // Section highlighting
    sectionEls.forEach((el) => {
      el.classList.toggle("active", star !== null && +el.dataset.star === star);
    });

    // Stars in question panel
    document.querySelectorAll(".run-star").forEach((el, i) => {
      el.classList.toggle("on", star !== null && i < star);
    });

    const ratingVal = document.getElementById("run-rating-val");
    if (ratingVal) ratingVal.textContent = star !== null ? String(star) : "—";

    // Question text & counter — map English backend defaults to German
    const displayText =
      !questionText || questionText === "Place a business card to begin"
        ? "Karte über die fünf Felder bewegen – die Position bestimmt die Sterne."
        : questionText;
    const qText = document.getElementById("run-q-text");
    if (qText) qText.textContent = displayText;

    const qCounter = document.getElementById("run-q-counter");
    if (qCounter && questionCount > 0) {
      qCounter.textContent = `Frage ${questionIndex + 1} von ${questionCount}`;
    }

    // Q-progress dots
    if (questionCount !== lastQCount) {
      buildQProgress(questionCount);
      lastQCount = questionCount;
    }
    document.querySelectorAll(".run-q-dot").forEach((dot, i) => {
      dot.className =
        "run-q-dot" +
        (i < questionIndex ? " done" : i === questionIndex ? " active" : "");
    });

    // Greet / thanks names
    const greetName = document.getElementById("run-greet-name");
    if (greetName) greetName.textContent = sessionName || "—";

    const greetMail = document.getElementById("run-greet-mail");
    if (greetMail) greetMail.textContent = sessionMail ? `Erkannt: ${sessionMail}` : "";

    const thanksName = document.getElementById("run-thanks-name");
    if (thanksName) thanksName.textContent = sessionName || "—";

    // Timer ring
    const timer = document.getElementById("run-timer");
    const ringFg = document.getElementById("run-ring-fg");
    const ringNum = document.getElementById("run-ring-num");
    const showTimer = phase === "COUNTDOWN" && countdownRemaining !== null;
    if (timer) timer.classList.toggle("show", showTimer);

    if (showTimer && ringFg && ringNum) {
      const remaining = Math.max(0, countdownRemaining);
      const offset = Math.min(RING_LEN, RING_LEN * (1 - remaining / TOTAL_COUNTDOWN_S)).toFixed(1);
      ringFg.style.strokeDashoffset = offset;
      ringNum.textContent = String(Math.ceil(remaining) || 0);
    }

    // Saved flash
    const savedFlash = document.getElementById("run-saved-flash");
    if (savedFlash) {
      savedFlash.classList.toggle(
        "show",
        phase === "SAVED" || phase === "SNAPSHOT_PENDING" || phase === "SNAPSHOT"
      );
    }

    // Hint text
    const hint = document.getElementById("run-hint");
    if (hint) {
      if (activePanel === "idle") {
        hint.textContent = isBooting ? "System startet …" : "Bereit – Visitenkarte auflegen.";
      } else if (activePanel === "greet") {
        hint.textContent = sessionName ? `Erkannt: ${sessionName}` : "Karte erkannt.";
      } else if (activePanel === "question") {
        hint.textContent =
          phase === "COUNTDOWN"
            ? "Karte ruhig halten …"
            : "Karte auf dem Tisch bewegen – die Spalte bestimmt die Sterne.";
      } else if (activePanel === "thanks") {
        hint.textContent = "Danke fürs Mitmachen!";
      }
    }
  });
}
