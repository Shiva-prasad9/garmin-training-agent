// Trend charts for the selected range, plus a table view of the same numbers.
import { el, fmtDate, fmtNum, watchWidth } from "../util.js";
import { lineChart } from "../charts.js";

// Adding a chart = adding one entry here.
const CHARTS = [
  { key: "hrv_last_night_ms", title: "HRV", sub: "Overnight average, ms", unit: "ms", color: "var(--line-hrv)" },
  { key: "sleep_hours", title: "Sleep", sub: "Hours per night", unit: "h", color: "var(--line-sleep)", decimals: 1 },
  { key: "resting_hr", title: "Resting heart rate", sub: "Beats per minute", unit: "bpm", color: "var(--line-rhr)" },
  { key: "body_battery_morning", title: "Body Battery (HP)", sub: "Level at wake-up", unit: "", color: "var(--line-bb)", max: 100, min: 0 },
];
const FLAG_FOR_SIGNAL = (key, row) => {
  if (["sleep_hours", "hrv_last_night_ms"].includes(key) && row.flags.includes("short_sleep")) return "short night";
  if (key === "hrv_last_night_ms" && row.flags.includes("hrv_outlier")) return "HRV outlier";
  return null;
};

export default {
  id: "trends",
  title: "Trends",
  render(sec, data) {
    sec.append(el("h2", { text: `Trends · last ${data.days} days` }));
    sec.append(el("div", { class: "legend" },
      el("span", {}, el("i", { style: "background:var(--accent);opacity:.25" }), "your normal range (28-day baseline)"),
      el("span", {}, el("i", { style: "background:var(--crit)" }), "✕ flagged day (unreliable reading)")));
    const grid = el("div", { class: "grid" });
    for (const c of CHARTS) {
      const host = el("div", { class: "chart" });
      grid.append(el("div", { class: "card" }, el("h3", { text: c.title }), el("div", { class: "sub", text: c.sub }), host));
      watchWidth(host, () => lineChart(host, {
        ...c, label: `${c.title} over the last ${data.days} days`,
        points: data.series.map((r) => ({
          date: r.date, value: r[c.key].value, base: r[c.key].baseline, spread: r[c.key].spread, z: r[c.key].z,
          flag: FLAG_FOR_SIGNAL(c.key, r),
        })),
      }));
      sec.append(grid);
    }
    // Table view: every number is reachable without hovering.
    const head = ["Date", ...CHARTS.map((c) => c.title)];
    const table = el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h) => el("th", { text: h })))),
      el("tbody", {}, ...[...data.series].reverse().map((r) => el("tr", {},
        el("td", { text: fmtDate(r.date) }),
        ...CHARTS.map((c) => el("td", { text: fmtNum(r[c.key].value, c.decimals ?? 0) }))))));
    sec.append(el("details", { class: "table" }, el("summary", { text: "Table view" }), el("div", { class: "tbl" }, table)));
  },
};
