import { useRef, useState } from "react";
import { api } from "../services/api";
import type { AnalyzeResult, UploadMeta } from "../types";

type Props = {
  meta: UploadMeta | null; // present when an upload/sample is active
  onLoaded: (result: AnalyzeResult) => void;
  onReset: () => void;
};

// The demo's "test it on your data" control. Idle: a drop-zone + sample loader.
// Active: a status banner describing the uploaded analysis, with a reset.
export default function UploadBar({ meta, onLoaded, onReset }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function run(label: string, task: () => Promise<AnalyzeResult>) {
    setError(null);
    setBusy(label);
    try {
      onLoaded(await task());
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(null);
    }
  }

  const onFile = (file: File | undefined) => {
    if (file) run(file.name, () => api.wfmAnalyze(file));
  };

  if (meta) {
    return (
      <div className="src-banner">
        <span className="src-dot" />
        <div className="src-text">
          <b>{meta.source}</b> — {meta.tickets_used.toLocaleString()} tickets over {meta.ndays} days ·{" "}
          {meta.skills.length} skills · roster modeled ({meta.agents_modeled} agents, {meta.scale_factor}× scale)
          {meta.warnings.length > 0 && <span className="src-warn"> · {meta.warnings.join(" ")}</span>}
        </div>
        <button className="btn-ghost" onClick={onReset}>
          Reset to demo dataset
        </button>
      </div>
    );
  }

  return (
    <div
      className={`src-bar${dragging ? " drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        onFile(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(e) => onFile(e.target.files?.[0])}
      />
      <div className="src-lead">
        <div className="src-kicker">Test it on your data</div>
        <div className="src-desc">
          Drop a Zendesk ticket CSV export here — demand is read from your file, no integration needed.
        </div>
        {error && <div className="src-error">{error}</div>}
      </div>
      <div className="src-actions">
        <button className="btn" onClick={() => inputRef.current?.click()} disabled={!!busy}>
          {busy ? `Analyzing ${busy}…` : "Choose CSV"}
        </button>
        <button className="btn-ghost" onClick={() => run("sample", api.wfmSample)} disabled={!!busy}>
          {busy === "sample" ? "Loading…" : "Load sample"}
        </button>
        <a className="src-link" href={api.sampleCsvUrl} download>
          format?
        </a>
      </div>
    </div>
  );
}
