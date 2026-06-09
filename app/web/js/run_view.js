function clampScore(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return Math.max(0, Math.min(1, value));
}

function phaseLabel(phase) {
  if (!phase) {
    return "WAIT_FOR_MOVEMENT";
  }
  return String(phase);
}

export function initRunView(store) {
  const questionLabel = document.getElementById("run-question-label");
  const message = document.getElementById("run-message");
  const meterFill = document.getElementById("run-meter-fill");
  const scoreValue = document.getElementById("run-score-value");
  const minLabel = document.getElementById("run-min-label");
  const maxLabel = document.getElementById("run-max-label");
  const phasePill = document.getElementById("pill-phase");
  const sourcePill = document.getElementById("pill-source");
  const fusionPill = document.getElementById("pill-fusion");
  const confidencePill = document.getElementById("pill-confidence");
  const countdownOverlay = document.getElementById("run-countdown-overlay");
  const countdownValue = document.getElementById("run-countdown-value");
  const countdownTitle = document.getElementById("run-countdown-title");

  store.subscribe((state) => {
    const snap = state.snapshot;
    const q = snap?.questionnaire || {};
    const t = snap?.tracking || {};

    const score = clampScore(q.score);
    const rating = typeof q.rating === "number" && Number.isFinite(q.rating) ? q.rating : null;

    if (questionLabel) {
      questionLabel.textContent = q.question_label || "Place a business card to begin";
    }
    if (message) {
      message.textContent = q.message || "System ready";
    }
    if (minLabel) {
      minLabel.textContent = q.min_label || "0";
    }
    if (maxLabel) {
      maxLabel.textContent = q.max_label || "10";
    }
    if (meterFill) {
      meterFill.style.width = `${Math.round((score || 0) * 100)}%`;
      meterFill.style.opacity = score === null ? "0.25" : "1";
    }
    if (scoreValue) {
      scoreValue.textContent = rating === null ? "--" : rating.toFixed(1);
    }

    if (phasePill) {
      phasePill.textContent = phaseLabel(q.phase);
    }
    if (sourcePill) {
      sourcePill.textContent = t.source || "idle";
    }
    if (fusionPill) {
      fusionPill.textContent = t.fusion_state || "NO_TARGET";
    }
    if (confidencePill) {
      const conf = typeof t.confidence === "number" && Number.isFinite(t.confidence) ? t.confidence : null;
      confidencePill.textContent = conf === null ? "--" : conf.toFixed(2);
    }

    const phase = q.phase || "WAIT_FOR_MOVEMENT";
    const showCountdown = phase === "COUNTDOWN" || phase === "SNAPSHOT_PENDING";
    if (countdownOverlay) {
      countdownOverlay.classList.toggle("hidden", !showCountdown);
    }

    if (countdownTitle) {
      countdownTitle.textContent = phase === "SNAPSHOT_PENDING" ? "Capturing" : "Hold still";
    }

    if (countdownValue) {
      if (phase === "COUNTDOWN" && typeof q.countdown_remaining_s === "number") {
        countdownValue.textContent = String(Math.max(0, Math.ceil(q.countdown_remaining_s)));
      } else if (phase === "SNAPSHOT_PENDING") {
        countdownValue.textContent = "OK";
      } else {
        countdownValue.textContent = "--";
      }
    }
  });
}
