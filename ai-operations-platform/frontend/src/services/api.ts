// Thin fetch client for the backend API.

import type {
  AnalyzeResult,
  CapacityResult,
  CoverageResult,
  DatasetManifest,
  ForecastResult,
  OptimizerResult,
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
};
