// Today's plan: the recommended session in full, the other choices compactly, and your choice.
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

function planButton(option, chosen, busy, act, label) {
  const selected = chosen && chosen.intensity === option.intensity;
  const button = el("button", {
    class: `plan-btn${selected ? " done" : ""}`, "aria-label": `${selected ? "Planned" : "Plan"}: ${option.title}`,
    onclick: () => act(() => choose(option.intensity)),
  }, selected ? "✓ Planned" : label);
  if (busy || selected) button.setAttribute("disabled", "");
  return button;
}

function more(option) {
  if (!option.reasons.length && !option.tomorrow) return null;
  return el("details", { class: "more" }, el("summary", { text: "Details" }),
    option.reasons.length ? el("ul", { class: "plain" }, ...option.reasons.map((r) => el("li", { text: r }))) : null,
    option.tomorrow ? el("p", { class: "tomorrow" }, el("b", { text: "Tomorrow: " }), option.tomorrow.replace(/^Tomorrow /, "")) : null);
}

// The recommended session, with its targets.
function hero(option, chosen, busy, act) {
  const lines = targetLines(option.prescription);
  return el("div", { class: `opt recommended${chosen && chosen.intensity === option.intensity ? " selected" : ""}` },
    el("div", { class: "opt-level", text: `★ Recommended · ${LEVEL_WORDS[option.intensity]}` }),
    el("h3", { text: option.title }),
    lines.length ? el("dl", { class: "targets" }, ...lines.map(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })])) : null,
    more(option),
    planButton(option, chosen, busy, act, "Plan this"));
}

// The other choices as compact buttons: name, and a short label with an icon. Choosing one plans it directly.
function choice(option, chosen, busy, act) {
  const risk = RISK[option.risk] || RISK.ok, selected = chosen && chosen.intensity === option.intensity;
  const short = { ok: "Fine to choose", caution: "Caution", not_advised: "Not advised", recommended: "Recommended" }[option.risk] || risk.label;
  const button = el("button", { class: `choice ${option.risk}${selected ? " selected" : ""}`, title: `${option.title}: ${risk.label}`,
    "aria-label": `${selected ? "Planned" : "Plan"}: ${option.title}. ${risk.label}`, onclick: () => act(() => choose(option.intensity)) },
    el("span", { class: "c-level", text: LEVEL_WORDS[option.intensity] }), el("b", { text: option.title }),
    el("span", { class: `badge ${risk.cls}` }, `${selected ? "\u2713 Planned" : `${risk.icon} ${short}`}`));
  if (busy || selected) button.setAttribute("disabled", "");
  return button;
}

export default {
  id: "quest",
  title: "Today's plan",
  render(sec, data) {
    sec.append(el("h2", { text: "Today's plan" }));
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

    const recommended = plan.options.find((o) => o.intensity === plan.recommended) || plan.options[0];
    sec.append(el("div", { class: "muted small", text: `${fmtDay(plan.day)} · allowed up to ${plan.cap}` }));

    if (chosen) {
      sec.append(el("div", { class: `chosen ${chosen.overridden ? "over" : ""}`, role: "status" },
        el("div", {}, el("b", { text: `Planned for today: ${chosen.title}` }),
          chosen.overridden ? el("p", { class: "badge warn" }, "▲ Above what your signals allow. ", chosen.warnings.join(" ")) : null),
        el("button", { class: "ghost", onclick: () => act(clearChoice) }, "Undo")));
    }
    sec.append(hero(recommended, chosen, busy, act),
      el("h3", { class: "mini", text: "Or choose" }),
      el("div", { class: "choices" }, ...plan.options.filter((o) => o !== recommended).map((o) => choice(o, chosen, busy, act))));
    sec.append(message);
  },
};
