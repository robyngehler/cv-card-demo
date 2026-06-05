window.addEventListener("DOMContentLoaded", () => {
  const status = document.getElementById("status");
  const meterFill = document.getElementById("meter-fill");
  const scoreValue = document.getElementById("score-value");
  const sourceValue = document.getElementById("source-value");
  const stateValue = document.getElementById("state-value");
  const detailLine = document.getElementById("detail-line");

  let reconnectTimer = null;

  function setWaiting(message) {
    status.textContent = message;
    meterFill.style.width = "0%";
    meterFill.style.opacity = "0.2";
    scoreValue.textContent = "--";
    sourceValue.textContent = "waiting";
    detailLine.textContent = "Place a card on the table.";
  }

  function describeState(state, source, visible) {
    if (!visible) {
      return "Card lost. Waiting...";
    }
    if (source === "tracked_occluded") {
      return "Tracking card through short occlusion.";
    }
    if (state === "TRACKING") {
      return "Tracking card.";
    }
    if (state === "CANDIDATE_DETECTED") {
      return "Confirming card...";
    }
    return "System ready.";
  }

  async function refreshState() {
    try {
      const response = await fetch("/api/state");
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      stateValue.textContent = payload.state || "UNKNOWN";
      if (!payload.state || payload.state === "IDLE_NO_CARD") {
        status.textContent = "Place a card on the table.";
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
      const source = score.source || "unknown";
      const state = score.state || stateValue.textContent || "UNKNOWN";

      stateValue.textContent = state;
      sourceValue.textContent = source;
      status.textContent = describeState(state, source, visible);

      if (!visible || scoreNumber === null) {
        setWaiting("Card lost. Waiting...");
        stateValue.textContent = state;
        sourceValue.textContent = source;
        return;
      }

      const percent = Math.max(0, Math.min(100, scoreNumber * 100));
      meterFill.style.width = `${percent}%`;
      meterFill.style.opacity = source === "tracked_occluded" ? "0.55" : "1";
      scoreValue.textContent = scoreNumber.toFixed(2);
      detailLine.textContent = `confidence ${Number(score.confidence || 0).toFixed(2)} • ${Number(score.candidates_count || 0)} candidates`;
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
  connectScoreSocket();
  window.setInterval(refreshState, 2000);
});
