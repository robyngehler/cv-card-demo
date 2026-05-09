const MAX_TIMELINE_ITEMS = 80;

export function createStateStore() {
  const listeners = new Set();

  const state = {
    ui: {
      diagnosticsOpen: false,
      mode: "RUN",
    },
    connection: {
      events: "CONNECTING",
      score: "CONNECTING",
      lastEventAt: null,
      backendReachable: false,
      reconnectAttempt: 0,
    },
    lastSnapshotTimestamp: 0,
    snapshot: null,
    camera: {
      settings: {},
      capabilities: {},
      last_error: null,
      lastApplyResult: null,
    },
    timeline: [],
  };

  function notify() {
    for (const listener of listeners) {
      listener(state);
    }
  }

  function patch(path, value) {
    const segments = path.split(".");
    let cursor = state;
    for (let i = 0; i < segments.length - 1; i += 1) {
      const segment = segments[i];
      if (!Object.prototype.hasOwnProperty.call(cursor, segment) || cursor[segment] === null) {
        cursor[segment] = {};
      }
      cursor = cursor[segment];
    }
    cursor[segments[segments.length - 1]] = value;
    notify();
  }

  function merge(path, partialValue) {
    const segments = path.split(".");
    let cursor = state;
    for (let i = 0; i < segments.length - 1; i += 1) {
      const segment = segments[i];
      if (!Object.prototype.hasOwnProperty.call(cursor, segment) || cursor[segment] === null) {
        cursor[segment] = {};
      }
      cursor = cursor[segment];
    }
    const leaf = segments[segments.length - 1];
    cursor[leaf] = {
      ...(cursor[leaf] || {}),
      ...(partialValue || {}),
    };
    notify();
  }

  function pushEvent(type, message) {
    const timestamp = new Date().toISOString();
    state.timeline.unshift({ timestamp, type, message });
    if (state.timeline.length > MAX_TIMELINE_ITEMS) {
      state.timeline.length = MAX_TIMELINE_ITEMS;
    }
    notify();
  }

  function subscribe(listener) {
    listeners.add(listener);
    listener(state);
    return () => listeners.delete(listener);
  }

  return {
    state,
    patch,
    merge,
    setSnapshot(snapshot) {
      const timestamp = Number(snapshot?.timestamp || 0);
      if (!Number.isFinite(timestamp) || timestamp <= state.lastSnapshotTimestamp) {
        return false;
      }
      state.snapshot = snapshot;
      state.lastSnapshotTimestamp = timestamp;
      state.ui.mode = snapshot?.app?.mode || state.ui.mode || "RUN";
      state.connection.lastEventAt = new Date().toISOString();
      notify();
      return true;
    },
    subscribe,
    pushEvent,
  };
}
