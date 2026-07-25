import type { CapacityResult } from "../types";
import { round } from "../utils/format";

const W = 960;
const H = 240;
const PADX = 6;
const PADY = 16;

// Step 2 — required vs available agents across the day. The coral band is where
// demand outruns the roster; the teal fill is covered capacity.
export default function IntradayPanel({ c }: { c: CapacityResult }) {
  const rows = c.intraday;
  const hi = Math.max(...rows.map((r) => Math.max(r.required, r.available))) * 1.08;
  const innerW = W - PADX * 2;
  const innerH = H - PADY * 2;

  const x = (i: number) => PADX + (i / (rows.length - 1)) * innerW;
  const y = (v: number) => PADY + innerH - (v / hi) * innerH;

  const line = (key: "required" | "available") => rows.map((r, i) => `${round(x(i), 1)},${round(y(r[key]), 1)}`).join(" ");
  const area = (key: "required" | "available") => {
    const pts = rows.map((r, i) => `${round(x(i), 1)},${round(y(r[key]), 1)}`).join(" L");
    return `M${pts} L${round(x(rows.length - 1), 1)},${H - PADY} L${round(x(0), 1)},${H - PADY} Z`;
  };

  const peakX = x(c.peak_hour);
  const ticks = [0, 3, 6, 9, 12, 15, 18, 21, 23];

  return (
    <div className="panel">
      <div className="panel-title" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Coverage by hour · average day (UTC)</span>
        <span className="legend">
          <span>
            <i style={{ background: "var(--deficit)" }} />
            required
          </span>
          <span>
            <i style={{ background: "var(--signal)" }} />
            available
          </span>
        </span>
      </div>

      <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
        aria-label="Required versus available agents by hour of day">
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} className="gridline" x1={0} y1={PADY + innerH * g} x2={W} y2={PADY + innerH * g} />
        ))}
        <path d={area("required")} fill="rgba(255,90,95,0.16)" />
        <path d={area("available")} fill="rgba(52,225,196,0.14)" />
        <polyline points={line("required")} fill="none" stroke="var(--deficit)" strokeWidth={2} />
        <polyline points={line("available")} fill="none" stroke="var(--signal)" strokeWidth={2} />
        <line x1={peakX} y1={PADY - 6} x2={peakX} y2={H - PADY} stroke="var(--demand)" strokeWidth={1} strokeDasharray="3 3" opacity={0.7} />
      </svg>

      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, padding: `0 ${PADX}px` }}>
        {ticks.map((t) => (
          <span key={t} style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--faint)" }}>
            {String(t).padStart(2, "0")}
          </span>
        ))}
      </div>

      <p className="chart-caption">
        Peak demand at <b>{String(c.peak_hour).padStart(2, "0")}:00</b> needs{" "}
        <b>{c.peak_required}</b> agents but only <b>{c.peak_available}</b> are on shift —{" "}
        {round(c.understaffed_pct)}% of hourly slots run short while {round(c.overstaffed_pct)}% sit
        idle. Handle time: <b>{c.handle_min_median}</b> min median, <b>{c.handle_min_p90}</b> min p90.
      </p>
    </div>
  );
}
