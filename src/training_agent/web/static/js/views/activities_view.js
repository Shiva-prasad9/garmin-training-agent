// Activities section: every workout of one sport (or all) over 1, 3, 6 or 12 months, with totals, hours per month and the list.
// Clicking a ride, run or hike opens the same detail window as on the overview.
import { getActivityLog } from "../api.js";
import { stackedBars } from "../charts.js";
import { KIND_NAMES } from "../nav.js";
import { activityRow } from "../panels/activities.js";
import { manualLog } from "./manual_log.js";
import { el, fmtDate, fmtNum, watchWidth, SPORT_NAMES } from "../util.js";

export const PERIODS = [[30, "1 month"], [90, "3 months"], [180, "6 months"], [365, "12 months"]];
const SPORTS = ["bike", "run", "gym", "swim", "other"];
const COLORS = Object.fromEntries(SPORTS.map((s) => [s, `var(--s-${s})`]));
const monthName = (iso) => new Date(iso.slice(0, 7) + "-01T00:00").toLocaleDateString(undefined, { month: "long", year: "numeric" });
const monthShort = (iso) => new Date(iso.slice(0, 10) + "T00:00").toLocaleDateString(undefined, { month: "short" });
const hm = (h) => `${Math.floor(h)}h ${String(Math.round((h % 1) * 60)).padStart(2, "0")}m`;

function tile(label, value, sub) {
  return el("div", { class: "dv-tile" }, el("div", { class: "k", text: label }), el("div", { class: "v", text: value }),
    sub ? el("div", { class: "s", text: sub }) : null);
}

export async function renderActivitiesView(main, kind, state, nav, rerender) {
  const data = await getActivityLog(kind, state.actDays);
  nav.setCounts(data.counts);
  main.replaceChildren();
  const title = KIND_NAMES[kind] || "Activities"; // also the page title in the header

  // header with the period selector
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Period" },
    ...PERIODS.map(([d, label]) => el("button", { "aria-pressed": String(d === state.actDays), onclick: () => { state.actDays = d; state.save("actDays", d); rerender(); } }, label)));
  const head = el("section", { class: "panel" },
    el("div", { class: "view-head" }, el("h2", { text: `Last ${PERIODS.find(([d]) => d === state.actDays)?.[1] || state.actDays + " days"}` }), seg));
  const t = data.totals;
  head.append(el("div", { class: "dv-tiles" },
    tile("Workouts", String(t.count)),
    tile("Time", hm(t.hours), t.count ? `${hm(t.hours / Math.max(t.count, 1))} on average` : null),
    t.distance_km ? tile("Distance", `${fmtNum(t.distance_km, 0)} km`) : null,
    t.climbing_m ? tile("Climbing", `${fmtNum(t.climbing_m, 0)} m`, "where recorded") : null));
  const windowStart = new Date(Date.now() - state.actDays * 864e5).toISOString().slice(0, 10);
  if (data.history_from && data.history_from > new Date(new Date(windowStart).getTime() + 7 * 864e5).toISOString().slice(0, 10)) {
    head.append(el("p", { class: "notice", text: `Your stored history starts on ${data.history_from}. To see further back, run: .venv/bin/python scripts/backfill.py --days 365 --details` }));
  }
  if (kind === "swim" || kind === "gym") head.append(el("p", { class: "muted small", text: "Swimming and strength sessions show the list summary only (no route or per-second readings)." }));
  main.append(head);
  main.append(el("section", { class: "panel panel-manual" }, manualLog(kind === "all" ? "gym" : kind === "hike" ? "hike" : kind)));

  if (!t.count) {
    main.append(el("section", { class: "panel" }, el("p", { class: "empty", text: "No workouts of this kind in this period." })));
    return;
  }

  // hours per month; hiking and "other" share one colour, so they are summed into "other"
  const rows = data.months.map((m) => ({ period: m.period, bike: m.bike, run: m.run, gym: m.gym, swim: m.swim, other: m.hike + m.other }));
  const keys = SPORTS.filter((s) => rows.some((r) => r[s] > 0));
  const names = kind === "hike" ? { ...SPORT_NAMES, other: "Hiking & walking" } : SPORT_NAMES;
  const host = el("div", { class: "chart" });
  const chart = el("section", { class: "panel" }, el("h3", { text: "Hours per month" }),
    el("div", { class: "legend" }, ...keys.map((s) => el("span", {}, el("i", { style: `background:${COLORS[s]}` }), names[s]))), host);
  main.append(chart);
  watchWidth(host, () => stackedBars(host, { rows, keys, colors: COLORS, names, periodLabel: monthShort, periodWord: "In", unit: "h", decimals: 1,
    label: `Hours of training per month, ${title}` }));

  // list, grouped by month
  const list = el("section", { class: "panel" });
  let current = "", group = null, hours = 0, n = 0, monthIndex = 0;
  const closeGroup = () => { if (group) group.firstChild.querySelector(".mh").textContent = `${n} workout${n === 1 ? "" : "s"} · ${hm(hours)}`; };
  for (const a of data.activities) {
    const month = a.start.slice(0, 7);
    if (month !== current) {
      closeGroup();
      current = month; hours = 0; n = 0;
      group = el("details", { class: "month", ...(monthIndex++ < 2 ? { open: "" } : {}) }, // the latest two months start open
        el("summary", { class: "month-head" }, el("h3", { text: monthName(a.start) }), el("span", { class: "mh muted small" })));
      list.append(group);
      group.append(el("div", { class: "acts" }));
    }
    hours += a.duration_min / 60; n += 1;
    group.querySelector(".acts").append(activityRow(a));
  }
  closeGroup();
  main.append(list);
}
