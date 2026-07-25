import type { CSSProperties } from "react";
import type { WfmSummary } from "../types";
import { round } from "../utils/format";

type Item = { label: string; value: string; unit?: string; sub: React.ReactNode; accent: string };

// Four readouts telling the story in order: forecast is solved, staffing isn't,
// coverage is short, and the fix is small.
export default function KpiStrip({ s }: { s: WfmSummary }) {
  const items: Item[] = [
    {
      label: "Forecast error",
      value: String(s.forecast.mae),
      unit: "MAE",
      accent: "var(--signal)",
      sub: (
        <>
          at the noise floor of <b>{s.forecast.noise_floor_mae}</b> — prediction is maxed out
        </>
      ),
    },
    {
      label: "Slots understaffed",
      value: String(round(s.capacity.understaffed_pct)),
      unit: "%",
      accent: "var(--deficit)",
      sub: (
        <>
          while <b>{round(s.capacity.overstaffed_pct)}%</b> sit clearly overstaffed
        </>
      ),
    },
    {
      label: "Coverage shortfall",
      value: String(round(Math.abs(s.coverage.net_shortage_agent_hours))),
      unit: "agent-h",
      accent: "var(--deficit)",
      sub: (
        <>
          worst skill <b>{s.coverage.worst_skill.replace(/^Tier 1 - /, "T1 ")}</b> at {s.coverage.worst_gap}
        </>
      ),
    },
    {
      label: "Roster moves to fix",
      value: String(s.optimizer.moves),
      unit: "moves",
      accent: "var(--signal)",
      sub: (
        <>
          <b>{s.optimizer.reassign}</b> reassign · <b>{s.optimizer.cross_train}</b> cross-train
        </>
      ),
    },
  ];

  return (
    <div className="kpi">
      {items.map((it) => (
        <div className="kpi-item" key={it.label} style={{ "--accent": it.accent } as CSSProperties}>
          <div className="kpi-label">{it.label}</div>
          <div className="kpi-val">
            {it.value}
            {it.unit && <span className="unit">{it.unit}</span>}
          </div>
          <div className="kpi-sub">{it.sub}</div>
        </div>
      ))}
    </div>
  );
}
