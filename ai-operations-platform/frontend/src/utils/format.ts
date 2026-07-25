// Presentation helpers shared across the workforce panels.

export const round = (n: number, d = 0): number => {
  const f = 10 ** d;
  return Math.round(n * f) / f;
};

export const signed = (n: number, d = 0): string => `${n > 0 ? "+" : ""}${round(n, d)}`;

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Medium label — fits the wider row labels (heatmap, gap list, realignment).
export const shortSkill = (n: string): string => n.replace(" - ", " ").replace("Reliability / SRE", "SRE");

// Tight label — for the narrow recommendations table where moves must stay on one line.
const TIGHT: Record<string, string> = {
  "Tier 1 - Technical Support": "T1 Tech",
  "Tier 2 - Product Support": "T2 Product",
  "Customer Service": "Customer Svc",
  "Reliability / SRE": "SRE",
  "Returns & Exchanges": "Returns",
  "Sales Engineering": "Sales Eng",
  "IT Support": "IT",
  "People Ops": "People Ops",
  "Billing": "Billing",
};
export const tightSkill = (n: string): string => TIGHT[n] ?? n;

// q-th percentile of a numeric array (q in [0,1]); robust chart scaling.
export function percentile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(q * sorted.length))];
}

// Diverging cell colour for the coverage grid: red = short, teal = surplus.
// Alpha scales with magnitude so near-balanced cells fade into the panel.
export function gapColor(value: number, limit = 8): string {
  const t = Math.min(Math.abs(value) / limit, 1);
  const alpha = 0.12 + t * 0.78;
  const rgb = value < 0 ? "255, 90, 95" : "52, 225, 196";
  return `rgba(${rgb}, ${value === 0 ? 0 : alpha})`;
}

// Map a series of numbers to SVG polyline points inside a [w,h] box.
export function toPoints(values: number[], w: number, h: number, pad = 0, min?: number, max?: number): string {
  const lo = min ?? Math.min(...values);
  const hi = max ?? Math.max(...values);
  const span = hi - lo || 1;
  const innerH = h - pad * 2;
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1 || 1)) * w;
      const y = pad + innerH - ((v - lo) / span) * innerH;
      return `${round(x, 2)},${round(y, 2)}`;
    })
    .join(" ");
}
