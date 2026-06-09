export function initDiagnosticsView(store) {
  const button = document.getElementById("toggle-diagnostics");
  const drawer = document.getElementById("diagnostics-drawer");
  const summary = document.getElementById("diagnostics-summary");
  const timeline = document.getElementById("diagnostics-timeline");
  const jsonBox = document.getElementById("diagnostics-json");

  if (button) {
    button.addEventListener("click", () => {
      store.patch("ui.diagnosticsOpen", !store.state.ui.diagnosticsOpen);
    });
  }

  store.subscribe((state) => {
    const open = Boolean(state.ui.diagnosticsOpen);
    if (drawer) {
      drawer.classList.toggle("hidden", !open);
    }

    const snapshot = state.snapshot || {};
    const services = snapshot.services || {};

    if (summary) {
      summary.innerHTML = "";
      Object.keys(services).forEach((key) => {
        const item = document.createElement("div");
        item.className = "diag-chip";
        item.textContent = `${key}: ${services[key]}`;
        summary.appendChild(item);
      });
    }

    if (timeline) {
      timeline.innerHTML = "";
      state.timeline.slice(0, 20).forEach((entry) => {
        const li = document.createElement("li");
        li.textContent = `${entry.timestamp} | ${entry.type} | ${entry.message}`;
        timeline.appendChild(li);
      });
    }

    if (jsonBox) {
      jsonBox.textContent = JSON.stringify(snapshot, null, 2);
    }
  });
}
