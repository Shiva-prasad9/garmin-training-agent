// Small DOM helpers. All text goes in via textContent / text nodes (data is untrusted).

export function el(tag, props = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  append(n, children);
  return n;
}

export function svgEl(tag, attrs = {}, ...children) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  append(n, children);
  return n;
}

function append(parent, children) {
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    parent.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
}

export const fmtDate = (iso) =>
  new Date(iso.slice(0, 10) + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

export const fmtDay = (iso) =>
  new Date(iso.slice(0, 10) + "T00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

export function fmtNum(v, decimals = 0) {
  return v == null ? "-" : Number(v).toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: 0 });
}

export function fmtDuration(min) {
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

// Distance from your own baseline, in spread units -> label + status class (icon + word, never colour alone).
export function zStatus(z) {
  if (z == null) return { cls: "", icon: "", label: "No baseline yet", dir: "" };
  const a = Math.abs(z);
  const dir = z > 0 ? "above" : "below";
  if (a < 1.5) return { cls: "good", icon: "✓", label: "Normal", dir };
  if (a < 2.5) return { cls: "warn", icon: "▲", label: `Notable, ${dir} usual`, dir };
  return { cls: "crit", icon: "!", label: `Unusual, ${dir} usual`, dir };
}

export const SPORT_NAMES = { bike: "Cycling", run: "Running", gym: "Strength", other: "Other" };
export const cssVar = (name) => `var(--${name})`;

export function prettify(s) {
  return (s || "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

// Run draw() now and again whenever the host's width changes, so charts are drawn at their real size.
export function watchWidth(host, draw) {
  let last = 0;
  const run = () => {
    const w = host.clientWidth;
    if (!w || Math.abs(w - last) < 8) return;
    last = w; draw();
  };
  new ResizeObserver(run).observe(host);
  run();
}
