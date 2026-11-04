// Heart-rate zone strip shared by the activity list and the detail dialog.
import { el } from "./util.js";

export const ZONE_COLORS = ["var(--z1)", "var(--z2)", "var(--z3)", "var(--z4)", "var(--z5)"];

export function zonesBar(a) {
  if (!a.zones_s) return null;
  const total = a.zones_s.reduce((s, v) => s + v, 0);
  if (!total) return null;
  return el("div", { class: "zones", role: "img",
    "aria-label": "Time in heart rate zones 1 to 5: " + a.zones_s.map((v) => `${Math.round(v / 60)} min`).join(", ") },
    ...a.zones_s.map((v, i) => (v > 0 ? el("span", { style: `flex:${v};background:${ZONE_COLORS[i]}`, title: `Zone ${i + 1}: ${Math.round(v / 60)} min` }) : null)));
}
