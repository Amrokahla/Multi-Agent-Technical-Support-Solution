// Thin fetch client for the backend API.

import type {
  AgentResponse,
  AnalyzeResult,
  CapacityResult,
  CoverageResult,
  DatasetManifest,
  ForecastResult,
  OptimizerResult,
  ReportsBundle,
  WfmBundle,
  WfmSummary,
} from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

// Surfaces the backend's `detail` message (e.g. "no created-at column") to the UI.
async function postFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* keep the default message */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  dataSummary: () => getJSON<DatasetManifest>("/health/data"),
  wfmSummary: () => getJSON<WfmSummary>("/wfm/summary"),
  wfmForecast: () => getJSON<ForecastResult>("/wfm/forecast"),
  wfmCapacity: () => getJSON<CapacityResult>("/wfm/capacity"),
  wfmCoverage: () => getJSON<CoverageResult>("/wfm/coverage"),
  wfmOptimize: () => getJSON<OptimizerResult>("/wfm/optimize"),

  // CSV-upload demo path — run the pipeline on an uploaded export or the sample.
  wfmAnalyze: (file: File) => postFile<AnalyzeResult>("/wfm/analyze", file),
  wfmSample: () => getJSON<AnalyzeResult>("/wfm/sample"),
  sampleCsvUrl: `${BASE}/wfm/sample.csv`,

  // The backend computes the pipeline once and caches it, so fetching in
  // parallel costs no more than the slowest single stage.
  async wfmBundle(): Promise<WfmBundle> {
    const [summary, forecast, capacity, coverage, optimizer] = await Promise.all([
      api.wfmSummary(),
      api.wfmForecast(),
      api.wfmCapacity(),
      api.wfmCoverage(),
      api.wfmOptimize(),
    ]);
    return { summary, forecast, capacity, coverage, optimizer };
  },

  // Reports — Sync runs the pipeline once and returns the cached bundle.
  syncReports: async (): Promise<ReportsBundle> => {
    const r = await fetch(`${BASE}/reports/sync`, { method: "POST" });
    if (!r.ok) throw new Error(`Sync failed (${r.status})`);
    return (await r.json()) as ReportsBundle;
  },
  getReports: () => getJSON<ReportsBundle>("/reports"),

  // Copilot — natural-language question to the orchestrator agent (with session memory).
  async askCopilot(question: string, history: { role: string; content: string }[] = []): Promise<AgentResponse> {
    const response = await fetch(`${BASE}/agent/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-20) }),
    });
    if (!response.ok) {
      let detail = `Copilot request failed (${response.status})`;
      try {
        detail = (await response.json()).detail ?? detail;
      } catch {
        /* keep default */
      }
      throw new Error(detail);
    }
    return (await response.json()) as AgentResponse;
  },
};
