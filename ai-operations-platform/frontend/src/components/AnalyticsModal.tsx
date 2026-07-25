import { useEffect } from "react";
import type { ReportsBundle } from "../types";
import ForecastPanel from "./ForecastPanel";
import CoveragePanel from "./CoveragePanel";
import RealignmentPanel from "./RealignmentPanel";
import InsightsPanel from "./InsightsPanel";
import ClientsPanel from "./ClientsPanel";

const TITLES: Record<string, string> = {
  forecast: "Forecast",
  coverage: "Coverage & SLA",
  realignment: "Reallocation plan",
  insights: "Trends",
  clients: "Clients",
};

// Report pop-up: renders the deterministic report for the chosen view.
export default function AnalyticsModal({
  view,
  bundle,
  onClose,
}: {
  view: string | null;
  bundle: ReportsBundle | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!view) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="modal-kicker">Report</div>
            <div className="modal-title">{TITLES[view] ?? view}</div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="modal-body">
          {!bundle ? (
            <p className="muted">Sync your data first.</p>
          ) : view === "forecast" ? (
            <ForecastPanel f={bundle.forecast} />
          ) : view === "coverage" ? (
            <CoveragePanel c={bundle.coverage} />
          ) : view === "realignment" ? (
            <RealignmentPanel o={bundle.optimizer} />
          ) : view === "insights" ? (
            <InsightsPanel insights={bundle.insights} />
          ) : view === "clients" ? (
            <ClientsPanel clients={bundle.clients} />
          ) : (
            <p className="muted">No report for this view.</p>
          )}
        </div>
      </div>
    </div>
  );
}
