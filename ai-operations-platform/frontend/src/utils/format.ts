// Presentation helpers shared across the workforce panels.

export const round = (n: number, d = 0): number => {
  const f = 10 ** d;
  return Math.round(n * f) / f;
};

export const signed = (n: number, d = 0): string => `${n > 0 ? "+" : ""}${round(n, d)}`;

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// --- Tool display (thinking process) ----------------------------------------

const TOOL_LABEL: Record<string, string> = {
  forecast_demand: "Forecast demand",
  predict_sla_risk: "SLA risk",
  allocate_resources: "Allocate agents",
  operational_insights: "Insights",
  client_load: "Client load",
  detect_spike: "Spike detection",
  capacity_impact: "Capacity impact",
  whatif_simulate: "What-if",
  team_compare: "Team compare",
  analyze_tickets: "Analyze tickets",
};

export const toolLabel = (tool: string): string => TOOL_LABEL[tool] ?? tool;

// Short, readable argument summary (skips long free-text like `focus`).
export function formatToolArgs(args: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(args)) {
    if (v === null || v === undefined || v === false || v === true || k === "focus" || k === "by_queue") continue;
    if (k === "available_agents") parts.push(`${v} agents`);
    else if (k === "agents_delta") parts.push(`${Number(v) > 0 ? "+" : ""}${v} agents`);
    else if (k === "uplift_pct") parts.push(`${Number(v) > 0 ? "+" : ""}${v}% volume`);
    else if (k === "window_weeks") parts.push(`${v}wk`);
    else if (k === "window_days") parts.push(`${v}d`);
    else if (k === "sample_size") parts.push(`n=${v}`);
    else if (k === "top_n") parts.push(`top ${v}`);
    else parts.push(String(v));
  }
  return parts.join(" · ");
}

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
  const rgb = value < 0 ? "199, 123, 114" : "134, 185, 176";
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
