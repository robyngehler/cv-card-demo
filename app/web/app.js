import { getJson, openScoreSocket, openUiEvents, postJson } from "./js/api.js";
import { createStateStore } from "./js/state_store.js";
import { initRunView } from "./js/run_view.js";
import { initLiveView } from "./js/live_view.js";
import { initConfigureView } from "./js/configure_view.js";
import { initDiagnosticsView } from "./js/diagnostics_view.js";

window.addEventListener("DOMContentLoaded", () => {
  const connectionPill = document.getElementById("connection-pill");
  const runView = document.getElementById("run-view");
  const configureView = document.getElementById("configure-view");
  const modeRunButton = document.getElementById("mode-run");
  const modeConfigureButton = document.getElementById("mode-configure");
  const store = createStateStore();

  initRunView(store);
  initLiveView(store);
  initConfigureView(store);
  initDiagnosticsView(store);

  let reconnectTimer = null;
  let eventSource = null;
  let scoreReconnectTimer = null;
  let scoreSocket = null;
  let snapshotPollTimer = null;
  let consecutiveSnapshotFailures = 0;

  function updateModeView(mode) {
    const isRun = mode !== "CONFIGURE_CAMERA";
    if (runView) {
      runView.classList.toggle("hidden", !isRun);
    }
    if (configureView) {
      configureView.classList.toggle("hidden", isRun);
    }
    if (modeRunButton) {
      modeRunButton.classList.toggle("active", isRun);
    }
    if (modeConfigureButton) {
      modeConfigureButton.classList.toggle("active", !isRun);
    }
  }

  function applySnapshot(snapshot) {
    const previous = store.state.snapshot;
    const accepted = store.setSnapshot(snapshot);
    if (!accepted) {
      return;
    }

    const previousState = previous?.app?.state || "--";
    const currentState = snapshot?.app?.state || "--";
    const previousPhase = previous?.questionnaire?.phase || "--";
    const currentPhase = snapshot?.questionnaire?.phase || "--";

    if (previousState !== currentState) {
      store.pushEvent("state", `${previousState} -> ${currentState}`);
    }
    if (previousPhase !== currentPhase) {
      store.pushEvent("phase", `${previousPhase} -> ${currentPhase}`);
    }

    store.merge("connection", {
      events: "CONNECTED",
      backendReachable: true,
      reconnectAttempt: 0,
    });
    consecutiveSnapshotFailures = 0;

    updateModeView(snapshot?.app?.mode || "RUN");
  }

  function clearReconnectTimer(timerId) {
    if (timerId) {
      clearTimeout(timerId);
    }
    return null;
  }

  function scheduleReconnect(previousTimer, callback) {
    const nextAttempt = (store.state.connection.reconnectAttempt || 0) + 1;
    const delayMs = Math.min(10000, 400 * Math.pow(2, Math.min(nextAttempt, 5)));
    return {
      timer: setTimeout(callback, delayMs),
      delayMs,
      nextAttempt,
      previousTimer,
    };
  }

  function connectEventStream() {
    eventSource = openUiEvents();

    eventSource.addEventListener("open", () => {
      reconnectTimer = clearReconnectTimer(reconnectTimer);
      store.merge("connection", {
        events: "CONNECTED",
        backendReachable: true,
        reconnectAttempt: 0,
      });
      store.pushEvent("events", "SSE connected");
    });

    eventSource.addEventListener("ui_snapshot", (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        applySnapshot(payload);
      } catch (_error) {
        store.pushEvent("events", "Invalid SSE payload");
      }
    });

    eventSource.addEventListener("error", () => {
      if (eventSource) {
        eventSource.close();
      }
      const reconnect = scheduleReconnect(reconnectTimer, connectEventStream);
      reconnectTimer = reconnect.timer;
      store.merge("connection", {
        events: "DISCONNECTED",
        reconnectAttempt: reconnect.nextAttempt,
      });
      store.pushEvent("events", `SSE disconnected, reconnect in ${reconnect.delayMs}ms`);
    });
  }

  function connectScoreStream() {
    scoreSocket = openScoreSocket();

    scoreSocket.addEventListener("open", () => {
      scoreReconnectTimer = clearReconnectTimer(scoreReconnectTimer);
      store.merge("connection", {
        score: "CONNECTED",
        backendReachable: true,
      });
      store.pushEvent("score", "Score stream connected");
    });

    scoreSocket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        if (payload?.type === "score_update" && payload.score) {
          store.merge("live", {
            score: payload.score,
            lastEventAt: new Date().toISOString(),
          });
        }
      } catch (_error) {
        store.pushEvent("score", "Invalid score payload");
      }
    });

    scoreSocket.addEventListener("close", () => {
      const reconnect = scheduleReconnect(scoreReconnectTimer, connectScoreStream);
      scoreReconnectTimer = reconnect.timer;
      store.merge("connection", {
        score: "DISCONNECTED",
      });
      store.pushEvent("score", `Score stream disconnected, reconnect in ${reconnect.delayMs}ms`);
    });

    scoreSocket.addEventListener("error", () => {
      if (scoreSocket) {
        scoreSocket.close();
      }
    });
  }

  async function loadInitialSnapshot() {
    try {
      const response = await getJson("/api/ui/snapshot");
      if (!response.ok || !response.data) {
        consecutiveSnapshotFailures += 1;
        if (consecutiveSnapshotFailures >= 3) {
          store.merge("connection", { backendReachable: false });
        }
        return;
      }
      applySnapshot(response.data);
    } catch (_error) {
      consecutiveSnapshotFailures += 1;
      if (consecutiveSnapshotFailures >= 3) {
        store.merge("connection", { backendReachable: false });
      }
    }
  }

  async function refreshSnapshotOnce() {
    try {
      const response = await getJson("/api/ui/snapshot");
      if (response.ok && response.data) {
        applySnapshot(response.data);
        return;
      }
      consecutiveSnapshotFailures += 1;
      if (consecutiveSnapshotFailures >= 3) {
        store.merge("connection", { backendReachable: false });
      }
    } catch (_error) {
      consecutiveSnapshotFailures += 1;
      if (consecutiveSnapshotFailures >= 3) {
        store.merge("connection", { backendReachable: false });
      }
    }
  }

  store.subscribe((state) => {
    const ws = state.connection.events;
    const score = state.connection.score;
    const reachable = state.connection.backendReachable;
    const connectionState = !reachable
      ? { label: "API DOWN", className: "error" }
      : ws === "CONNECTED" && score === "CONNECTED"
        ? { label: "LIVE", className: "ok" }
        : ws === "DISCONNECTED" || score === "DISCONNECTED"
          ? { label: "RECONNECTING", className: "warn" }
          : { label: "CONNECTING", className: "warn" };
    if (connectionPill) {
      connectionPill.textContent = connectionState.label;
      connectionPill.classList.remove("ok", "warn", "error");
      connectionPill.classList.add(connectionState.className);
    }
  });

  if (modeRunButton) {
    modeRunButton.addEventListener("click", () => {
      postJson("/api/mode/run", {})
        .then(() => {
          store.patch("ui.mode", "RUN");
          updateModeView("RUN");
          store.pushEvent("mode", "Switched to RUN");
          return refreshSnapshotOnce();
        })
        .catch(() => {
          store.pushEvent("mode", "Failed to switch to RUN");
        });
    });
  }

  if (modeConfigureButton) {
    modeConfigureButton.addEventListener("click", () => {
      postJson("/api/mode/configure-camera", {})
        .then(() => {
          store.patch("ui.mode", "CONFIGURE_CAMERA");
          updateModeView("CONFIGURE_CAMERA");
          store.pushEvent("mode", "Switched to CONFIGURE_CAMERA");
          return refreshSnapshotOnce();
        })
        .catch(() => {
          store.pushEvent("mode", "Failed to switch to CONFIGURE_CAMERA");
        });
    });
  }

  store.pushEvent("app", "Frontend console initialized");
  loadInitialSnapshot().catch(() => {
    store.pushEvent("snapshot", "Initial snapshot failed");
  });
  connectEventStream();
  connectScoreStream();
  snapshotPollTimer = setInterval(() => {
    refreshSnapshotOnce().catch(() => {
      consecutiveSnapshotFailures += 1;
      if (consecutiveSnapshotFailures >= 3) {
        store.merge("connection", { backendReachable: false });
      }
    });
  }, 1000);
});
