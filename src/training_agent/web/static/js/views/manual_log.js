// Log an activity by hand: pick the activity from a drop-down. Garmin misses some sessions (strength especially).
import { el, fmtDay, fmtDuration, prettify } from "../util.js";
import { deleteManual, listManual, logManual, announceChange } from "../api.js";

const CHOICES = [["gym", "Strength training"], ["run", "Running"], ["bike", "Cycling"], ["swim", "Swimming"], ["hike", "Hiking"], ["walk", "Walking"], ["other", "Other"]];
const GYM_KINDS = [["full", "Full body"], ["upper", "Upper body"], ["lower", "Lower body"], ["other", "Other"]];
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export function manualLog(preselect = "gym") {
  const today = new Date(), oldest = new Date(); oldest.setDate(oldest.getDate() - 90);
  const msg = el("p", { class: "form-msg", role: "status" });
  const field = (label, control, id) => el("label", { class: "field", ...(id ? { id } : {}) }, el("span", { text: label }), control);
  const sport = el("select", {}, ...CHOICES.map(([v, t]) => el("option", { value: v, text: t, ...(v === preselect ? { selected: "" } : {}) })));
  const kind = el("select", {}, ...GYM_KINDS.map(([v, t]) => el("option", { value: v, text: t })));
  const day = el("input", { type: "date", value: iso(today), min: iso(oldest), max: iso(today) });
  const minutes = el("input", { type: "number", min: "5", max: "720", value: "50", inputmode: "numeric" });
  const distance = el("input", { type: "number", min: "0", max: "1000", step: "0.1", placeholder: "optional", inputmode: "decimal" });
  const effort = el("input", { type: "number", min: "1", max: "10", value: "5", inputmode: "numeric" });
  const submit = el("button", { type: "submit", class: "plan-btn" }, "Log it");
  const kindField = field("Type", kind), distField = field("Distance (km)", distance);
  const sync = () => { kindField.hidden = sport.value !== "gym"; distField.hidden = sport.value === "gym"; };
  sport.addEventListener("change", sync); sync();

  const form = el("form", { class: "gym-form", onsubmit: async (e) => {
    e.preventDefault(); msg.textContent = ""; submit.setAttribute("disabled", "");
    const entry = { sport: sport.value, day: day.value, minutes: Number(minutes.value), effort: Number(effort.value) };
    if (sport.value === "gym") entry.kind = kind.value;
    else if (distance.value) entry.distance_km = Number(distance.value);
    try { await logManual(entry); announceChange(); } catch (err) { msg.textContent = err.message; submit.removeAttribute("disabled"); }
  } }, field("Activity", sport), kindField, field("When", day), field("Minutes", minutes), distField, field("How hard (1-10)", effort), submit);

  const list = el("ul", { class: "plain gym-list" });
  listManual().then((rows) => {
    if (!rows.length) return;
    rows.forEach((r) => list.append(el("li", {},
      el("span", { text: `${fmtDay(r.start)} · ${prettify(r.source_sport)} · ${fmtDuration(r.duration_min)}${r.distance_km ? ` · ${r.distance_km} km` : ""}` }),
      el("button", { class: "ghost small", "aria-label": `Delete the entry from ${fmtDay(r.start)}`,
        onclick: async () => { try { await deleteManual(r.id); announceChange(); } catch (err) { msg.textContent = err.message; } } }, "Delete"))));
  }).catch((err) => { msg.textContent = err.message; });

  return el("details", { class: "manual" }, el("summary", { text: "+ Log an activity by hand" }), form, msg,
    el("p", { class: "muted small", text: "1 = very easy, 5 = normal, 10 = as hard as it gets." }), list);
}
