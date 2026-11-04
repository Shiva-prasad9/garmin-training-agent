// Insights: what your own data says, in plain words, and what to do about it.
import { el } from "../util.js";
import { AREA, pickStep } from "./nextstep.js";

// Status always carries an icon and words, never colour alone.
const STATUS = { act: { icon: "▲", label: "Needs action" }, watch: { icon: "●", label: "Keep an eye on it" }, good: { icon: "✓", label: "On track" } };

export default {
  id: "insights",
  title: "Insights",
  render(sec, data) {
    const plan = data.plan && data.plan.plan;
    const list = (plan && plan.insights) || [];
    if (!list.length) { sec.hidden = true; return; }
    const top = pickStep(plan);
    sec.append(el("h2", { text: "Insights from your last weeks" }));
    sec.append(el("div", { class: "insight-grid" }, ...list.map((i) => {
      const st = STATUS[i.status] || STATUS.watch;
      return el("article", { class: `insight ${i.status}${top && top.id === i.id ? " top" : ""}` },
        el("div", { class: "insight-head" }, el("span", { class: `pill ${i.status}`, text: `${st.icon} ${st.label}` }), el("span", { class: "muted small", text: AREA[i.area] || i.area })),
        el("h3", { text: i.headline }),
        el("p", { class: "muted small", text: i.meaning }),
        i.action ? el("p", { class: "do" }, el("b", { text: "Do this: " }), i.action) : null,
        i.evidence && i.evidence.length ? el("details", { class: "more" }, el("summary", { text: "The numbers" }), el("ul", { class: "plain" }, ...i.evidence.map((e) => el("li", { text: e })))) : null);
    })));
  },
};
