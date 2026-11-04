// This week: how many planned sessions are done, and what is still open.
import { el } from "../util.js";
import { ring } from "../charts.js";

const word = (s) => (s.kind === s.sport || s.kind === "general" ? s.sport : `${s.sport} (${s.kind})`);

export default {
  id: "week",
  title: "This week",
  render(sec, data) {
    sec.append(el("h2", { text: "This week" }));
    const plan = data.plan && data.plan.plan;
    if (!plan) { sec.append(el("p", { class: "empty", text: "No plan yet." })); return; }
    const done = plan.done_this_week.length, open = plan.remaining_slots.length, total = done + open;
    const host = el("div", { class: "ring" });
    sec.append(host);
    ring(host, { fraction: total ? done / total : 0, center: `${done}/${total}`, sub: "sessions", color: "var(--accent-mark)", label: `${done} of ${total} sessions done this week` });
    if (open) sec.append(el("div", { class: "chips center" }, ...plan.remaining_slots.map((s) => el("span", { class: "chip", text: word(s) }))));
    if (plan.dropped_slots.length) sec.append(el("div", { class: "chips center dropped" }, ...plan.dropped_slots.map((s) => el("span", { class: "chip flag", text: `✕ ${word(s)}` }))));
  },
};
