function toNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function frameAgeMs(snapshot) {
  const nowMs = Date.now();
  const frameTs = toNumber(snapshot?.camera?.last_frame_ts);
  if (frameTs === null) {
    return null;
  }
  return Math.max(0, Math.round(nowMs - frameTs * 1000));
}

export function initLiveView(store) {
  const runImage = document.getElementById("run-live-image");
  const configureImage = document.getElementById("configure-live-image");
  const runAge = document.getElementById("run-frame-age");
  const configureAge = document.getElementById("configure-frame-age");
  let timer = null;
  let runBlobUrl = "";
  let configureBlobUrl = "";
  let currentMode = "RUN";

  async function fetchFrame(mode) {
    const target = mode === "CONFIGURE_CAMERA" ? configureImage : runImage;
    if (!target) {
      return;
    }

    const response = await fetch(`/api/live-frame?mode=${mode === "CONFIGURE_CAMERA" ? "configure" : "run"}&ts=${Date.now()}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return;
    }

    const blob = await response.blob();
    const nextUrl = URL.createObjectURL(blob);

    if (mode === "CONFIGURE_CAMERA") {
      if (configureBlobUrl) {
        URL.revokeObjectURL(configureBlobUrl);
      }
      configureBlobUrl = nextUrl;
      target.src = configureBlobUrl;
    } else {
      if (runBlobUrl) {
        URL.revokeObjectURL(runBlobUrl);
      }
      runBlobUrl = nextUrl;
      target.src = runBlobUrl;
    }
  }

  function startPolling() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    const fps = currentMode === "CONFIGURE_CAMERA" ? 3 : 4;
    timer = setInterval(() => {
      fetchFrame(currentMode).catch(() => {
        // Keep polling even if one fetch fails.
      });
    }, Math.round(1000 / fps));
    fetchFrame(currentMode).catch(() => {
      // first frame best-effort
    });
  }

  startPolling();

  store.subscribe((state) => {
    const snapshot = state.snapshot;
    const mode = snapshot?.app?.mode || "RUN";
    if (mode !== currentMode) {
      currentMode = mode;
      startPolling();
    }

    const ageMs = frameAgeMs(snapshot);
    const stale = ageMs !== null && ageMs > 300;
    const ageLabel = ageMs === null ? "no frame" : `${ageMs} ms`;

    if (runAge) {
      runAge.textContent = ageLabel;
      runAge.classList.toggle("stale", stale);
    }

    if (configureAge) {
      configureAge.textContent = ageLabel;
      configureAge.classList.toggle("stale", stale);
    }
  });
}
