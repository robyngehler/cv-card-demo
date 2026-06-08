import { getJson, openWebSocket } from "./js/api.js";
import { createStateStore } from "./js/state_store.js";
import { initTabs } from "./js/tabs.js";
import { initQuestionnaireView } from "./js/questionnaire_view.js";
import { initDebugView } from "./js/debug_view.js";
import { initControlView } from "./js/control_view.js";

function safeNumber(value, fallback = null) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

window.addEventListener("DOMContentLoaded", () => {
  const connectionPill = document.getElementById("connection-pill");
  const store = createStateStore();

  initTabs(store);
  initQuestionnaireView(store);
  initDebugView(store);
  initControlView(store);

  let reconnectTimer = null;

  function applyScoreUpdate(payload) {
    const score = payload?.score || {};
    const oldState = store.state.app.state;
    const oldPhase = store.state.score.question_phase;
    const oldFusion = store.state.score.fusion_state;
    const oldCandidate = store.state.session.candidate_id;

    const visible = Boolean(score.visible);
    const normalizedScore = safeNumber(score.score, safeNumber(score.x_normalized, null));

    store.merge("score", {
      visible,
      score: normalizedScore,
      rating: safeNumber(score.rating, null),
      source: score.source || "unknown",
      fusion_state: score.fusion_state || "NO_TARGET",
      question_label: score.question_label || "Place a business card to begin",
      question_min_label: score.question_min_label || "0",
      question_max_label: score.question_max_label || "10",
      countdown_remaining_s: safeNumber(score.countdown_remaining_s, null),
      message: score.message || "System ready",
      confidence: safeNumber(score.confidence, 0),
      candidates_count: safeNumber(score.candidates_count, 0),
      question_phase: score.question_phase || store.state.session.phase || "WAIT_FOR_MOVEMENT",
    });

    store.merge("session", {
      candidate_id: score.candidate_id || store.state.session.candidate_id,
      identity_status: score.identity_status || store.state.session.identity_status,
      current_question_id: score.question_id || store.state.session.current_question_id,
      phase: score.question_phase || store.state.session.phase,
    });

    store.merge("app", {
      state: score.state || store.state.app.state,
    });

    store.merge("connection", {
      scoreWs: "CONNECTED",
      lastScoreAt: new Date().toISOString(),
      reconnectAttempt: 0,
      backendReachable: true,
    });

    if (oldState !== store.state.app.state) {
      store.pushEvent("state", `${oldState || "UNKNOWN"} -> ${store.state.app.state}`);
    }
    if (oldPhase !== store.state.score.question_phase) {
      store.pushEvent("phase", `${oldPhase || "--"} -> ${store.state.score.question_phase}`);
    }
    if (oldFusion !== store.state.score.fusion_state) {
      store.pushEvent("fusion", `${oldFusion || "--"} -> ${store.state.score.fusion_state}`);
    }
    if ((score.candidate_id || null) !== (oldCandidate || null)) {
      store.pushEvent("candidate", `${oldCandidate || "--"} -> ${score.candidate_id || "--"}`);
    }
    if (store.state.score.question_phase === "COUNTDOWN") {
      store.pushEvent("countdown", "Countdown active");
    }
    if (store.state.score.question_phase === "SNAPSHOT") {
      store.pushEvent("snapshot", "Snapshot triggered");
    }
  }

  function connectScoreSocket() {
    const socket = openWebSocket("/ws/score");

    socket.addEventListener("open", () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      store.merge("connection", {
        scoreWs: "CONNECTED",
        reconnectAttempt: 0,
      });
      store.pushEvent("ws", "Score websocket connected");
    });

    socket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        applyScoreUpdate(payload);
      } catch (_error) {
        store.pushEvent("ws", "Invalid websocket payload");
      }
    });

    socket.addEventListener("close", () => {
      const nextAttempt = (store.state.connection.reconnectAttempt || 0) + 1;
      const delayMs = Math.min(10000, 400 * Math.pow(2, Math.min(nextAttempt, 5)));
      store.merge("connection", {
        scoreWs: "DISCONNECTED",
        reconnectAttempt: nextAttempt,
      });
      store.pushEvent("ws", `Score websocket disconnected, reconnect in ${delayMs}ms`);
      reconnectTimer = setTimeout(connectScoreSocket, delayMs);
    });

    socket.addEventListener("error", () => {
      socket.close();
    });
  }

  async function pollState() {
    const response = await getJson("/api/state");
    if (!response.ok || !response.data) {
      store.merge("connection", { backendReachable: false });
      return;
    }

    store.merge("connection", { backendReachable: true });
    store.merge("app", {
      state: response.data.state || "UNKNOWN",
      substate: response.data.substate || null,
    });
    store.merge("session", {
      session_id: response.data.session?.session_id || null,
      candidate_id: response.data.session?.candidate_id || null,
      identity_status: response.data.session?.identity_status || "UNKNOWN",
      current_question_id: response.data.session?.current_question_id || null,
      phase: response.data.session?.phase || store.state.session.phase,
      completed: Boolean(response.data.session?.completed),
      question_index: response.data.session?.question_index || 0,
    });
    store.merge("runtime", {
      tracking: response.data.tracking || {},
      card: response.data.card || {},
      hand: response.data.hand || {},
    });
  }

  async function pollHealth() {
    const response = await getJson("/api/health");
    if (!response.ok || !response.data) {
      store.merge("health", { status: "UNREACHABLE" });
      return;
    }

    const previous = store.state.health.services || {};
    const current = response.data.services || {};

    Object.keys(current).forEach((key) => {
      const prevStatus = previous[key]?.status || previous[key] || "--";
      const nextStatus = current[key]?.status || current[key] || "--";
      if (prevStatus !== nextStatus) {
        store.pushEvent("health", `${key}: ${prevStatus} -> ${nextStatus}`);
      }
    });

    store.merge("health", {
      status: "OK",
      services: current,
    });
  }

  async function loadVersion() {
    const response = await getJson("/api/version");
    if (!response.ok || !response.data) {
      return;
    }
    store.merge("app", {
      name: response.data.app || "cv-card-demo",
      version: response.data.version || "0.1.0",
    });
  }

  store.subscribe((state) => {
    const ws = state.connection.scoreWs;
    const reachable = state.connection.backendReachable;
    connectionPill.textContent = `${ws}${reachable ? "" : " / API DOWN"}`;
  });

  store.pushEvent("app", "Frontend console initialized");
  connectScoreSocket();
  loadVersion();
  pollState();
  pollHealth();

  setInterval(() => {
    pollState().catch(() => {
      store.pushEvent("state", "State polling failed");
    });
  }, 1000);

  setInterval(() => {
    pollHealth().catch(() => {
      store.pushEvent("health", "Health polling failed");
    });
  }, 2000);
});
