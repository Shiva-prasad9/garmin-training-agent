// Hand-written SVG charts: a line chart with a personal "normal range" band, and stacked bars.
// Specs: 2px lines, 8px+ end dot with a 2px surface ring, hairline grid, tooltip on hover/focus.
import { el, svgEl, fmtDate, fmtNum, zStatus } from "./util.js";

const DEFAULT_H = 210, M = { l: 40, r: 44, t: 14, b: 26 };

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
  const W = Math.max(host.clientWidth, 260), H = o.height ?? DEFAULT_H;
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
    const when = (o.periodLabel || fmtDate)(r.period ?? r.week);
    svg.append(svgEl("text", { x: cx, y: h - 6, "text-anchor": "middle" }, when));
    const hit = svgEl("rect", { x: cx - slot / 2, y: 0, width: slot, height: h, fill: "transparent", tabindex: 0,
      "aria-label": `${o.periodWord || "Week of"} ${when}, total ${fmtNum(totals[i], o.decimals ?? 0)} ${o.unit || "load"}` });
    const show = () => {
      tip.replaceChildren(el("div", { class: "t", text: `${o.periodWord || "Week of"} ${when}` }),
        el("div", { class: "v", text: `${fmtNum(totals[i], o.decimals ?? 0)} ${o.unit || "load"}` }),
        ...present.map((k) => el("div", { class: "t" }, el("span", { class: "k", style: `background:${o.colors[k]}` }), `${o.names[k]} ${fmtNum(r[k], o.decimals ?? 0)}`)));
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

// One measurement along a workout (x = distance in km). Same look as the trend charts: 2px line, light wash, hairline grid,
// hover/arrow-key readout. `onCursor(fraction)` reports the hovered position; the returned `setCursor(fraction)` mirrors one.
export function seriesChart(host, o) {
  host.replaceChildren();
  const W = Math.max(host.clientWidth, 260), h = 150, m = { l: 44, r: 12, t: 10, b: 24 };
  const xs = o.x, ys = o.y, n = Math.min(xs.length, ys.length);
  const vals = ys.slice(0, n).filter((v) => v != null);
  if (n < 2 || !vals.length) {
    host.append(el("p", { class: "empty", text: "Not recorded for this workout." }));
    return { setCursor() {} };
  }
  let min = Math.min(...vals), max = Math.max(...vals);
  const pad = (max - min || 1) * 0.1;
  min -= pad; max += pad;
  if (o.min != null) min = Math.max(min, o.min);
  const fmt = o.fmt || ((v) => fmtNum(v, o.decimals ?? 0));
  const x0 = xs[0] ?? 0, x1 = xs[n - 1] ?? 1, xr = x1 - x0 || 1;
  const px = (i) => M2(m.l + (((xs[i] ?? x0) - x0) / xr) * (W - m.l - m.r));
  const M2 = (v) => Math.round(v * 10) / 10;
  const py = (v) => m.t + ((max - v) * (h - m.t - m.b)) / (max - min || 1);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${h}`, role: "img", "aria-label": o.label });
  for (let t = 0; t <= 2; t++) {
    const v = min + ((max - min) * t) / 2, yy = py(v);
    svg.append(svgEl("line", { x1: m.l, x2: W - m.r, y1: yy, y2: yy, stroke: "var(--grid)", "stroke-width": 1 }));
    svg.append(svgEl("text", { x: m.l - 8, y: yy + 4, "text-anchor": "end" }, fmt(v)));
  }
  [0, 0.5, 1].forEach((f, k) => svg.append(svgEl("text", { x: m.l + f * (W - m.l - m.r), y: h - 6,
    "text-anchor": k === 0 ? "start" : k === 2 ? "end" : "middle" }, `${fmtNum(x0 + xr * f, 1)} km`)));
  for (const r of runs(ys.slice(0, n), (v) => v)) {
    const line = r.map(([i, v]) => `${px(i)},${py(v)}`);
    svg.append(svgEl("polygon", { points: [`${px(r[0][0])},${h - m.b}`, ...line, `${px(r[r.length - 1][0])},${h - m.b}`].join(" "),
      fill: o.color, opacity: 0.1 }));
    svg.append(svgEl("polyline", { points: line.join(" "), fill: "none", stroke: o.color, "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round" }));
  }
  const cross = svgEl("line", { y1: m.t, y2: h - m.b, stroke: "var(--muted)", "stroke-width": 1, opacity: 0, "pointer-events": "none" });
  const dot = svgEl("circle", { r: 4, fill: o.color, stroke: "var(--surface-2)", "stroke-width": 2, opacity: 0, "pointer-events": "none" });
  const tip = el("div", { class: "tip", style: "display:none" });
  const place = (i) => {
    const xx = px(i);
    cross.setAttribute("x1", xx); cross.setAttribute("x2", xx); cross.setAttribute("opacity", 1);
    if (ys[i] != null) { dot.setAttribute("cx", xx); dot.setAttribute("cy", py(ys[i])); dot.setAttribute("opacity", 1); } else dot.setAttribute("opacity", 0);
    return xx;
  };
  let idx = 0;
  const show = (i) => {
    idx = Math.max(0, Math.min(n - 1, i));
    const xx = place(idx);
    tip.replaceChildren(el("div", { class: "t", text: `${fmtNum(xs[idx], 1)} km` }),
      el("div", { class: "v" }, el("span", { class: "k", style: `background:${o.color}` }), ys[idx] == null ? "no reading" : `${fmt(ys[idx])} ${o.unit || ""}`));
    tip.style.display = "block";
    const left = (xx / W) * host.clientWidth;
    tip.style.left = `${Math.min(left + 12, host.clientWidth - tip.offsetWidth - 4)}px`; tip.style.top = "0px";
    o.onCursor?.(idx / (n - 1));
  };
  const hide = () => { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); tip.style.display = "none"; o.onCursor?.(null); };
  const hit = svgEl("rect", { x: m.l - 4, y: 0, width: W - m.l - m.r + 8, height: h, fill: "transparent", tabindex: 0,
    "aria-label": `${o.label}: use left and right arrows to move along the workout` });
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const xv = x0 + (((e.clientX - r.left) / r.width) * W - m.l) / (W - m.l - m.r) * xr;
    let best = 0;
    for (let i = 1; i < n; i++) if (Math.abs((xs[i] ?? x0) - xv) < Math.abs((xs[best] ?? x0) - xv)) best = i;
    show(best);
  });
  hit.addEventListener("pointerleave", hide);
  hit.addEventListener("focus", () => show(idx));
  hit.addEventListener("blur", hide);
  hit.addEventListener("keydown", (e) => {
    const step = Math.max(1, Math.round(n / 40));
    if (e.key === "ArrowLeft") { show(idx - step); e.preventDefault(); }
    if (e.key === "ArrowRight") { show(idx + step); e.preventDefault(); }
  });
  svg.append(cross, dot, hit);
  host.append(svg, tip);
  return { setCursor(f) { if (f == null) { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); } else place(Math.round(f * (n - 1))); } };
}

// The route as a line (no map tiles, nothing leaves this computer). North is up; a scale bar shows distance.
export function routeMap(host, route, o) {
  host.replaceChildren();
  if (!route || route.length < 2) {
    host.append(el("p", { class: "empty", text: "No GPS route for this workout." }));
    return { setCursor() {} };
  }
  const W = Math.max(host.clientWidth, 240), pad = 22;
  const lats = route.map((p) => p[0]), lons = route.map((p) => p[1]);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const k = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const wDeg = Math.max((maxLon - minLon) * k, 1e-5), hDeg = Math.max(maxLat - minLat, 1e-5);
  const H = Math.round(Math.max(200, Math.min(380, (W - 2 * pad) * (hDeg / wDeg) + 2 * pad)));
  const s = Math.min((W - 2 * pad) / wDeg, (H - 2 * pad) / hDeg);
  const ox = (W - wDeg * s) / 2, oy = (H - hDeg * s) / 2;
  const X = (lon) => ox + (lon - minLon) * k * s, Y = (lat) => oy + (maxLat - lat) * s;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.label });
  svg.append(svgEl("rect", { x: 1, y: 1, width: W - 2, height: H - 2, rx: 10, fill: "var(--surface-2)", stroke: "var(--outline)", "stroke-width": 2 }));
  const pts = route.map((p) => `${X(p[1]).toFixed(1)},${Y(p[0]).toFixed(1)}`).join(" ");
  svg.append(svgEl("polyline", { points: pts, fill: "none", stroke: "var(--surface)", "stroke-width": 7, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  svg.append(svgEl("polyline", { points: pts, fill: "none", stroke: o.color, "stroke-width": 3.5, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  const [a, b] = [route[0], route[route.length - 1]];
  svg.append(svgEl("circle", { cx: X(a[1]), cy: Y(a[0]), r: 6, fill: "var(--good)", stroke: "var(--surface-2)", "stroke-width": 2 }));
  svg.append(svgEl("text", { x: X(a[1]) + 9, y: Y(a[0]) - 8 }, "Start"));
  svg.append(svgEl("path", { d: `M${X(b[1]) - 5.5},${Y(b[0]) - 5.5}h11v11h-11z`, fill: "var(--crit)", stroke: "var(--surface-2)", "stroke-width": 2 }));
  svg.append(svgEl("text", { x: X(b[1]) + 9, y: Y(b[0]) + 16 }, "End"));
  svg.append(svgEl("text", { x: W - 14, y: 20, "text-anchor": "end" }, "N ↑"));
  // scale bar: pick 1, 2, 5 x 10^n km that is about a quarter of the width
  const mPerPx = 111320 / s, target = (W * 0.25) * mPerPx;
  const pow = 10 ** Math.floor(Math.log10(target)), bar = [1, 2, 5, 10].map((q) => q * pow).filter((v) => v <= target * 1.2).pop() || pow;
  const bw = bar / mPerPx;
  svg.append(svgEl("line", { x1: 14, x2: 14 + bw, y1: H - 14, y2: H - 14, stroke: "var(--ink-2)", "stroke-width": 2 }));
  svg.append(svgEl("text", { x: 14, y: H - 20 }, bar >= 1000 ? `${bar / 1000} km` : `${bar} m`));
  const marker = svgEl("circle", { r: 6, fill: "var(--surface)", stroke: o.color, "stroke-width": 3, opacity: 0, "pointer-events": "none" });
  svg.append(marker);
  host.append(svg);
  return { setCursor(f) {
    if (f == null) { marker.setAttribute("opacity", 0); return; }
    const p = route[Math.round(f * (route.length - 1))];
    marker.setAttribute("cx", X(p[1])); marker.setAttribute("cy", Y(p[0])); marker.setAttribute("opacity", 1);
  } };
}

// Tiny trend line for a KPI card: 2px line, soft wash, round end dot. Gaps (nulls) break the line.
export function sparkline(host, values, color) {
  host.replaceChildren();
  const W = 160, H = 40, p = 4, n = values.length;
  const vals = values.filter((v) => v != null);
  if (n < 2 || vals.length < 2) return;
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const x = (i) => p + (i * (W - 2 * p)) / (n - 1), y = (v) => H - p - ((v - min) / span) * (H - 2 * p);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Last days at a glance" });
  for (const r of runs(values, (v) => v)) {
    const line = r.map(([i, v]) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    svg.append(svgEl("polygon", { points: [`${x(r[0][0])},${H - p}`, ...line, `${x(r[r.length - 1][0])},${H - p}`].join(" "), fill: color, opacity: 0.14 }));
    svg.append(svgEl("polyline", { points: line.join(" "), fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
  }
  const last = n - 1 - [...values].reverse().findIndex((v) => v != null);
  svg.append(svgEl("circle", { cx: x(last), cy: y(values[last]), r: 3.5, fill: color, stroke: "var(--surface)", "stroke-width": 2 }));
  host.append(svg);
}

// Semi-circle gauge of the four allowed levels (rest, easy, moderate, hard). Levels up to `cap` are lit; the needle marks `pick`.
export function levelGauge(host, o) {
  host.replaceChildren();
  const cx = 110, cy = 104, r = 84, W = 220, H = 128, gap = 3;
  const pt = (deg, rad = r) => [cx + rad * Math.cos((deg * Math.PI) / 180), cy - rad * Math.sin((deg * Math.PI) / 180)];
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.label });
  o.levels.forEach((lv, i) => {
    const a0 = 180 - i * 45 - gap, a1 = 180 - (i + 1) * 45 + gap, [x0, y0] = pt(a0), [x1, y1] = pt(a1);
    svg.append(svgEl("path", { d: `M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`, fill: "none",
      stroke: lv.color, "stroke-width": 16, "stroke-linecap": "round", opacity: lv.lit ? 1 : 0.18 }));
  });
  const tip = o.levels.findIndex((l) => l.key === o.pick);
  if (tip >= 0) {
    const [nx, ny] = pt(180 - (tip + 0.5) * 45, r - 30);
    svg.append(svgEl("line", { x1: cx, y1: cy, x2: nx, y2: ny, stroke: "var(--ink)", "stroke-width": 3, "stroke-linecap": "round" }));
  }
  svg.append(svgEl("circle", { cx, cy, r: 7, fill: "var(--ink)", stroke: "var(--surface)", "stroke-width": 3 }));
  host.append(svg);
}

// Progress ring with a number in the middle.
export function ring(host, o) {
  host.replaceChildren();
  const S = 120, c = S / 2, r = 46, len = 2 * Math.PI * r, frac = Math.max(0, Math.min(1, o.fraction));
  const svg = svgEl("svg", { viewBox: `0 0 ${S} ${S}`, role: "img", "aria-label": o.label });
  svg.append(svgEl("circle", { cx: c, cy: c, r, fill: "none", stroke: "var(--grid)", "stroke-width": 12 }));
  svg.append(svgEl("circle", { cx: c, cy: c, r, fill: "none", stroke: o.color, "stroke-width": 12, "stroke-linecap": "round",
    "stroke-dasharray": `${(len * frac).toFixed(1)} ${len.toFixed(1)}`, transform: `rotate(-90 ${c} ${c})` }));
  svg.append(svgEl("text", { x: c, y: c + 2, "text-anchor": "middle", class: "ring-num" }, o.center));
  svg.append(svgEl("text", { x: c, y: c + 20, "text-anchor": "middle", class: "ring-sub" }, o.sub || ""));
  host.append(svg);
}
