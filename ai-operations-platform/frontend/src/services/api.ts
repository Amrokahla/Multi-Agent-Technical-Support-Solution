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

  // Streamed copilot turn: tool events + answer tokens over SSE. Rejects if the
  // stream can't open so the caller can fall back to askCopilot.
  async askCopilotStream(
    question: string,
    history: { role: string; content: string }[],
    handlers: StreamHandlers,
  ): Promise<void> {
    const response = await fetch(`${BASE}/agent/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-20) }),
    });
    if (!response.ok || !response.body) throw new Error(`Stream unavailable (${response.status})`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSSE(buffer);
      buffer = rest;
      for (const ev of events) dispatchSSE(ev, handlers);
    }
  },
};

// --- SSE helpers (streaming copilot) -----------------------------------------

export interface SSEEvent {
  event: string;
  data: unknown;
}

export interface StreamHandlers {
  onPlan?: (round: number) => void;
  onToolStart: (e: { index: number; tool: string; arguments: Record<string, unknown> }) => void;
  onToolEnd: (e: { index: number; tool: string; ok: boolean; error: string | null }) => void;
  onSynth?: () => void;
  onToken: (text: string) => void;
  onDone: (response: AgentResponse) => void;
  onError: (message: string) => void;
}

// Pure parser: pull whole `event:/data:` frames out of the buffer, return the
// leftover partial frame. Comment lines (`:` keep-alives) and malformed frames
// are skipped. Tolerates \r\n from proxies.
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = [];
  let rest = buffer.replace(/\r\n/g, "\n");
  let idx: number;
  while ((idx = rest.indexOf("\n\n")) !== -1) {
    const raw = rest.slice(0, idx);
    rest = rest.slice(idx + 2);
    let event = "message";
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
      if (line.startsWith(":")) continue;
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (dataLines.length) {
      try {
        events.push({ event, data: JSON.parse(dataLines.join("\n")) });
      } catch {
        /* skip malformed frame */
      }
    }
  }
  return { events, rest };
}

function dispatchSSE(ev: SSEEvent, h: StreamHandlers): void {
  const d = ev.data as Record<string, unknown>;
  switch (ev.event) {
    case "plan":
      h.onPlan?.(Number(d.round));
      break;
    case "tool_start":
      h.onToolStart(d as never);
      break;
    case "tool_end":
      h.onToolEnd(d as never);
      break;
    case "synth":
      h.onSynth?.();
      break;
    case "token":
      h.onToken(String(d.text ?? ""));
      break;
    case "done":
      h.onDone(ev.data as AgentResponse);
      break;
    case "error":
      h.onError(String(d.message ?? "Copilot stream error"));
      break;
  }
}
