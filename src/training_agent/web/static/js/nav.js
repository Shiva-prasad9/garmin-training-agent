// Side navigation: Overview, Activities (a drop-down of sports) and Guide. Routes are hash links: #/overview, #/activities/bike, #/guide.
import { el, svgEl } from "./util.js";

export const KIND_NAMES = { all: "All activities", bike: "Cycling", run: "Running", hike: "Hiking & walking", swim: "Swimming", gym: "Strength", other: "Other" };
const KINDS = Object.keys(KIND_NAMES);
const DOT = { bike: "bike", run: "run", hike: "other", swim: "swim", gym: "gym", other: "other" };
const ICONS = {
  overview: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  guide: "M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM8 8h6M8 12h6",
  insights: "M13.5 2 4 13.5h6.2L9 22l10-12.2h-6.4z",
};
const icon = (name) => svgEl("svg", { viewBox: "0 0 24 24", class: "ico", "aria-hidden": "true" },
  svgEl("path", { d: ICONS[name], fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linejoin": "round", "stroke-linecap": "round" }));

export function buildNav(host) {
  const counts = {};
  const kindLinks = KINDS.map((k) => {
    const count = el("span", { class: "count" });
    const a = el("a", { href: `#/activities/${k}`, "data-kind": k },
      k === "all" ? null : el("i", { class: "dot", style: `background:var(--s-${DOT[k]})` }), el("span", { class: "lbl", text: KIND_NAMES[k] }), count);
    counts[k] = count;
    return a;
  });
  const group = el("details", { class: "navgroup" },
    el("summary", {}, icon("activity"), el("span", { class: "lbl", text: "Activities" })), el("div", { class: "sub" }, ...kindLinks));
  const overview = el("a", { href: "#/overview", "data-view": "overview" }, icon("overview"), el("span", { class: "lbl", text: "Overview" }));
  const guide = el("a", { href: "#/guide", "data-view": "guide" }, icon("guide"), el("span", { class: "lbl", text: "User guide" }));
  const insights = el("a", { href: "#/insights", "data-view": "insights" }, icon("insights"), el("span", { class: "lbl", text: "Insights" }));
  host.replaceChildren(overview, group, guide, insights);

  return {
    mark({ view, kind }) {
      overview.removeAttribute("aria-current"); guide.removeAttribute("aria-current"); insights.removeAttribute("aria-current");
      kindLinks.forEach((a) => a.removeAttribute("aria-current"));
      group.classList.toggle("active", view === "activities");
      if (view === "overview") overview.setAttribute("aria-current", "page");
      else if (view === "guide") guide.setAttribute("aria-current", "page");
      else if (view === "insights") insights.setAttribute("aria-current", "page");
      else if (view === "activities") {
        group.open = true;
        kindLinks.find((a) => a.dataset.kind === kind)?.setAttribute("aria-current", "page");
      }
    },
    setCounts(byKind) {
      const total = Object.values(byKind).reduce((s, v) => s + v, 0);
      counts.all.textContent = String(total);
      for (const k of KINDS.slice(1)) counts[k].textContent = byKind[k] ? String(byKind[k]) : "";
    },
  };
}
