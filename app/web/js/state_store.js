const MAX_TIMELINE_ITEMS = 80;

export function createStateStore() {
  const listeners = new Set();

  const state = {
    ui: {
      activeTab: "questionnaire",
      debugFps: 5,
    },
    connection: {
      scoreWs: "CONNECTING",
      lastScoreAt: null,
      backendReachable: false,
      reconnectAttempt: 0,
    },
    app: {
      name: "cv-card-demo",
      version: "0.1.0",
      state: "BOOT",
      substate: null,
    },
    session: {
      session_id: null,
      candidate_id: null,
      identity_status: "UNKNOWN",
      current_question_id: null,
      phase: "WAIT_FOR_MOVEMENT",
      completed: false,
      question_index: 0,
    },
    score: {
      visible: false,
      score: null,
      rating: null,
      source: "idle",
      fusion_state: "NO_TARGET",
      question_label: "Place a business card to begin",
      question_min_label: "0",
      question_max_label: "10",
      countdown_remaining_s: null,
      message: "System starting...",
      confidence: 0,
      candidates_count: 0,
      question_phase: "WAIT_FOR_MOVEMENT",
    },
    health: {
      status: "UNKNOWN",
      services: {},
    },
    runtime: {
      card: {},
      hand: {},
      tracking: {},
    },
    camera: {
      settings: {},
      capabilities: {},
      last_error: null,
      lastApplyResult: null,
    },
    debugFrame: {
      src: "",
      ageLabel: "no frame",
      available: false,
      lastLoadedAt: null,
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
    subscribe,
    pushEvent,
  };
}
