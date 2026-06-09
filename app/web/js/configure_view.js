import { getJson, postJson } from "./api.js";

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

const EPSILON = 1e-6;

function textForResult(payload) {
  if (!payload) {
    return "No command sent yet.";
  }
  const status = payload.status || "UNKNOWN";
  const applied = payload.applied ? Object.keys(payload.applied).length : 0;
  const rejected = payload.rejected ? Object.keys(payload.rejected).length : 0;
  const err = payload.last_error ? ` | ${payload.last_error}` : "";
  return `Status ${status} | Applied ${applied} | Rejected ${rejected}${err}`;
}

function buildControlItem(key, descriptor) {
  const wrapper = document.createElement("div");
  wrapper.className = "control-row";

  const top = document.createElement("div");
  top.className = "control-row-top";

  const title = document.createElement("span");
  title.textContent = key;

  const value = document.createElement("span");
  value.textContent = descriptor.value ?? "--";

  top.appendChild(title);
  top.appendChild(value);

  const input = document.createElement("input");
  input.type = "range";
  input.min = descriptor.min ?? 0;
  input.max = descriptor.max ?? 100;
  input.step = descriptor.step ?? 1;
  input.value = descriptor.value ?? descriptor.min ?? 0;
  input.disabled = !descriptor.supported;
  input.dataset.key = key;

  input.addEventListener("input", () => {
    value.textContent = input.value;
  });

  const foot = document.createElement("div");
  foot.className = "control-row-foot";
  foot.textContent = descriptor.supported
    ? `${descriptor.min}..${descriptor.max}`
    : "not supported by active backend";

  wrapper.appendChild(top);
  wrapper.appendChild(input);
  wrapper.appendChild(foot);
  return {
    wrapper,
    input,
    value,
    foot,
  };
}

function toNumber(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function almostEqual(a, b, step = 1) {
  if (a === null || b === null) {
    return false;
  }
  const tolerance = Math.max(EPSILON, Math.abs(step || 1) / 2);
  return Math.abs(a - b) <= tolerance;
}

function clamp(value, min, max) {
  if (value === null) {
    return null;
  }
  if (min !== null && value < min) {
    return min;
  }
  if (max !== null && value > max) {
    return max;
  }
  return value;
}

export function initConfigureView(store) {
  const controlsRoot = document.getElementById("camera-controls");
  const resultLine = document.getElementById("configure-result");
  const applyButton = document.getElementById("apply-camera-settings");
  const refreshButton = document.getElementById("refresh-camera-settings");
  const restartButton = document.getElementById("restart-camera");
  const controlsState = {
    byKey: {},
    backendValues: {},
    draftValues: {},
    meta: {},
  };

  async function loadControls() {
    const response = await getJson("/api/camera/settings");
    if (!response.ok || !response.data) {
      if (resultLine) {
        resultLine.textContent = "Failed to load camera settings";
      }
      return;
    }

    const settings = response.data.settings || {};
    store.merge("camera", {
      settings,
      capabilities: settings,
      last_error: response.data.last_error || null,
    });

    if (!controlsRoot) {
      return;
    }

    controlsRoot.innerHTML = "";
    controlsState.byKey = {};
    controlsState.meta = {};

    CONTROL_ORDER.forEach((key) => {
      if (!Object.prototype.hasOwnProperty.call(settings, key)) {
        return;
      }
      const descriptor = settings[key] || {};
      const field = buildControlItem(key, descriptor);
      const min = toNumber(descriptor.min, 0);
      const max = toNumber(descriptor.max, 100);
      const step = toNumber(descriptor.step, 1);
      const backendValue = toNumber(descriptor.value, min);
      const oldDraft = toNumber(controlsState.draftValues[key], null);
      const nextValue = clamp(oldDraft !== null ? oldDraft : backendValue, min, max);

      controlsState.backendValues[key] = backendValue;
      controlsState.draftValues[key] = nextValue;
      controlsState.meta[key] = { min, max, step, supported: Boolean(descriptor.supported) };

      field.input.value = String(nextValue ?? min);
      field.value.textContent = field.input.value;
      field.foot.textContent = descriptor.supported
        ? `${min}..${max}`
        : "not supported by active backend";

      field.input.addEventListener("input", () => {
        const v = toNumber(field.input.value, null);
        controlsState.draftValues[key] = v;
        field.value.textContent = field.input.value;
      });

      controlsState.byKey[key] = field;
      controlsRoot.appendChild(field.wrapper);
    });

    if (resultLine) {
      resultLine.textContent = `Settings loaded (${response.data.status || "UNKNOWN"})`;
    }
  }

  async function applySettings() {
    if (!controlsRoot) {
      return;
    }
    const payload = {};
    Object.keys(controlsState.byKey).forEach((key) => {
      const field = controlsState.byKey[key];
      const meta = controlsState.meta[key] || {};
      if (!field || field.input.disabled || !meta.supported) {
        return;
      }
      const draft = toNumber(controlsState.draftValues[key], null);
      const backend = toNumber(controlsState.backendValues[key], null);
      if (almostEqual(draft, backend, meta.step)) {
        return;
      }
      payload[key] = draft;
    });

    if (Object.keys(payload).length === 0) {
      if (resultLine) {
        resultLine.textContent = "No changed values to apply.";
      }
      return;
    }

    const response = await postJson("/api/camera/settings", payload);
    const data = response.data || { status: "ERROR", last_error: "request_failed" };
    store.merge("camera", { lastApplyResult: data, last_error: data.last_error || null });
    if (resultLine) {
      resultLine.textContent = textForResult(data);
    }

    const appliedValues = data.applied_values || {};
    Object.keys(appliedValues).forEach((key) => {
      const newValue = toNumber(appliedValues[key], null);
      if (newValue !== null) {
        controlsState.draftValues[key] = newValue;
      }
    });

    await loadControls();
  }

  async function restartCamera() {
    const response = await postJson("/api/camera/restart", {});
    const data = response.data || { status: "ERROR", last_error: "request_failed" };
    if (resultLine) {
      resultLine.textContent = `Restart ${data.status || "ERROR"}${data.last_error ? ` | ${data.last_error}` : ""}`;
    }
    await loadControls();
  }

  if (applyButton) {
    applyButton.addEventListener("click", () => {
      applySettings().catch(() => {
        if (resultLine) {
          resultLine.textContent = "Failed to apply settings";
        }
      });
    });
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", () => {
      loadControls().catch(() => {
        if (resultLine) {
          resultLine.textContent = "Failed to refresh settings";
        }
      });
    });
  }

  if (restartButton) {
    restartButton.addEventListener("click", () => {
      restartCamera().catch(() => {
        if (resultLine) {
          resultLine.textContent = "Failed to restart camera";
        }
      });
    });
  }

  loadControls().catch(() => {
    if (resultLine) {
      resultLine.textContent = "Failed to load camera settings";
    }
  });
}
