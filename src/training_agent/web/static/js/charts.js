// Hand-written SVG charts: a line chart with a personal "normal range" band, and stacked bars.
// Specs: 2px lines, 8px+ end dot with a 2px surface ring, hairline grid, tooltip on hover/focus.
import { el, svgEl, fmtDate, fmtNum, zStatus } from "./util.js";

const H = 210, M = { l: 40, r: 44, t: 14, b: 26 };

// Break a point list into runs of consecutive non-null values.
function runs(points, accessor) {
  const out = []; let cur = [];
  points.forEach((p, i) => {
    const v = accessor(p);
    if (v == null) { if (cur.length) out.push(cur); cur = []; } else cur.push([i, v]);
  });
  if (cur.length) out.push(cur);
  return out;
}

export function lineChart(host, o) {
  host.replaceChildren();
  const W = Math.max(host.clientWidth, 260);
  const pts = o.points, n = pts.length, dec = o.decimals ?? 0;
  const vals = pts.map((p) => p.value).filter((v) => v != null);
  const bandLo = pts.filter((p) => p.base != null).map((p) => p.base - 1.5 * p.spread);
  const bandHi = pts.filter((p) => p.base != null).map((p) => p.base + 1.5 * p.spread);
  if (!vals.length) { host.append(el("p", { class: "empty", text: "No data in this range." })); return; }

  let min = Math.min(...vals, ...bandLo), max = Math.max(...vals, ...bandHi);
  const pad = (max - min || 1) * 0.1;
  min -= pad; max += pad;
  if (o.max != null) max = Math.min(max, o.max);
  if (o.min != null) min = Math.max(min, o.min);

  const x = (i) => M.l + (n === 1 ? 0 : (i * (W - M.l - M.r)) / (n - 1));
  const y = (v) => M.t + ((max - Math.min(Math.max(v, min), max)) * (H - M.t - M.b)) / (max - min || 1);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.label });

  // grid + y ticks
  for (let t = 0; t <= 3; t++) {
    const v = min + ((max - min) * t) / 3, yy = y(v);
    svg.append(svgEl("line", { x1: M.l, x2: W - M.r, y1: yy, y2: yy, stroke: "var(--grid)", "stroke-width": 1 }));
    svg.append(svgEl("text", { x: M.l - 8, y: yy + 4, "text-anchor": "end" }, fmtNum(v, dec > 0 ? 1 : 0)));
  }
  // x ticks: first, middle, last
  [0, Math.floor((n - 1) / 2), n - 1].filter((v, i, a) => a.indexOf(v) === i).forEach((i) =>
    svg.append(svgEl("text", { x: x(i), y: H - 6, "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle" }, fmtDate(pts[i].date))));

  // normal-range band (runs of points with a baseline)
  for (const r of runs(pts, (p) => (p.base == null ? null : p.base))) {
    const top = r.map(([i]) => `${x(i)},${y(pts[i].base + 1.5 * pts[i].spread)}`);
    const bot = r.map(([i]) => `${x(i)},${y(pts[i].base - 1.5 * pts[i].spread)}`).reverse();
    svg.append(svgEl("polygon", { points: [...top, ...bot].join(" "), fill: "var(--accent)", opacity: 0.12 }));
    svg.append(svgEl("polyline", { points: r.map(([i, v]) => `${x(i)},${y(v)}`).join(" "), fill: "none",
      stroke: "var(--muted)", "stroke-width": 1, opacity: 0.8 }));
  }

  // area wash + 2px line
  for (const r of runs(pts, (p) => p.value)) {
    const line = r.map(([i, v]) => `${x(i)},${y(v)}`);
    const base = y(min);
    svg.append(svgEl("polygon", { points: [`${x(r[0][0])},${base}`, ...line, `${x(r[r.length - 1][0])},${base}`].join(" "),
      fill: o.color, opacity: 0.1 }));
    svg.append(svgEl("polyline", { points: line.join(" "), fill: "none", stroke: o.color, "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round" }));
  }

  // markers: flagged days get a red cross; last point gets the end dot + value
  pts.forEach((p, i) => {
    if (p.value == null) return;
    if (p.flag) {
      const cx = x(i), cy = y(p.value);
      svg.append(svgEl("path", { d: `M${cx - 4},${cy - 4}L${cx + 4},${cy + 4}M${cx + 4},${cy - 4}L${cx - 4},${cy + 4}`,
        stroke: "var(--crit)", "stroke-width": 2, "stroke-linecap": "round" }));
    } else if (n <= 16 || i === n - 1) {
      svg.append(svgEl("circle", { cx: x(i), cy: y(p.value), r: 4, fill: o.color, stroke: "var(--surface-2)", "stroke-width": 2 }));
    }
  });
  const last = pts[n - 1];
  if (last.value != null)
    svg.append(svgEl("text", { class: "endlabel", x: x(n - 1) + 9, y: y(last.value) + 4 }, fmtNum(last.value, dec)));

  // hover layer: crosshair snaps to the nearest day
  const cross = svgEl("line", { y1: M.t, y2: H - M.b, stroke: "var(--muted)", "stroke-width": 1, opacity: 0, "pointer-events": "none" });
  const tip = el("div", { class: "tip", style: "display:none" });
  const hit = svgEl("rect", { x: M.l - 6, y: 0, width: W - M.l - M.r + 12, height: H, fill: "transparent", tabindex: 0,
    "aria-label": `${o.label}: use left and right arrows to read each day` });
  let idx = n - 1;
  const show = (i) => {
    idx = Math.max(0, Math.min(n - 1, i));
    const p = pts[idx], px = x(idx);
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("opacity", 1);
    const st = zStatus(p.z);
    tip.replaceChildren(
      el("div", { class: "t", text: fmtDate(p.date) }),
      el("div", { class: "v" }, el("span", { class: "k", style: `background:${o.color}` }), `${fmtNum(p.value, dec)} ${o.unit || ""}`),
      p.base != null ? el("div", { class: "t", text: `usual ${fmtNum(p.base, dec)} · ${st.icon} ${st.label}` }) : null,
      p.flag ? el("div", { class: "t", text: `✕ flagged: ${p.flag}` }) : null,
    );
    tip.style.display = "block";
    const left = (px / W) * host.clientWidth;
    tip.style.left = `${Math.min(left + 12, host.clientWidth - tip.offsetWidth - 4)}px`;
    tip.style.top = "6px";
  };
  const hide = () => { cross.setAttribute("opacity", 0); tip.style.display = "none"; };
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    show(Math.round(((px - M.l) / (W - M.l - M.r)) * (n - 1)));
  });
  hit.addEventListener("pointerleave", hide);
  hit.addEventListener("focus", () => show(idx));
  hit.addEventListener("blur", hide);
  hit.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { show(idx - 1); e.preventDefault(); }
    if (e.key === "ArrowRight") { show(idx + 1); e.preventDefault(); }
  });
  svg.append(cross, hit);
  host.append(svg, tip);
}

// Stacked columns: one per week, one segment per sport. 24px max, 2px surface gaps, 4px rounded top.
export function stackedBars(host, o) {
  host.replaceChildren();
  const rows = o.rows, keys = o.keys, w = Math.max(host.clientWidth, 260), h = 220, m = { l: 38, r: 10, t: 12, b: 26 };
  const totals = rows.map((r) => keys.reduce((s, k) => s + (r[k] || 0), 0));
  const max = Math.max(...totals, 1) * 1.1;
  const slot = (w - m.l - m.r) / rows.length, bw = Math.min(24, slot * 0.6);
  const y = (v) => m.t + ((max - v) * (h - m.t - m.b)) / max;
  const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": o.label });
  for (let t = 0; t <= 3; t++) {
    const v = (max * t) / 3, yy = y(v);
    svg.append(svgEl("line", { x1: m.l, x2: w - m.r, y1: yy, y2: yy, stroke: "var(--grid)" }));
    svg.append(svgEl("text", { x: m.l - 8, y: yy + 4, "text-anchor": "end" }, fmtNum(v, 0)));
  }
  const tip = el("div", { class: "tip", style: "display:none" });
  rows.forEach((r, i) => {
    const cx = m.l + slot * i + slot / 2;
    let acc = 0;
    const present = keys.filter((k) => (r[k] || 0) > 0);
    present.forEach((k, j) => {
      const top = y(acc + r[k]), bottom = y(acc) - (j > 0 ? 2 : 0), hh = Math.max(bottom - top, 0);
      acc += r[k];
      const isTop = j === present.length - 1, rad = Math.min(4, hh / 2);
      const d = isTop
        ? `M${cx - bw / 2},${top + hh}V${top + rad}Q${cx - bw / 2},${top} ${cx - bw / 2 + rad},${top}H${cx + bw / 2 - rad}Q${cx + bw / 2},${top} ${cx + bw / 2},${top + rad}V${top + hh}Z`
        : `M${cx - bw / 2},${top}H${cx + bw / 2}V${top + hh}H${cx - bw / 2}Z`;
      svg.append(svgEl("path", { d, fill: o.colors[k] }));
    });
    svg.append(svgEl("text", { x: cx, y: h - 6, "text-anchor": "middle" }, fmtDate(r.week)));
    const hit = svgEl("rect", { x: cx - slot / 2, y: 0, width: slot, height: h, fill: "transparent", tabindex: 0,
      "aria-label": `Week of ${fmtDate(r.week)}, total load ${fmtNum(totals[i], 0)}` });
    const show = () => {
      tip.replaceChildren(el("div", { class: "t", text: `Week of ${fmtDate(r.week)}` }),
        el("div", { class: "v", text: `${fmtNum(totals[i], 0)} load` }),
        ...present.map((k) => el("div", { class: "t" }, el("span", { class: "k", style: `background:${o.colors[k]}` }), `${o.names[k]} ${fmtNum(r[k], 0)}`)));
      tip.style.display = "block";
      const left = (cx / w) * host.clientWidth;
      tip.style.left = `${Math.min(left + 12, host.clientWidth - tip.offsetWidth - 4)}px`; tip.style.top = "6px";
    };
    hit.addEventListener("pointermove", show); hit.addEventListener("focus", show);
    hit.addEventListener("pointerleave", () => (tip.style.display = "none"));
    hit.addEventListener("blur", () => (tip.style.display = "none"));
    svg.append(hit);
  });
  host.append(svg, tip);
}
