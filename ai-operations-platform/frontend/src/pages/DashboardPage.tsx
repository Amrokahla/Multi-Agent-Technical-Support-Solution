import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { DatasetManifest } from "../types";

// Placeholder overview — confirms the backend + frozen dataset are wired up.
export default function DashboardPage() {
  const [data, setData] = useState<DatasetManifest | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dataSummary().then(setData).catch((e) => setError(String(e)));
  }, []);

  return (
    <section>
      <h1>Overview</h1>
      <p className="muted">Support operations intelligence over the Zendesk dataset.</p>

      {error && <p className="error">Backend not reachable — {error}</p>}
      {!data && !error && <p className="muted">Loading dataset summary…</p>}

      {data && (
        <div className="cards">
          <Stat label="Tickets" value={data.ticket_count} />
          <Stat label="Comments" value={data.comment_count} />
          <Stat label="SLA metric events" value={data.metric_events} />
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card">
      <div className="card-value">{value?.toLocaleString?.() ?? "—"}</div>
      <div className="card-label">{label}</div>
    </div>
  );
}
