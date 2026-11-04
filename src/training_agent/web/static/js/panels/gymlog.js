// Gym log: Garmin often misses strength sessions, so you can add them by hand.
import { el, fmtDay, fmtDuration } from "../util.js";
import { listGym, logGym, deleteGym, announceChange } from "../api.js";

function dayOptions() {
  const out = [];
  for (let back = 0; back <= 14; back++) {
    const d = new Date(); d.setDate(d.getDate() - back);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    out.push(el("option", { value: iso, text: back === 0 ? "Today" : back === 1 ? "Yesterday" : fmtDay(iso) }));
  }
  return out;
}

export default {
  id: "gymlog",
  title: "Gym log",
  render(sec) {
    sec.append(el("h2", { text: "Gym log" }));
    const msg = el("p", { class: "form-msg", role: "status" });
    const field = (label, control) => el("label", { class: "field" }, el("span", { text: label }), control);
    const day = el("select", {}, ...dayOptions());
    const kind = el("select", {}, ...[["full", "Full body"], ["upper", "Upper body"], ["lower", "Lower body"], ["other", "Other"]]
      .map(([v, t]) => el("option", { value: v, text: t })));
    const minutes = el("input", { type: "number", min: "5", max: "300", value: "50", inputmode: "numeric" });
    const effort = el("input", { type: "number", min: "1", max: "10", value: "5", inputmode: "numeric" });
    const submit = el("button", { type: "submit", class: "plan-btn" }, "Log session");
    const form = el("form", { class: "gym-form", onsubmit: async (e) => {
      e.preventDefault(); msg.textContent = ""; submit.setAttribute("disabled", "");
      try {
        await logGym({ day: day.value, kind: kind.value, minutes: Number(minutes.value), effort: Number(effort.value) });
        announceChange();
      } catch (err) { msg.textContent = err.message; submit.removeAttribute("disabled"); }
    } },
      field("When", day), field("Type", kind), field("Minutes", minutes), field("How hard (1-10)", effort), submit);
    sec.append(form, msg,
      el("p", { class: "muted small", text: "1 = very easy, 5 = a normal session, 10 = as hard as it gets. The rating scales the load estimate." }));

    const list = el("ul", { class: "plain gym-list" });
    sec.append(el("h3", { class: "mini", text: "Logged by hand (last 30 days)" }), list);
    listGym().then((rows) => {
      if (!rows.length) { list.append(el("li", { class: "muted small", text: "No entries yet." })); return; }
      rows.forEach((r) => list.append(el("li", {},
        el("span", { text: `${fmtDay(r.start)} · ${r.source_sport} · ${fmtDuration(r.duration_min)}` }),
        el("button", { class: "ghost small", "aria-label": `Delete the entry from ${fmtDay(r.start)}`,
          onclick: async () => { try { await deleteGym(r.id); announceChange(); } catch (err) { msg.textContent = err.message; } } }, "Delete"))));
    }).catch((err) => list.append(el("li", { class: "muted small", text: err.message })));
  },
};
