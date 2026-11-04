import { getOverview, getPlan } from "./api.js";
import { panels } from "./panels/index.js";
import { el, fmtDay } from "./util.js";

const main = document.getElementById("panels");
const subtitle = document.getElementById("subtitle");
const state = { days: 10 };

function safeStorage(op, key, value) {
  try { return op === "get" ? localStorage.getItem(key) : localStorage.setItem(key, value); } catch { return null; }
}

// theme toggle (remembered per browser; works without storage)
const root = document.documentElement;
const savedTheme = safeStorage("get", "theme");
if (savedTheme) root.dataset.theme = savedTheme;
document.getElementById("theme").addEventListener("click", () => {
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  safeStorage("set", "theme", root.dataset.theme);
  load(); // redraw charts so they pick up the new colours
});

// range selector
const savedDays = Number(safeStorage("get", "days"));
if ([7, 10, 14].includes(savedDays)) state.days = savedDays;
const buttons = [...document.querySelectorAll("#range button")];
function markRange() { buttons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.days) === state.days))); }
buttons.forEach((b) => b.addEventListener("click", () => {
  state.days = Number(b.dataset.days); safeStorage("set", "days", state.days); markRange(); load();
}));
markRange();

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
    subtitle.textContent = `Status window · ${fmtDay(data.latest_date)}${behind}`;
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
load();

// Panels announce changes (a chosen session, a gym entry); redraw everything from fresh data.
document.addEventListener("data-changed", () => load());
