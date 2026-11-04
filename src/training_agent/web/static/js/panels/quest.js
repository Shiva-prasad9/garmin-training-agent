// Daily quest: the planner's recommendation, an option for every intensity, and your choice.
import { el, fmtDay, fmtDuration, fmtNum } from "../util.js";
import { choose, clearChoice, announceChange } from "../api.js";

const LEVEL_WORDS = { rest: "Rest", easy: "Easy", moderate: "Moderate", hard: "Hard" };
// Risk labels always carry an icon and words, never colour alone. Every option can be chosen.
const RISK = {
  recommended: { icon: "★", label: "Recommended", cls: "good" },
  ok: { icon: "✓", label: "Fine to choose", cls: "good" },
  caution: { icon: "▲", label: "Caution: above what your signals allow", cls: "warn" },
  not_advised: { icon: "!", label: "Not advised", cls: "crit" },
};

function pace(minPerKm) {
  const m = Math.floor(minPerKm), s = Math.round((minPerKm - m) * 60);
  return `${m}:${String(s).padStart(2, "0")} /km`;
}

function targetLines(p) {
  if (!p) return [];
  const lines = [];
  if (p.duration_min) lines.push(["Time", fmtDuration(p.duration_min)]);
  if (p.distance_km) lines.push(["Distance", `${fmtNum(p.distance_km, 1)} km`]);
  if (p.pace_min_per_km) lines.push(["Pace", pace(p.pace_min_per_km)]);
  if (p.speed_kmh) lines.push(["Speed", `${fmtNum(p.speed_kmh, 1)} km/h`]);
  if (p.elevation_gain_m) lines.push(["Climbing", `about ${fmtNum(p.elevation_gain_m)} m`]);
  if (p.hr_low) lines.push(["Heart rate", `${p.hr_low}-${p.hr_high} bpm`]);
  return lines;
}

function card(option, chosen, busy, act) {
  const risk = RISK[option.risk] || RISK.ok;
  const selected = chosen && chosen.intensity === option.intensity;
  const lines = targetLines(option.prescription);
  const button = el("button", {
    class: `plan-btn${selected ? " done" : ""}`, disabled: busy || selected ? "" : null,
    "aria-label": `${selected ? "Planned" : "Plan"}: ${option.title}`,
    onclick: () => act(() => choose(option.intensity)),
  }, selected ? "✓ Planned" : "Plan this");
  if (busy || selected) button.setAttribute("disabled", ""); else button.removeAttribute("disabled");
  return el("div", { class: `opt ${option.risk}${selected ? " selected" : ""}` },
    el("div", { class: "opt-level", text: LEVEL_WORDS[option.intensity] }),
    el("div", { class: `badge ${risk.cls}` }, `${risk.icon} ${risk.label}`),
    el("h3", { text: option.title }),
    lines.length ? el("dl", { class: "targets" }, ...lines.map(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })])) : null,
    option.prescription && option.prescription.note ? el("p", { class: "muted small", text: option.prescription.note }) : null,
    option.reasons.length ? el("ul", { class: "why" }, ...option.reasons.map((r) => el("li", { text: r }))) : null,
    option.tomorrow ? el("p", { class: "tomorrow" }, el("b", { text: "Tomorrow: " }), option.tomorrow.replace(/^Tomorrow /, "")) : null,
    button);
}

export default {
  id: "quest",
  title: "Daily quest",
  render(sec, data) {
    sec.append(el("h2", { text: "Daily quest" }));
    const plan = data.plan && data.plan.plan;
    if (!plan) {
      sec.append(el("p", { class: "empty", text: data.plan && data.plan.error ? `The planner is not available: ${data.plan.error}` : "The planner is not available." }));
      return;
    }
    const chosen = (data.plan.chosen || [])[0] || null;
    const message = el("p", { class: "form-msg", role: "status" });
    let busy = false;
    const act = async (call) => {
      if (busy) return;
      busy = true; message.textContent = "";
      sec.querySelectorAll(".plan-btn").forEach((b) => b.setAttribute("disabled", ""));
      try { await call(); announceChange(); }
      catch (err) { message.textContent = err.message; busy = false; sec.querySelectorAll(".plan-btn:not(.done)").forEach((b) => b.removeAttribute("disabled")); }
    };

    const recommended = plan.options.find((o) => o.intensity === plan.recommended);
    sec.append(el("div", { class: "quest-head" },
      el("div", {}, el("div", { class: "muted small", text: `${fmtDay(plan.day)} · allowed up to ${plan.cap}` }),
        el("div", { class: "big", text: `Recommended: ${recommended ? recommended.title : plan.recommended}` })),
    ));
    sec.append(el("p", { class: "summary", text: plan.summary.replace(/^Recommended: [^.]*\.\s*/, "") }));
    if (plan.coach_note) sec.append(el("p", { class: "summary", text: `Coach: ${plan.coach_note}` }));

    if (chosen) {
      sec.append(el("div", { class: `chosen ${chosen.overridden ? "over" : ""}`, role: "status" },
        el("div", {}, el("b", { text: `Planned for today: ${chosen.title}` }),
          chosen.overridden ? el("p", { class: "badge warn" }, "▲ Above what your signals allow. ", chosen.warnings.join(" ")) : null),
        el("button", { class: "ghost", onclick: () => act(clearChoice) }, "Undo")));
    }
    sec.append(el("div", { class: "options" }, ...plan.options.map((o) => card(o, chosen, busy, act))));
    sec.append(message);
    sec.append(el("p", { class: "muted small", text: "You decide. Every option can be chosen; the labels only tell you what your own data suggests." }));
  },
};
