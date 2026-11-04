// Workout detail dialog: key numbers, heart-rate zones, charts along the distance, and the route.
// Opened by clicking a row in the Activities panel. Data comes from /api/activities/<id> (already stored; no Garmin call).
import { getActivity } from "../api.js";
import { el, fmtDay, fmtNum, prettify, watchWidth, SPORT_NAMES } from "../util.js";
import { routeMap, seriesChart } from "../charts.js";
import { ZONE_COLORS, zonesBar } from "../zones.js";

const clock = (s) => {
  if (s == null) return "-";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.round(s % 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m ${String(sec).padStart(2, "0")}s`;
};
const paceText = (kmh) => {
  if (!kmh || kmh < 0.5) return "-";
  const p = 60 / kmh, m = Math.floor(p), s = Math.round((p - m) * 60);
  return `${s === 60 ? m + 1 : m}:${String(s === 60 ? 0 : s).padStart(2, "0")}`;
};
const paceFromMinutes = (v) => paceText(60 / v);
// Pace in min/km. Stops and walking breaks would stretch the chart, so readings slower than twice your typical pace become gaps.
function calmPace(speeds) {
  const paces = speeds.map((v) => (v != null && v > 1 ? 60 / v : null));
  const sorted = paces.filter((p) => p != null).sort((a, b) => a - b);
  const typical = sorted.length ? sorted[Math.floor(sorted.length / 2)] : null;
  return paces.map((p) => (p != null && typical != null && p <= typical * 2 ? p : null));
}

function tile(label, value, sub) {
  return el("div", { class: "dv-tile" }, el("div", { class: "k", text: label }), el("div", { class: "v", text: value }),
    sub ? el("div", { class: "s", text: sub }) : null);
}

function tiles(a, d, usePace) {
  const speed = (kmh) => (usePace ? `${paceText(kmh)} /km` : `${fmtNum(kmh, 1)} km/h`);
  const stopped = d.elapsed_s != null && d.moving_s != null ? d.elapsed_s - d.moving_s : null;
  const out = [
    tile("Distance", `${fmtNum(d.distance_km ?? a.distance_km, 1)} km`),
    tile("Moving time", clock(d.moving_s), "while you were moving"),
    tile("Elapsed time", clock(d.elapsed_s), stopped > 30 ? `${clock(stopped)} stopped` : "start to finish"),
    tile(usePace ? "Average pace" : "Average speed", speed(d.avg_moving_speed_kmh ?? d.avg_speed_kmh), "moving"),
    tile(usePace ? "Best pace" : "Max speed", speed(d.max_speed_kmh)),
    tile("Climbing", d.elevation_gain_m != null ? `↑ ${fmtNum(d.elevation_gain_m, 0)} m` : "-", d.elevation_loss_m != null ? `↓ ${fmtNum(d.elevation_loss_m, 0)} m` : null),
    tile("Elevation range", d.min_elevation_m != null ? `${fmtNum(d.min_elevation_m, 0)}–${fmtNum(d.max_elevation_m, 0)} m` : "-", "lowest to highest"),
    tile("Heart rate", d.avg_hr != null ? `${fmtNum(d.avg_hr, 0)} bpm` : "none", d.max_hr != null ? `${fmtNum(d.min_hr, 0)}–${fmtNum(d.max_hr, 0)} bpm range` : null),
    d.calories != null ? tile("Calories", fmtNum(d.calories, 0), "kcal") : null,
    d.avg_temp_c != null ? tile("Temperature", `${fmtNum(d.avg_temp_c, 0)} °C`, "average") : null,
    a.training_load != null ? tile("Training load", fmtNum(a.training_load, 0), "Garmin's own number") : null,
  ];
  return el("div", { class: "dv-tiles" }, ...out.filter(Boolean));
}

function zoneKey(a) {
  if (!a.zones_s || !a.zones_s.some((v) => v > 0)) return null;
  return el("div", {}, el("h4", { text: "Time in heart-rate zones" }), zonesBar(a),
    el("div", { class: "legend" }, ...a.zones_s.map((v, i) => el("span", {}, el("i", { style: `background:${ZONE_COLORS[i]}` }), `Z${i + 1} ${Math.round(v / 60)} min`))));
}

function render(body, a, d, sport) {
  const usePace = sport === "run" || /hik|walk/i.test(a.source_sport || "");
  const color = `var(--s-${sport})`;
  const s = d.series || {};
  const x = s.distance_km || [];
  const cursorTargets = [];
  const broadcast = (from) => (f) => cursorTargets.forEach((t) => { if (t !== from) t.setCursor(f); });

  const specs = [];
  if (s.heart_rate) specs.push({ title: "Heart rate", y: s.heart_rate, unit: "bpm", color: "var(--line-rhr)", dec: 0 });
  if (s.speed_kmh) {
    specs.push(usePace
      ? { title: "Pace", y: calmPace(s.speed_kmh), unit: "/km", color, fmt: paceFromMinutes }
      : { title: "Speed", y: s.speed_kmh, unit: "km/h", color, dec: 1 });
  }
  if (s.elevation_m) specs.push({ title: "Elevation", y: s.elevation_m, unit: "m", color: "var(--line-bb)", dec: 0 });
  if (s.power_w) specs.push({ title: "Power", y: s.power_w, unit: "W", color: "var(--s-other)", dec: 0 });
  if (s.cadence) specs.push({ title: usePace ? "Cadence (steps/min)" : "Cadence (rpm)", y: s.cadence, unit: usePace ? "spm" : "rpm", color: "var(--s-other)", dec: 0 });

  const charts = el("div", { class: "dv-charts" });
  for (const sp of specs) {
    const host = el("div", { class: "chart" });
    charts.append(el("div", { class: "dv-chart" }, el("h4", { text: sp.title }), host));
    let api = { setCursor() {} };
    const target = { setCursor: (f) => api.setCursor(f) };
    cursorTargets.push(target);
    watchWidth(host, () => {
      api = seriesChart(host, { x, y: sp.y, unit: sp.unit, color: sp.color, decimals: sp.dec, fmt: sp.fmt,
        label: `${sp.title} along the workout`, onCursor: broadcast(target) });
    });
  }
  const mapHost = el("div", { class: "chart" });
  let map = { setCursor() {} };
  cursorTargets.push({ setCursor: (f) => map.setCursor(f) });
  watchWidth(mapHost, () => { map = routeMap(mapHost, d.route, { color, label: "Route of the workout" }); });

  body.replaceChildren(
    tiles(a, d, usePace),
    el("div", { class: "dv-grid" },
      el("div", {}, el("h4", { text: "Route" }), mapHost,
        el("p", { class: "muted small", text: "Drawn from your GPS points on this page. No map service is used, so your route never leaves this computer." }),
        zoneKey(a)),
      specs.length ? charts : el("p", { class: "empty", text: "No per-second readings were stored for this workout." })));
}

export function openActivityDetail(a) {
  const sport = ["bike", "run"].includes(a.sport) ? a.sport : "other";
  const dlg = el("dialog", { class: "dv", "aria-label": `${SPORT_NAMES[a.sport] || "Workout"} details` });
  const title = `${SPORT_NAMES[a.sport] || "Workout"}${a.source_sport && prettify(a.source_sport).toLowerCase() !== (SPORT_NAMES[a.sport] || "").toLowerCase() ? ` · ${prettify(a.source_sport)}` : ""}`;
  const close = el("button", { class: "ghost", "aria-label": "Close details", onclick: () => dlg.close() }, "Close");
  const body = el("div", { class: "dv-body" }, el("p", { class: "muted", text: "Loading details…" }));
  dlg.style.setProperty("--sport", `var(--s-${sport})`);
  const big = a.distance_km ? [fmtNum(a.distance_km, a.distance_km >= 100 ? 0 : 1), "KM"] : [fmtNum(a.duration_min, 0), "MIN"];
  const burst = el("div", { class: "burst", "aria-hidden": "true" }, el("b", {}, big[0], el("small", { text: big[1] })));
  dlg.append(el("header", { class: "dv-head" }, el("div", {}, el("h3", { text: title }), el("div", { class: "muted small", text: fmtDay(a.start) })),
    el("div", { class: "right" }, burst, close)), body);
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  document.body.append(dlg);
  dlg.showModal();
  getActivity(a.id).then((res) => {
    if (!res.detail) {
      body.replaceChildren(el("p", { class: "empty", text: "The route and readings for this workout have not been downloaded yet. Run: .venv/bin/python scripts/backfill.py --days 90 --details" }));
      return;
    }
    render(body, res.activity, res.detail, sport);
  }).catch((err) => body.replaceChildren(el("p", { class: "empty", text: `Could not load the details: ${err.message}` })));
}
