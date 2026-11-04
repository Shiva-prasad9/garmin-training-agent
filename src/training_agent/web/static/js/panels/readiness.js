// Readiness: how hard today may be, as a four-step gauge. The reasons live in the plan's Details and on the Insights page.
import { el, svgEl } from "../util.js";
import { levelGauge } from "../charts.js";

const LEVELS = [
  { key: "rest", name: "Rest", color: "var(--lvl-rest)" },
  { key: "easy", name: "Easy", color: "var(--lvl-easy)" },
  { key: "moderate", name: "Moderate", color: "var(--lvl-moderate)" },
  { key: "hard", name: "Hard", color: "var(--lvl-hard)" },
];

export default {
  id: "readiness",
  title: "Readiness",
  render(sec, data) {
    sec.append(el("h2", { text: "Readiness" }));
    const plan = data.plan && data.plan.plan;
    if (!plan) { sec.append(el("p", { class: "empty", text: "No plan yet." })); return; }
    const capIdx = LEVELS.findIndex((l) => l.key === plan.cap), cap = LEVELS[capIdx];
    const host = el("div", { class: "gauge" });
    sec.append(host, el("div", { class: "gauge-read" }, el("div", { class: "k", text: "Allowed up to" }), el("div", { class: "big", text: cap.name })));
    levelGauge(host, { label: `Allowed intensity today: ${cap.name}. Suggested: ${plan.recommended}.`, pick: plan.recommended,
      levels: LEVELS.map((l, i) => ({ ...l, lit: i <= capIdx })) });
    if (plan.coach_note) {
      sec.append(el("div", { class: "coach" },
        el("div", { class: "coach-head" }, svgEl("svg", { viewBox: "0 0 24 24", class: "bolt", "aria-hidden": "true" }, svgEl("path", { d: "M13.5 2 4 13.5h6.2L9 22l10-12.2h-6.4z" })), el("b", { text: "Coach" })),
        el("p", { text: plan.coach_note })));
    }
  },
};
