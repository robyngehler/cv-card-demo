import { getJson } from "./api.js";

const CONTROL_ORDER = [
  "exposure",
  "focus",
  "sharpness",
  "brightness",
  "contrast",
  "saturation",
  "gain",
  "white_balance",
];

const AUTO_TOGGLE_MAP = {
  exposure: "auto_exposure",
  focus: "auto_focus",
  white_balance: "auto_white_balance",
};

function capitalize(value) {
  return value.replaceAll("_", " ").replace(/(^|\s)\S/g, (s) => s.toUpperCase());
}

function buildRangeInput(key, setting) {
  const container = document.createElement("div");
  container.className = "control-item";

  const label = document.createElement("label");
  label.setAttribute("for", `control-${key}`);
  label.textContent = capitalize(key);

  const valueLabel = document.createElement("span");
  valueLabel.id = `control-${key}-value`;
  valueLabel.textContent = setting.value === null || setting.value === undefined ? "--" : String(Math.round(Number(setting.value) * 100) / 100);
  label.appendChild(valueLabel);

  const input = document.createElement("input");
  input.type = "range";
  input.id = `control-${key}`;
  input.name = key;
  input.min = String(setting.min ?? 0);
  input.max = String(setting.max ?? 100);
  input.step = String(setting.step ?? 1);
  input.value = String(setting.value ?? setting.min ?? 0);
  input.disabled = !setting.supported;

  input.addEventListener("input", () => {
    valueLabel.textContent = input.value;
  });

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = setting.supported
    ? `range ${input.min}..${input.max}`
    : "Not supported by current camera backend";

  container.appendChild(label);
  container.appendChild(input);
  container.appendChild(meta);

  if (setting.auto_supported && AUTO_TOGGLE_MAP[key]) {
    const toggleLabel = document.createElement("label");
    toggleLabel.className = "meta";
    const toggle = document.createElement("input");
    toggle.type = "checkbox";
    toggle.name = AUTO_TOGGLE_MAP[key];
    toggle.checked = Boolean(setting.auto);
    toggle.disabled = !setting.supported;
    toggleLabel.appendChild(toggle);
    toggleLabel.appendChild(document.createTextNode(` ${capitalize(AUTO_TOGGLE_MAP[key])}`));
    container.appendChild(toggleLabel);
  }

  return container;
}

export function initControlView(store) {
  const formNode = document.getElementById("camera-form");
  const refreshButton = document.getElementById("refresh-controls");
  const applyButton = document.getElementById("apply-controls");
  const restartButton = document.getElementById("restart-camera");
  const resultNode = document.getElementById("control-result");
  const fpsRange = document.getElementById("debug-fps");
  const fpsValue = document.getElementById("debug-fps-value");

  function readFormPayload() {
    const payload = {};
    const rangeInputs = formNode.querySelectorAll("input[type='range']");
    rangeInputs.forEach((input) => {
      if (input.disabled) {
        return;
      }
      payload[input.name] = Number(input.value);
    });

    const boolInputs = formNode.querySelectorAll("input[type='checkbox']");
    boolInputs.forEach((input) => {
      if (input.disabled) {
        return;
      }
      payload[input.name] = input.checked;
    });

    return payload;
  }

  function renderSettings(settings) {
    formNode.innerHTML = "";
    CONTROL_ORDER.forEach((key) => {
      if (!settings[key]) {
        return;
      }
      formNode.appendChild(buildRangeInput(key, settings[key]));
    });
  }

  async function refreshSettings() {
    const response = await getJson("/api/camera/settings");
    if (!response.ok || !response.data) {
      resultNode.textContent = `Failed to load settings (${response.status})`;
      store.pushEvent("control", `Camera settings load failed (${response.status})`);
      return;
    }

    store.merge("camera", {
      settings: response.data.settings || {},
      capabilities: response.data.settings || {},
      last_error: response.data.last_error || null,
    });
    renderSettings(response.data.settings || {});
    resultNode.textContent = `Camera settings loaded (${response.data.status || "OK"})`;
    store.pushEvent("control", "Camera settings refreshed");
  }

  async function applySettings() {
    const payload = readFormPayload();
    const response = await getJson("/api/camera/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.data) {
      resultNode.textContent = `Apply failed (${response.status})`;
      store.pushEvent("control", `Apply failed (${response.status})`);
      return;
    }

    store.merge("camera", {
      lastApplyResult: response.data,
      last_error: response.data.last_error || null,
    });

    const rejectedKeys = Object.keys(response.data.rejected || {});
    if (rejectedKeys.length) {
      resultNode.textContent = `Partial apply: rejected ${rejectedKeys.join(", ")}`;
      store.pushEvent("control", `Partial apply, rejected ${rejectedKeys.join(", ")}`);
    } else {
      resultNode.textContent = "Settings applied successfully";
      store.pushEvent("control", "Settings applied successfully");
    }
  }

  async function restartCamera() {
    const response = await getJson("/api/camera/restart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    if (!response.data) {
      resultNode.textContent = `Restart failed (${response.status})`;
      store.pushEvent("control", `Camera restart failed (${response.status})`);
      return;
    }

    resultNode.textContent = response.data.status === "OK"
      ? "Camera restarted"
      : `Restart error: ${response.data.last_error || "unknown"}`;
    store.pushEvent("control", `Camera restart -> ${response.data.status}`);
    refreshSettings().catch(() => {
      store.pushEvent("control", "Refresh after restart failed");
    });
  }

  refreshButton.addEventListener("click", () => {
    refreshSettings().catch(() => {
      resultNode.textContent = "Failed to refresh camera settings";
    });
  });

  applyButton.addEventListener("click", () => {
    applySettings().catch(() => {
      resultNode.textContent = "Failed to apply camera settings";
    });
  });

  restartButton.addEventListener("click", () => {
    restartCamera().catch(() => {
      resultNode.textContent = "Failed to restart camera";
    });
  });

  fpsRange.addEventListener("input", () => {
    const fps = Number(fpsRange.value || 5);
    fpsValue.textContent = `${fps} Hz`;
    store.patch("ui.debugFps", fps);
  });

  store.subscribe((state) => {
    fpsValue.textContent = `${state.ui.debugFps} Hz`;
    fpsRange.value = String(state.ui.debugFps);
  });

  refreshSettings().catch(() => {
    resultNode.textContent = "Camera settings unavailable";
  });
}
