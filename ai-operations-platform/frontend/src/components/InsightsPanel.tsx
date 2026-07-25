import type { InsightsData } from "../types";

// Trends report — KPI movements, anomalies, and the top drivers.
export default function InsightsPanel({ insights }: { insights: InsightsData }) {
  return (
    <div>
      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-title">Headline</div>
        <p style={{ margin: 0, fontSize: 15 }}>{insights.headline}</p>
      </div>

      <div className="panel">
        <div className="panel-title">KPI movement · last window vs prior</div>
        <div className="gaplist">
          {insights.kpis.map((k) => {
            const color = k.favorable === false ? "var(--deficit)" : k.favorable ? "var(--signal)" : "var(--muted)";
            return (
              <div className="gap-row" key={k.name} style={{ gridTemplateColumns: "160px 1fr 90px" }}>
                <span className="gap-name">{k.name.replace(/_/g, " ")}</span>
                <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                  {k.current} {k.unit}
                </span>
                <span className="gap-val" style={{ color }}>
                  {k.change_pct > 0 ? "+" : ""}
                  {k.change_pct}%
                </span>
              </div>
            );
          })}
        </div>
        {insights.anomalies.length > 0 && (
          <p className="chart-caption">
            {insights.anomalies.length} anomalous week(s) flagged.
          </p>
        )}
      </div>
    </div>
  );
}
