import { getJson } from "./api.js";

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  if (typeof value === "number") {
    if (Number.isInteger(value)) {
      return String(value);
    }
    return value.toFixed(3);
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function initDebugView(store) {
  const frameImage = document.getElementById("debug-frame");
  const framePlaceholder = document.getElementById("debug-frame-placeholder");
  const frameAge = document.getElementById("debug-frame-age");
  const runtimeKv = document.getElementById("runtime-kv");
  const timelineNode = document.getElementById("timeline");

  let debugTimer = null;
  let frameTimestamp = null;

  function renderTimeline(state) {
    timelineNode.innerHTML = "";
    state.timeline.slice(0, 30).forEach((item) => {
      const li = document.createElement("li");
      const shortTs = item.timestamp.split("T")[1]?.replace("Z", "") || item.timestamp;
      li.textContent = `${shortTs} [${item.type}] ${item.message}`;
      timelineNode.appendChild(li);
    });
  }

  function renderRuntime(state) {
    const rows = [
      ["state", state.app.state],
      ["substate", state.app.substate],
      ["session_id", state.session.session_id],
      ["candidate_id", state.session.candidate_id],
      ["identity_status", state.session.identity_status],
      ["question_id", state.session.current_question_id],
      ["question_phase", state.score.question_phase || state.session.phase],
      ["visible", state.score.visible],
      ["score", state.score.score],
      ["rating", state.score.rating],
      ["source", state.score.source],
      ["fusion_state", state.score.fusion_state],
      ["detector_confidence", state.score.confidence],
      ["card_x_norm", state.runtime.card.x_normalized],
      ["card_bbox", state.runtime.card.bbox_points],
      ["hand_proxy_norm", {
        x: state.runtime.hand.proxy_x_normalized,
        y: state.runtime.hand.proxy_y_normalized,
      }],
      ["hand_landmarks", state.runtime.hand.landmark_count],
      ["hand_confidence", state.runtime.hand.confidence],
      ["snapshot_pending", state.health.services?.snapshot_processing?.status],
      ["ocr_status", state.health.services?.ocr?.status],
      ["vector_status", state.health.services?.vector?.status],
      ["persistence_status", state.health.services?.persistence?.status],
    ];

    runtimeKv.innerHTML = "";
    rows.forEach(([key, value]) => {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = formatValue(value);
      runtimeKv.appendChild(dt);
      runtimeKv.appendChild(dd);
    });
  }

  async function refreshDebugFrame() {
    const response = await fetch(`/api/debug-frame?ts=${Date.now()}`);
    if (response.status === 204) {
      frameImage.removeAttribute("src");
      framePlaceholder.classList.remove("hidden");
      frameAge.textContent = "no frame";
      store.merge("debugFrame", { available: false, ageLabel: "no frame", src: "" });
      return;
    }

    if (!response.ok) {
      frameAge.textContent = `error ${response.status}`;
      store.pushEvent("debug", `Debug frame endpoint error ${response.status}`);
      return;
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    frameImage.src = objectUrl;
    framePlaceholder.classList.add("hidden");
    frameTimestamp = Date.now();
    frameAge.textContent = "fresh";
    store.merge("debugFrame", {
      available: true,
      src: objectUrl,
      ageLabel: "fresh",
      lastLoadedAt: frameTimestamp,
    });
  }

  function syncDebugTimer(state) {
    const shouldRun = state.ui.activeTab === "debug";
    const fps = Math.max(1, Number(state.ui.debugFps || 5));
    const intervalMs = Math.round(1000 / fps);

    if (!shouldRun) {
      if (debugTimer) {
        clearInterval(debugTimer);
        debugTimer = null;
      }
      return;
    }

    if (debugTimer) {
      clearInterval(debugTimer);
      debugTimer = null;
    }

    refreshDebugFrame().catch(() => {
      store.pushEvent("debug", "Debug frame refresh failed");
    });
    debugTimer = setInterval(() => {
      refreshDebugFrame().catch(() => {
        store.pushEvent("debug", "Debug frame refresh failed");
      });
    }, intervalMs);
  }

  setInterval(() => {
    if (!frameTimestamp) {
      return;
    }
    const ageSeconds = Math.max(0, (Date.now() - frameTimestamp) / 1000);
    frameAge.textContent = `${ageSeconds.toFixed(1)}s ago`;
  }, 300);

  store.subscribe((state) => {
    renderRuntime(state);
    renderTimeline(state);
    syncDebugTimer(state);
  });

  getJson("/api/debug-frame").catch(() => {
    store.pushEvent("debug", "Initial debug frame probe failed");
  });
}
