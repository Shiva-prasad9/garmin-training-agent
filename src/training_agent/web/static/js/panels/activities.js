// Recent workouts (with heart-rate zones) and weekly training load by sport.
import { el, fmtDay, fmtDuration, fmtNum, prettify, watchWidth, SPORT_NAMES } from "../util.js";
import { stackedBars } from "../charts.js";

const SPORTS = ["bike", "run", "gym", "swim", "other"];
const COLORS = Object.fromEntries(SPORTS.map((s) => [s, `var(--s-${s})`]));
const ZONE_COLORS = ["var(--z1)", "var(--z2)", "var(--z3)", "var(--z4)", "var(--z5)"];

function zones(a) {
  if (!a.zones_s) return null;
  const total = a.zones_s.reduce((s, v) => s + v, 0);
  if (!total) return null;
  return el("div", { class: "zones", role: "img",
    "aria-label": "Time in heart rate zones 1 to 5: " + a.zones_s.map((v) => `${Math.round(v / 60)} min`).join(", ") },
    ...a.zones_s.map((v, i) => (v > 0 ? el("span", { style: `flex:${v};background:${ZONE_COLORS[i]}`, title: `Zone ${i + 1}: ${Math.round(v / 60)} min` }) : null)));
}

// "Cycling · Road biking", but just "Running" / "Strength training" when the names already match.
function activityTitle(sport, sourceSport) {
  const base = SPORT_NAMES[sport], src = prettify(sourceSport);
  if (!src || src.toLowerCase() === base.toLowerCase()) return base;
  return src.toLowerCase().startsWith(base.toLowerCase()) ? src : `${base} \u00B7 ${src}`;
}

function activityRow(a) {
  const sport = SPORTS.includes(a.sport) ? a.sport : "other";
  return el("div", { class: "act" },
    el("div", { class: "bar", style: `background:${COLORS[sport]}` }),
    el("div", {},
      el("div", { class: "name", text: activityTitle(sport, a.source_sport) }),
      el("div", { class: "when", text: fmtDay(a.start) }),
      el("div", { class: "nums" },
        el("span", { text: fmtDuration(a.duration_min) }),
        a.distance_km ? el("span", { text: `${fmtNum(a.distance_km, 1)} km` }) : null,
        el("span", { text: a.avg_hr ? `${Math.round(a.avg_hr)} bpm avg` : "no heart rate" })),
      zones(a)),
    el("div", { class: "load" }, el("b", { text: a.training_load != null ? fmtNum(a.training_load, 0) : "-" }), el("span", { text: "LOAD" })));
}

export default {
  id: "activities",
  title: "Activities",
  render(sec, data) {
    sec.append(el("h2", { text: "Activities" }));
    const left = el("div", { class: "acts" });
    if (!data.activities.length) left.append(el("p", { class: "empty", text: `No workouts in the last ${data.days} days.` }));
    data.activities.forEach((a) => left.append(activityRow(a)));
    left.append(el("div", { class: "legend" }, el("span", { text: "HR zones:" }),
      ...ZONE_COLORS.map((c, i) => el("span", {}, el("i", { style: `background:${c}` }), `Z${i + 1}`))));

    const host = el("div", { class: "chart" });
    const right = el("div", {}, el("h3", { text: "Weekly training load" }),
      el("div", { class: "legend" }, ...SPORTS.map((s) => el("span", {}, el("i", { style: `background:${COLORS[s]}` }), SPORT_NAMES[s]))),
      host,
      el("p", { class: "muted", text: "Garmin's own per-workout load, summed by week. Strength and rides without heart rate count for less than they cost you." }));
    sec.append(left, right);
    watchWidth(host, () => stackedBars(host, { rows: data.weekly_load, keys: SPORTS, colors: COLORS, names: SPORT_NAMES,
      label: "Weekly training load by sport, last 6 weeks" }));
  },
};
