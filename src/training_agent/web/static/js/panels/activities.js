// Overview: a short "Recent activity" list. The full history, filters and manual log live under Activities in the menu.
import { el, fmtDay, fmtDuration, fmtNum, prettify, SPORT_NAMES } from "../util.js";
import { zonesBar } from "../zones.js";
import { openActivityDetail } from "./activity_detail.js";

const SPORTS = ["bike", "run", "gym", "swim", "other"];
const COLORS = Object.fromEntries(SPORTS.map((s) => [s, `var(--s-${s})`]));
const HAS_DETAIL = ["bike", "run", "other"]; // swimming and gym have no route to show
const RECENT = 5;

// "Cycling · Road biking", but just "Running" / "Strength training" when the names already match.
function activityTitle(sport, sourceSport) {
  const base = SPORT_NAMES[sport], src = prettify(sourceSport);
  if (!src || src.toLowerCase() === base.toLowerCase()) return base;
  return src.toLowerCase().startsWith(base.toLowerCase()) ? src : `${base} · ${src}`;
}

function wire(row, a, sport) {
  if (!HAS_DETAIL.includes(sport)) return row;
  row.classList.add("clickable");
  row.setAttribute("tabindex", "0"); row.setAttribute("role", "button"); row.setAttribute("title", "Open details");
  row.setAttribute("aria-label", `${activityTitle(sport, a.source_sport)}, ${fmtDay(a.start)}: open details`);
  row.addEventListener("click", () => openActivityDetail(a));
  row.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openActivityDetail(a); } });
  return row;
}

// Full row, used on the Activities page.
export function activityRow(a) {
  const sport = SPORTS.includes(a.sport) ? a.sport : "other";
  return wire(el("div", { class: "act" },
    el("div", { class: "bar", style: `background:${COLORS[sport]}` }),
    el("div", {},
      el("div", { class: "name", text: activityTitle(sport, a.source_sport) }),
      el("div", { class: "when", text: fmtDay(a.start) }),
      el("div", { class: "nums" },
        el("span", { text: fmtDuration(a.duration_min) }),
        a.distance_km ? el("span", { text: `${fmtNum(a.distance_km, 1)} km` }) : null,
        el("span", { text: a.avg_hr ? `${Math.round(a.avg_hr)} bpm avg` : "no heart rate" })),
      zonesBar(a)),
    el("div", { class: "load" }, el("b", { text: a.training_load != null ? fmtNum(a.training_load, 0) : "-" }), el("span", { text: "LOAD" }))), a, sport);
}

// Short row for the overview: sport colour, name, when, and one line of numbers.
function recentRow(a) {
  const sport = SPORTS.includes(a.sport) ? a.sport : "other";
  return wire(el("div", { class: "recent-row" },
    el("i", { class: "dot", style: `background:${COLORS[sport]}` }),
    el("div", {}, el("div", { class: "name", text: activityTitle(sport, a.source_sport) }),
      el("div", { class: "when", text: `${fmtDay(a.start)} · ${fmtDuration(a.duration_min)}${a.distance_km ? ` · ${fmtNum(a.distance_km, 1)} km` : ""}` }))), a, sport);
}

export default {
  id: "activities",
  title: "Recent activity",
  render(sec, data) {
    sec.append(el("h2", { text: "Recent activity" }));
    if (!data.activities.length) { sec.append(el("p", { class: "empty", text: `No workouts in the last ${data.days} days.` })); }
    else sec.append(el("div", { class: "recent" }, ...data.activities.slice(0, RECENT).map(recentRow)));
    sec.append(el("a", { class: "more-link", href: "#/activities/all" }, "See all activities →"));
  },
};
