function clampPercent(value) {
  return Math.max(0, Math.min(100, value));
}

function toShortCandidate(value) {
  if (!value) {
    return "--";
  }
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 9)}...${value.slice(-6)}`;
}

function countdownModeCopy(phase) {
  if (phase === "COUNTDOWN") {
    return {
      title: "Locking answer",
      copy: "Keeping score fixed while we capture the card.",
    };
  }
  if (phase === "SNAPSHOT") {
    return {
      title: "Capturing snapshot",
      copy: "Hold still for one brief moment.",
    };
  }
  return {
    title: "Preparing snapshot",
    copy: "Waiting for stability before capture.",
  };
}

export function initQuestionnaireView(store) {
  const questionLabel = document.getElementById("question-label");
  const identityMessage = document.getElementById("identity-message");
  const phaseValue = document.getElementById("phase-value");
  const meterFill = document.getElementById("meter-fill");
  const scoreValue = document.getElementById("score-value");
  const fusionValue = document.getElementById("fusion-value");
  const sourceValue = document.getElementById("source-value");
  const stateValue = document.getElementById("state-value");
  const minLabel = document.getElementById("min-label");
  const maxLabel = document.getElementById("max-label");
  const detailLine = document.getElementById("detail-line");

  const countdownShell = document.getElementById("countdown-shell");
  const countdownValue = document.getElementById("countdown-value");
  const countdownTitle = document.getElementById("countdown-title");
  const countdownCopy = document.getElementById("countdown-copy");
  const ringProgress = document.getElementById("ring-progress");

  const ringCircumference = 2 * Math.PI * 52;

  store.subscribe((state) => {
    const score = state.score;
    const candidateName = score.candidate_name || state.session?.candidate_name;

    questionLabel.textContent = score.question_label || "Place a business card to begin";
    // Show greeting with name if available
    let greetingText = score.message || "System starting...";
    if (candidateName && score.question_phase === "ACTIVE_SCORING") {
      greetingText = `Hallo ${candidateName}!`;
    }
    identityMessage.textContent = greetingText;
    phaseValue.textContent = score.question_phase || state.session.phase || "WAIT_FOR_MOVEMENT";

    fusionValue.textContent = score.fusion_state || "NO_TARGET";
    sourceValue.textContent = score.source || "idle";
    stateValue.textContent = state.app.state || "BOOT";

    minLabel.textContent = score.question_min_label || "0";
    maxLabel.textContent = score.question_max_label || "10";

    const visible = Boolean(score.visible);
    const scoreValueRaw = typeof score.score === "number" ? score.score : null;
    const rating = typeof score.rating === "number" ? score.rating : null;

    if (!visible || scoreValueRaw === null) {
      meterFill.style.width = "0%";
      meterFill.style.opacity = "0.2";
      scoreValue.textContent = "--";
    } else {
      meterFill.style.width = `${clampPercent(scoreValueRaw * 100)}%`;
      meterFill.style.opacity = score.fusion_state === "HAND_PROXY_ACTIVE" ? "0.82" : "1";
      scoreValue.textContent = rating !== null ? rating.toFixed(1) : scoreValueRaw.toFixed(2);
    }

    const phase = score.question_phase || state.session.phase;
    const hasCountdown = phase === "COUNTDOWN" || phase === "SNAPSHOT";
    if (hasCountdown) {
      countdownShell.classList.remove("hidden");
      const remaining = typeof score.countdown_remaining_s === "number"
        ? Math.max(0, score.countdown_remaining_s)
        : null;
      const textValue = remaining === null ? "..." : String(Math.max(1, Math.ceil(remaining)));
      countdownValue.textContent = textValue;

      const progress = remaining === null ? 0.35 : Math.max(0, Math.min(1, remaining / 3));
      ringProgress.style.strokeDasharray = String(ringCircumference);
      ringProgress.style.strokeDashoffset = String(ringCircumference * (1 - progress));

      const copy = countdownModeCopy(phase);
      countdownTitle.textContent = copy.title;
      countdownCopy.textContent = copy.copy;
    } else {
      countdownShell.classList.add("hidden");
    }

    detailLine.textContent = `candidate ${toShortCandidate(state.session.candidate_id)} • confidence ${Number(score.confidence || 0).toFixed(2)} • detector candidates ${Number(score.candidates_count || 0)}`;
  });
}
