import { getOverview, getPlan } from "./api.js";
import { guide, insightPanels, panels } from "./panels/index.js";
import { buildNav, KIND_NAMES } from "./nav.js";
import { renderActivitiesView } from "./views/activities_view.js";
import { el, fmtDay } from "./util.js";

const main = document.getElementById("panels");
const subtitle = document.getElementById("subtitle");
const state = { days: 10, actDays: 180, guideOpen: false, save: (k, v) => safeStorage("set", k, v) };
const nav = buildNav(document.getElementById("nav"));
const pageTitle = document.getElementById("pageTitle");
const rangeControl = document.getElementById("range");

function safeStorage(op, key, value) {
  try { return op === "get" ? localStorage.getItem(key) : localStorage.setItem(key, value); } catch { return null; }
}

// theme toggle (remembered per browser; works without storage)
const root = document.documentElement;
const savedTheme = safeStorage("get", "theme");
if (savedTheme) root.dataset.theme = savedTheme;
document.getElementById("theme").addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light"; // dark is the default
  safeStorage("set", "theme", root.dataset.theme);
  show(); // redraw charts so they pick up the new colours
});

// range selector
const savedDays = Number(safeStorage("get", "days"));
if ([7, 10, 14].includes(savedDays)) state.days = savedDays;
const buttons = [...document.querySelectorAll("#range button")];
function markRange() { buttons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.days) === state.days))); }
buttons.forEach((b) => b.addEventListener("click", () => {
  state.days = Number(b.dataset.days); safeStorage("set", "days", state.days); markRange(); show();
}));
markRange();
const savedAct = Number(safeStorage("get", "actDays"));
if ([30, 90, 180, 365].includes(savedAct)) state.actDays = savedAct;

// which page: #/overview (default), #/activities/<sport>, #/guide
function route() {
  const [view, kind] = location.hash.replace(/^#\/?/, "").split("/");
  return { view: ["activities", "guide", "insights"].includes(view) ? view : "overview", kind: kind || "all" };
}
async function show() {
  const r = route();
  nav.mark(r);
  rangeControl.hidden = r.view !== "overview"; // the 7/10/14 day buttons only apply to the overview
  pageTitle.textContent = r.view === "overview" ? "Dashboard" : r.view === "guide" ? "User guide" : r.view === "insights" ? "Insights" : KIND_NAMES[r.kind] || "Activities";
  if (r.view === "overview") return load();
  main.classList.add("loading");
  try {
    if (r.view === "guide") {
      subtitle.textContent = "How to read this dashboard";
      main.replaceChildren();
      const sec = el("section", { class: "panel panel-guide" });
      main.append(sec);
      guide.render(sec, null, { guideOpen: true });
    } else if (r.view === "insights") {
      subtitle.textContent = "What your data says, and what to do next";
      const plan = await getPlan().catch((err) => ({ error: err.message }));
      main.replaceChildren();
      for (const p of insightPanels) {
        const sec = el("section", { class: `panel panel-${p.id}` });
        main.append(sec);
        p.render(sec, { plan }, state);
      }
      if (!main.querySelector(".panel:not([hidden])")) main.append(el("section", { class: "panel" }, el("p", { class: "empty", text: "No insights yet. They appear once enough days of data are stored." })));
    } else {
      subtitle.textContent = "Your workouts, by sport and month";
      await renderActivitiesView(main, r.kind, state, nav, show);
    }
  } catch (err) {
    main.replaceChildren(el("section", { class: "panel" }, el("p", { text: `Error: ${err.message}` })));
  } finally {
    main.classList.remove("loading");
  }
}
window.addEventListener("hashchange", () => { window.scrollTo(0, 0); show(); });

async function load() {
  main.classList.add("loading"); // keep the previous render, just dim it
  const scrollY = window.scrollY;
  try {
    const data = await getOverview(state.days);
    data.plan = await getPlan().catch((err) => ({ error: err.message }));
    main.replaceChildren();
    if (data.empty) {
      subtitle.textContent = "No data yet";
      main.append(el("section", { class: "panel" }, el("p", { text: "The database is empty. Run scripts/backfill.py first." })));
      return;
    }
    const behind = data.days_behind > 0 ? ` · latest data is ${data.days_behind} day${data.days_behind > 1 ? "s" : ""} old` : "";
    subtitle.textContent = `${fmtDay(data.latest_date)}${behind}`;
    for (const p of panels) {
      const sec = el("section", { class: `panel panel-${p.id}` });
      main.append(sec);
      try { p.render(sec, data, state); } catch (err) { sec.append(el("p", { class: "empty", text: `This panel could not be drawn: ${err.message}` })); }
    }
    window.scrollTo(0, scrollY);
  } catch (err) {
    subtitle.textContent = "Could not load data";
    main.replaceChildren(el("section", { class: "panel" }, el("p", { text: `Error: ${err.message}` })));
  } finally {
    main.classList.remove("loading");
  }
}
show();

// Panels announce changes (a chosen session, a gym entry); redraw everything from fresh data.
document.addEventListener("data-changed", () => show());
