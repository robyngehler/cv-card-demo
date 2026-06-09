import { getJson, openUiEvents, postJson } from "./js/api.js";
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

    updateModeView(snapshot?.app?.mode || "RUN");
  }

  function connectEventStream() {
    eventSource = openUiEvents();

    eventSource.addEventListener("open", () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      store.merge("connection", {
        events: "CONNECTED",
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
      const nextAttempt = (store.state.connection.reconnectAttempt || 0) + 1;
      const delayMs = Math.min(10000, 400 * Math.pow(2, Math.min(nextAttempt, 5)));
      store.merge("connection", {
        events: "DISCONNECTED",
        reconnectAttempt: nextAttempt,
        backendReachable: false,
      });
      store.pushEvent("events", `SSE disconnected, reconnect in ${delayMs}ms`);
      reconnectTimer = setTimeout(connectEventStream, delayMs);
    });
  }

  async function loadInitialSnapshot() {
    const response = await getJson("/api/ui/snapshot");
    if (!response.ok || !response.data) {
      store.merge("connection", { backendReachable: false });
      return;
    }
    applySnapshot(response.data);
  }

  async function refreshSnapshotOnce() {
    const response = await getJson("/api/ui/snapshot");
    if (response.ok && response.data) {
      applySnapshot(response.data);
    }
  }

  store.subscribe((state) => {
    const ws = state.connection.events;
    const reachable = state.connection.backendReachable;
    connectionPill.textContent = `${ws}${reachable ? "" : " / API DOWN"}`;
  });

  if (modeRunButton) {
    modeRunButton.addEventListener("click", () => {
      postJson("/api/mode/run", {})
        .then(() => {
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
});
