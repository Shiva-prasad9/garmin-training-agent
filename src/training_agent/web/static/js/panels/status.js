// Status window: the latest day compared with your own normal.
import { el, fmtDay, fmtNum, zStatus } from "../util.js";

// tag = RPG-style label; key = field in the API; domain = how far (in spreads) the meter reaches either side.
const STATS = [
  { tag: "VIT", name: "HRV, last night", key: "hrv_last_night_ms", unit: "ms", good: 1 },
  { tag: "REST", name: "Sleep score", key: "sleep_score", unit: "", good: 1 },
  { tag: "SLP", name: "Sleep duration", key: "sleep_hours", unit: "h", dec: 1, good: 1 },
  { tag: "PULSE", name: "Resting heart rate", key: "resting_hr", unit: "bpm", good: -1 },
];
const FLAG_TEXT = {
  short_sleep: "Short night: sleep readings ignored",
  hrv_outlier: "HRV outlier",
  missing_sleep: "No sleep data",
  missing_hrv: "No HRV data",
  insufficient_baseline: "Baseline still building",
};

function meter(s) {
  if (s.base == null) return null;
  const span = 4 * s.spread, lo = s.base - span;
  const pct = (v) => Math.max(0, Math.min(100, ((v - lo) / (2 * span)) * 100));
  const normL = pct(s.base - 1.5 * s.spread), normR = pct(s.base + 1.5 * s.spread);
  return el("div", { class: "meter", role: "img", "aria-label": "Position compared with your normal range" },
    el("div", { class: "norm", style: `left:${normL}%;width:${normR - normL}%` }),
    el("div", { class: "mark", style: `left:${pct(s.value)}%` }));
}

// 7-day trend, worded by whether the direction is good for this signal (icon + word, never colour alone).
function trendBadge(sig, good, unit, dec = 0) {
  if (sig.trend == null) return el("div", { class: "badge", text: "7-day: not enough data" });
  if (sig.trend === "steady") return el("div", { class: "badge", text: `\u2194 7-day: steady (avg ${fmtNum(sig.trend_mean, dec)}${unit ? " " + unit : ""})` });
  const better = (sig.trend === "up") === (good === 1);
  return el("div", { class: `badge ${better ? "good" : "warn"}` },
    `${sig.trend === "up" ? "\u25B2" : "\u25BC"} 7-day: ${better ? "improving" : "declining"} (avg ${fmtNum(sig.trend_mean, dec)}${unit ? " " + unit : ""})`);
}

function card(def, sig) {
  const s = { value: sig.value, base: sig.baseline, spread: sig.spread, z: sig.z };
  const st = zStatus(s.z);
  return el("div", { class: "stat" },
    el("div", { class: "tag", text: def.tag }),
    el("div", { class: "name", text: def.name }),
    el("div", { class: "val" }, fmtNum(s.value, def.dec ?? 0), el("small", { text: def.unit })),
    s.base != null ? el("div", { class: "base", text: `your usual ${fmtNum(s.base, def.dec ?? 0)} ${def.unit}` }) : null,
    el("div", { class: `badge ${st.cls}` }, st.icon ? `${st.icon} ` : "", st.label),
    trendBadge(sig, def.good, def.unit, def.dec ?? 0),
    meter(s));
}

export default {
  id: "status",
  title: "Status window",
  render(sec, data) {
    sec.append(el("h2", { text: "Status window" }));
    const s = data.status;
    const bb = s.body_battery_morning;
    const bbSt = zStatus(bb.z);
    sec.append(el("div", { class: "status-head" },
      el("div", {},
        el("div", { class: "hero" }, el("span", { class: "num", text: fmtNum(bb.value) }),
          el("span", { class: "lbl", text: "HP · morning Body Battery" })),
        el("div", { class: `badge ${bbSt.cls}` }, bbSt.icon ? `${bbSt.icon} ` : "", bbSt.label,
          bb.baseline != null ? ` (usual ${fmtNum(bb.baseline)})` : ""),
        trendBadge(bb, 1, "")),
      el("div", { class: "chips" },
        el("span", { class: "chip", text: fmtDay(s.date) }),
        s.hrv_status ? el("span", { class: "chip", text: `HRV status: ${s.hrv_status.toLowerCase()}` }) : null,
        ...s.flags.map((f) => el("span", { class: "chip flag", text: FLAG_TEXT[f] || f })))));
    sec.append(el("div", { class: "stats" }, ...STATS.map((d) => card(d, s[d.key]))));
  },
};
