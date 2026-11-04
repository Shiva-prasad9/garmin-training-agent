async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let message = `Server returned ${res.status}`;
    try {
      const detail = (await res.json()).detail;
      message = typeof detail === "string" ? detail : "Please check the values you entered.";
    } catch { /* keep the default message */ }
    throw new Error(message);
  }
  return res.json();
}

export const getOverview = (days) => request("GET", `/api/overview?days=${days}`);
export const getPlan = () => request("GET", "/api/plan");
export const choose = (intensity) => request("POST", "/api/plan/choose", { intensity });
export const clearChoice = () => request("POST", "/api/plan/clear");
export const getActivityLog = (kind, days) => request("GET", `/api/activity-log?kind=${kind}&days=${days}`);
export const getActivity = (id) => request("GET", `/api/activities/${encodeURI(id)}`);
export const listManual = () => request("GET", "/api/manual");
export const logManual = (entry) => request("POST", "/api/manual", entry);
export const deleteManual = (id) => request("DELETE", `/api/manual/${encodeURI(id)}`);

// Panels call this after a change so every panel redraws from fresh data.
export const announceChange = () => document.dispatchEvent(new CustomEvent("data-changed"));
