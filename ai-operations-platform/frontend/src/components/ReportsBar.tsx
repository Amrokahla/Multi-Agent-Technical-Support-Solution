import type { ReportsBundle } from "../types";

const TABS = [
  { key: "forecast", label: "Forecast" },
  { key: "coverage", label: "Coverage & SLA" },
  { key: "realignment", label: "Reallocation" },
  { key: "insights", label: "Trends" },
  { key: "clients", label: "Clients" },
];

// Left bar: report tabs (open pop-ups) + Sync data pinned at the bottom.
export default function ReportsBar({
  bundle,
  syncing,
  error,
  onSync,
  onOpen,
}: {
  bundle: ReportsBundle | null;
  syncing: boolean;
  error: string | null;
  onSync: () => void;
  onOpen: (view: string) => void;
}) {
  return (
    <aside className="reports-bar">
      <div className="brand">
        <div className="brand-mark">◇</div>
        <div className="brand-name">
          AI Operations
          <span>Support Intelligence</span>
        </div>
      </div>

      <div className="reports-body">
        <p className="nav-label">Reports</p>
        {bundle ? (
          <nav className="report-tabs">
            {TABS.map((t) => (
              <button key={t.key} className="report-tab" onClick={() => onOpen(t.key)}>
                {t.label}
              </button>
            ))}
          </nav>
        ) : (
          <p className="reports-hint">Sync your data to generate reports.</p>
        )}
      </div>

      <div className="reports-foot">
        {error && <div className="reports-err">{error}</div>}
        {bundle && (
          <div className="synced">
            synced {new Date(bundle.synced_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
        )}
        <button className="btn sync-btn" onClick={onSync} disabled={syncing}>
          {syncing ? "Syncing…" : bundle ? "Re-sync data" : "Sync data"}
        </button>
      </div>
    </aside>
  );
}
