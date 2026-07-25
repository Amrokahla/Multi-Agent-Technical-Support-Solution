import type { ClientsData } from "../types";

// Clients report — who drives the load and whether it's concentrated.
export default function ClientsPanel({ clients }: { clients: ClientsData }) {
  const max = Math.max(...clients.clients.map((c) => c.share_pct), 1);
  return (
    <div className="panel">
      <div className="panel-title" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Top clients by ticket share</span>
        <span className="legend">
          {clients.concentration.is_concentrated ? "concentrated" : "broad"} · top1 ×
          {clients.concentration.top1_vs_uniform ?? "—"} vs uniform
        </span>
      </div>
      <div className="gaplist">
        {clients.clients.map((c) => (
          <div className="gap-row" key={c.organization_id} style={{ gridTemplateColumns: "170px 1fr 120px" }}>
            <span className="gap-name">
              {c.client}
              {c.dedicated && <span className="risk-tag" style={{ marginLeft: 6 }}>dedicated</span>}
            </span>
            <span className="gap-track">
              <span
                className="gap-fill"
                style={{ left: 0, width: `${(c.share_pct / max) * 100}%`, background: "var(--signal)" }}
              />
            </span>
            <span className="gap-val" style={{ color: "var(--muted)" }}>
              {c.share_pct}% · {c.per_day}/day
            </span>
          </div>
        ))}
      </div>
      <p className="chart-caption">
        {clients.total_tickets.toLocaleString()} tickets in the window across all clients.
      </p>
    </div>
  );
}
