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
export const listGym = () => request("GET", "/api/gym");
export const logGym = (entry) => request("POST", "/api/gym", entry);
export const deleteGym = (id) => request("DELETE", `/api/gym/${encodeURI(id)}`);

// Panels call this after a change so every panel redraws from fresh data.
export const announceChange = () => document.dispatchEvent(new CustomEvent("data-changed"));
