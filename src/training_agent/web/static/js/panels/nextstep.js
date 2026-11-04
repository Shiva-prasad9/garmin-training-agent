// Next best step: the one most useful thing to do now, and why. Comes from the planner's insights (highest priority first).
import { el, svgEl } from "../util.js";

export const AREA = { recovery: "Recovery", sleep: "Sleep", load: "Training load", intensity: "Intensity", consistency: "Consistency", progress: "Progression" };

export function pickStep(plan) {
  const list = (plan && plan.insights) || [];
  return list.find((i) => i.status !== "good" && i.action) || list.find((i) => i.action) || null;
}

export default {
  id: "nextstep",
  title: "Next best step",
  render(sec, data) {
    const plan = data.plan && data.plan.plan;
    const step = pickStep(plan);
    if (!step) { sec.hidden = true; return; }
    const onTrack = step.status === "good";
    const rec = plan.options.find((o) => o.intensity === plan.recommended);
    sec.append(el("div", { class: "next" },
      el("div", { class: "next-main" },
        el("div", { class: "next-label" },
          svgEl("svg", { viewBox: "0 0 24 24", class: "bolt", "aria-hidden": "true" }, svgEl("path", { d: "M13.5 2 4 13.5h6.2L9 22l10-12.2h-6.4z" })),
          onTrack ? "You are on track" : "Your next best step", el("span", { class: "chip", text: AREA[step.area] || step.area })),
        el("div", { class: "next-action", text: step.action }),
        el("p", { class: "next-why" }, el("b", { text: "Why: " }), step.headline),
        el("p", { class: "muted small", text: step.meaning })),
      el("div", { class: "next-side" },
        el("div", { class: "k", text: "Today's session" }),
        el("div", { class: "v", text: rec ? rec.title : plan.recommended }),
        el("div", { class: "muted small", text: `Allowed up to ${plan.cap}` }))));
  },
};
