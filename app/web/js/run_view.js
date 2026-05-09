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

function toFiniteInteger(value) {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.floor(value)) : null;
}

export function initRunView(store) {
  const questionLabel = document.getElementById("run-question-label");
  const message = document.getElementById("run-message");
  const sessionId = document.getElementById("run-session-id");
  const questionProgress = document.getElementById("run-question-progress");
  const countdownInline = document.getElementById("run-countdown-inline");
  const progressFill = document.getElementById("run-progress-fill");
  const progressLabel = document.getElementById("run-progress-label");
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
    const live = state.live?.score || {};

    const score = clampScore(live.score ?? q.score ?? t.score);
    const rating = typeof live.rating === "number" && Number.isFinite(live.rating)
      ? live.rating
      : (typeof q.rating === "number" && Number.isFinite(q.rating)
        ? q.rating
        : (typeof t.rating === "number" && Number.isFinite(t.rating) ? t.rating : null));
    const questionIndex = toFiniteInteger(live.question_index ?? q.question_index ?? 0) ?? 0;
    const questionCount = toFiniteInteger(q.question_count ?? 0) ?? 0;
    const questionProgressLabel = questionCount > 0 ? `${Math.min(questionIndex + 1, questionCount)}/${questionCount}` : "--";
    const progressPercent = questionCount > 0 ? Math.min(100, (Math.min(questionIndex + 1, questionCount) / questionCount) * 100) : 0;
    const countdownRemaining = typeof live.countdown_remaining_s === "number" && Number.isFinite(live.countdown_remaining_s)
      ? live.countdown_remaining_s
      : (typeof q.countdown_remaining_s === "number" && Number.isFinite(q.countdown_remaining_s)
        ? q.countdown_remaining_s
        : null);
    const phase = live.question_phase || q.phase || "WAIT_FOR_MOVEMENT";
    const questionText = live.question_label || q.question_label || "Place a business card to begin";
    const messageText = live.message || q.message || "System ready";

    if (questionLabel) {
      questionLabel.textContent = questionText;
    }
    if (message) {
      message.textContent = messageText;
    }
    if (sessionId) {
      sessionId.textContent = live.session_id || q.session_id || t.session_id || "--";
    }
    if (questionProgress) {
      questionProgress.textContent = questionProgressLabel;
    }
    if (progressLabel) {
      progressLabel.textContent = `${Math.round(progressPercent)}%`;
    }
    if (progressFill) {
      progressFill.style.width = `${progressPercent}%`;
    }
    if (minLabel) {
      minLabel.textContent = live.question_min_label || q.min_label || "0";
    }
    if (maxLabel) {
      maxLabel.textContent = live.question_max_label || q.max_label || "10";
    }
    if (meterFill) {
      meterFill.style.width = `${Math.round((score || 0) * 100)}%`;
      meterFill.style.opacity = score === null ? "0.25" : "1";
    }
    if (scoreValue) {
      scoreValue.textContent = rating === null ? "--" : rating.toFixed(1);
    }

    if (phasePill) {
      phasePill.textContent = phaseLabel(phase);
    }
    if (sourcePill) {
      sourcePill.textContent = live.source || t.source || "idle";
    }
    if (fusionPill) {
      fusionPill.textContent = live.fusion_state || t.fusion_state || "NO_TARGET";
    }
    if (confidencePill) {
      const conf = typeof live.confidence === "number" && Number.isFinite(live.confidence)
        ? live.confidence
        : (typeof t.confidence === "number" && Number.isFinite(t.confidence) ? t.confidence : null);
      confidencePill.textContent = conf === null ? "--" : conf.toFixed(2);
    }

    const showCountdown = phase === "COUNTDOWN" || phase === "SNAPSHOT_PENDING";
    if (countdownOverlay) {
      countdownOverlay.classList.toggle("hidden", !showCountdown);
    }

    if (countdownTitle) {
      countdownTitle.textContent = phase === "SNAPSHOT_PENDING" ? "Capturing" : "Hold still";
    }

    if (countdownValue) {
      if (phase === "COUNTDOWN" && typeof countdownRemaining === "number") {
        countdownValue.textContent = String(Math.max(0, Math.ceil(countdownRemaining)));
      } else if (phase === "SNAPSHOT_PENDING") {
        countdownValue.textContent = "OK";
      } else {
        countdownValue.textContent = "--";
      }
    }

    if (countdownInline) {
      if (phase === "COUNTDOWN" && typeof countdownRemaining === "number") {
        countdownInline.textContent = `${Math.max(0, Math.ceil(countdownRemaining))} s`;
      } else if (phase === "SNAPSHOT_PENDING") {
        countdownInline.textContent = "capturing";
      } else {
        countdownInline.textContent = "--";
      }
    }
  });
}
