// This week: what the active plan asks for, what is done, what is still open, and what was dropped.
import { el } from "../util.js";

const word = (s) => (s.kind === s.sport || s.kind === "general" ? s.sport : `${s.sport} (${s.kind})`);

export default {
  id: "week",
  title: "This week",
  render(sec, data) {
    sec.append(el("h2", { text: "This week" }));
    const plan = data.plan && data.plan.plan;
    if (!plan) { sec.append(el("p", { class: "empty", text: "No plan yet." })); return; }
    sec.append(el("p", { class: "muted small", text: `Plan source: ${plan.week_source.replace("_", " ")}${plan.week_phase !== "template" ? ` · phase: ${plan.week_phase}` : ""}` }));
    sec.append(el("h3", { class: "mini", text: "Done so far" }));
    sec.append(plan.done_this_week.length
      ? el("ul", { class: "plain" }, ...plan.done_this_week.map((d) => el("li", { text: d })))
      : el("p", { class: "muted small", text: "Nothing recorded yet this week." }));
    sec.append(el("h3", { class: "mini", text: "Still open" }));
    sec.append(el("div", { class: "chips" }, ...(plan.remaining_slots.length
      ? plan.remaining_slots.map((s) => el("span", { class: "chip", text: word(s) }))
      : [el("span", { class: "muted small", text: "Nothing left." })])));
    if (plan.dropped_slots.length) {
      sec.append(el("h3", { class: "mini", text: "Dropped (the week is behind)" }));
      sec.append(el("div", { class: "chips" }, ...plan.dropped_slots.map((s) => el("span", { class: "chip flag", text: `✕ ${word(s)}` }))));
    }
  },
};
