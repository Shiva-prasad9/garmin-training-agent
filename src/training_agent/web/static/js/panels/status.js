// Key numbers: the latest day compared with your own normal, each with its last days as a small trend line.
import { el, fmtNum, watchWidth, zStatus } from "../util.js";
import { sparkline } from "../charts.js";

const KPIS = [
  { label: "Body Battery", key: "body_battery_morning", unit: "", note: "at wake-up", good: 1, color: "var(--line-bb)" },
  { label: "HRV", key: "hrv_last_night_ms", unit: "ms", note: "last night", good: 1, color: "var(--line-hrv)" },
  { label: "Sleep score", key: "sleep_score", unit: "", note: "last night", good: 1, color: "var(--line-sleep)", extra: "sleep_hours" },
  { label: "Resting heart rate", key: "resting_hr", unit: "bpm", note: "", good: -1, color: "var(--line-rhr)" },
];
const FLAG_TEXT = {
  short_sleep: "Short night: sleep readings ignored",
  hrv_outlier: "HRV outlier",
  missing_sleep: "No sleep data",
  missing_hrv: "No HRV data",
  insufficient_baseline: "Baseline still building",
};

// Weekly direction in two or three words (icon + words, never colour alone).
function trendBadge(sig, good) {
  if (sig.trend == null) return null;
  if (sig.trend === "steady") return el("div", { class: "badge", text: "\u2194 Steady this week" });
  const better = (sig.trend === "up") === (good === 1);
  return el("div", { class: `badge ${better ? "good" : "warn"}` }, `${sig.trend === "up" ? "\u25B2 Rising" : "\u25BC Falling"} \u00B7 ${better ? "good" : "not ideal"}`);
}

function kpi(def, s, series) {
  const sig = s[def.key], st = zStatus(sig.z);
  const spark = el("div", { class: "spark" });
  watchWidth(spark, () => sparkline(spark, series.map((r) => r[def.key].value), def.color));
  return el("div", { class: "stat" },
    el("div", { class: "kpi-top" }, el("i", { class: "dot", style: `background:${def.color}` }), el("span", { class: "name", text: def.label }),
      def.note ? el("span", { class: "note", text: def.note }) : null),
    el("div", { class: "val" }, fmtNum(sig.value), el("small", { text: def.unit }),
      def.extra && s[def.extra] && s[def.extra].value != null ? el("span", { class: "extra", text: `${fmtNum(s[def.extra].value, 1)} h sleep` }) : null),
    sig.baseline != null ? el("div", { class: "base", text: `your usual ${fmtNum(sig.baseline)}${def.unit ? " " + def.unit : ""}` }) : null,
    el("div", { class: `badge ${st.cls}` }, st.icon ? `${st.icon} ` : "", st.label),
    trendBadge(sig, def.good),
    spark);
}

export default {
  id: "status",
  title: "Key numbers",
  render(sec, data) {
    const s = data.status;
    if (s.flags.length) sec.append(el("div", { class: "status-strip" }, ...s.flags.map((f) => el("span", { class: "chip flag", text: FLAG_TEXT[f] || f }))));
    sec.append(el("div", { class: "kpis" }, ...KPIS.map((d) => kpi(d, s, data.series))));
  },
};
