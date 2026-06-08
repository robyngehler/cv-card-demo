window.addEventListener("DOMContentLoaded", () => {
  const status = document.getElementById("status");
  const questionLabel = document.getElementById("question-label");
  const meterFill = document.getElementById("meter-fill");
  const scoreValue = document.getElementById("score-value");
  const sourceValue = document.getElementById("source-value");
  const stateValue = document.getElementById("state-value");
  const fusionValue = document.getElementById("fusion-value");
  const phaseValue = document.getElementById("phase-value");
  const candidateValue = document.getElementById("candidate-value");
  const minLabel = document.getElementById("min-label");
  const maxLabel = document.getElementById("max-label");
  const countdownPanel = document.getElementById("countdown-panel");
  const countdownValue = document.getElementById("countdown-value");
  const detailLine = document.getElementById("detail-line");
  const debugLine = document.getElementById("debug-line");
  const debugFrame = document.getElementById("debug-frame");

  let reconnectTimer = null;
  let debugFrameTimer = null;

  function setWaiting(message) {
    status.textContent = message;
    questionLabel.textContent = "Place a business card to begin";
    meterFill.style.width = "0%";
    meterFill.style.opacity = "0.2";
    scoreValue.textContent = "--";
    sourceValue.textContent = "waiting";
    fusionValue.textContent = "NO_TARGET";
    phaseValue.textContent = "WAIT_FOR_MOVEMENT";
    candidateValue.textContent = "--";
    minLabel.textContent = "0";
    maxLabel.textContent = "10";
    countdownPanel.classList.add("hidden");
    detailLine.textContent = "Place a card on the table.";
    debugLine.textContent = "No debug data yet.";
  }

  function describeState(state, source, fusionState, phase, visible) {
    if (state === "SNAPSHOT") {
      return "Saving the answer and preparing the next question.";
    }
    if (fusionState === "IDENTITY_PRECHECK") {
      return "Recognizing card...";
    }
    if (!visible) {
      return "Place a business card on the table.";
    }
    if (phase === "COUNTDOWN") {
      return "Hold still. Snapshot countdown is running.";
    }
    if (fusionState === "HAND_PROXY_ACTIVE") {
      return "Hand-card fusion is driving the live score.";
    }
    if (fusionState === "CARD_TO_HAND_MERGE") {
      return "Hand takeover detected. Keeping the score continuous.";
    }
    if (fusionState === "CARD_REACQUIRED") {
      return "Business card reacquired without changing the selected score.";
    }
    if (state === "CANDIDATE_DETECTED") {
      return "Confirming business card...";
    }
    if (state === "TRACKING") {
      return `Tracking through ${source}.`;
    }
    return "System ready.";
  }

  function shortCandidate(value) {
    if (!value) {
      return "--";
    }
    if (value.length <= 16) {
      return value;
    }
    return `${value.slice(0, 8)}...${value.slice(-6)}`;
  }

  function refreshDebugFrame() {
    debugFrame.src = `/api/debug-frame?ts=${Date.now()}`;
  }

  async function refreshState() {
    try {
      const response = await fetch("/api/state");
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      stateValue.textContent = payload.state || "UNKNOWN";
      fusionValue.textContent = payload.tracking?.fusion_state || fusionValue.textContent;
      candidateValue.textContent = shortCandidate(payload.session?.candidate_id);
      phaseValue.textContent = payload.session?.phase || phaseValue.textContent;
      if (!payload.state || payload.state === "IDLE_NO_CARD") {
        status.textContent = "Place a business card on the table.";
      }
    } catch (_error) {
      status.textContent = "Backend unreachable. Retrying...";
    }
  }

  function connectScoreSocket() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/score`);

    socket.addEventListener("open", () => {
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      refreshState();
    });

    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      const score = payload.score || {};
      const visible = Boolean(score.visible);
      const xNormalized = typeof score.x_normalized === "number" ? score.x_normalized : null;
      const scoreNumber = typeof score.score === "number" ? score.score : xNormalized;
      const ratingNumber = typeof score.rating === "number" ? score.rating : null;
      const source = score.source || "unknown";
      const state = score.state || stateValue.textContent || "UNKNOWN";
      const fusionState = score.fusion_state || "NO_TARGET";
      const phase = score.question_phase || "WAIT_FOR_MOVEMENT";
      const countdownRemaining = typeof score.countdown_remaining_s === "number" ? score.countdown_remaining_s : null;
      const identityStatus = score.identity_status || "--";
      const message = score.message || describeState(state, source, fusionState, phase, visible);

      stateValue.textContent = state;
      sourceValue.textContent = source;
      fusionValue.textContent = fusionState;
      phaseValue.textContent = phase;
      candidateValue.textContent = shortCandidate(score.candidate_id);
      questionLabel.textContent = score.question_label || "Place a business card to begin";
      minLabel.textContent = score.question_min_label || "0";
      maxLabel.textContent = score.question_max_label || "10";
      status.textContent = message;

      if (!visible || scoreNumber === null) {
        setWaiting("Waiting for a business card...");
        stateValue.textContent = state;
        sourceValue.textContent = source;
        fusionValue.textContent = fusionState;
        phaseValue.textContent = phase;
        candidateValue.textContent = shortCandidate(score.candidate_id);
        return;
      }

      const percent = Math.max(0, Math.min(100, scoreNumber * 100));
      meterFill.style.width = `${percent}%`;
      meterFill.style.opacity = fusionState === "HAND_PROXY_ACTIVE" ? "0.82" : "1";
      scoreValue.textContent = ratingNumber !== null ? ratingNumber.toFixed(1) : scoreNumber.toFixed(2);
      if (countdownRemaining !== null && phase === "COUNTDOWN") {
        countdownPanel.classList.remove("hidden");
        countdownValue.textContent = String(Math.max(1, Math.ceil(countdownRemaining)));
      } else {
        countdownPanel.classList.add("hidden");
      }
      detailLine.textContent = `confidence ${Number(score.confidence || 0).toFixed(2)} • ${Number(score.candidates_count || 0)} detector candidates`;
      const debug = score.debug || {};
      debugLine.textContent = `identity ${identityStatus} • card_source ${debug.card_source || "--"} • hand_visible ${debug.hand_visible ? "yes" : "no"} • hand_valid ${debug.hand_valid ? "yes" : "no"}`;
    });

    socket.addEventListener("close", () => {
      status.textContent = "Connection lost. Reconnecting...";
      reconnectTimer = window.setTimeout(connectScoreSocket, 1000);
    });

    socket.addEventListener("error", () => {
      socket.close();
    });
  }

  setWaiting("Backend is starting...");
  refreshState();
  refreshDebugFrame();
  connectScoreSocket();
  window.setInterval(refreshState, 2000);
  debugFrameTimer = window.setInterval(refreshDebugFrame, 1200);
});
