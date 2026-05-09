export async function getJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    data = await response.json();
  }
  return { ok: response.ok, status: response.status, data };
}

export async function postJson(url, payload = {}) {
  return getJson(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload || {}),
  });
}

export function openUiEvents() {
  return new EventSource("/api/ui/events");
}

export function openScoreSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${protocol}://${window.location.host}/ws/score`);
}
