import { useCallback, useState } from "react";
import { api } from "../services/api";
import type { AgentResponse } from "../types";

// Friendly labels for the inline "working" status while a tool runs.
const TOOL_LABEL: Record<string, string> = {
  forecast_demand: "Forecasting demand",
  predict_sla_risk: "Assessing SLA risk",
  allocate_resources: "Planning reallocation",
  operational_insights: "Reading trends",
  client_load: "Ranking clients",
  detect_spike: "Localizing the spike",
  capacity_impact: "Modeling capacity",
  whatif_simulate: "Running what-if",
  team_compare: "Comparing teams",
  analyze_tickets: "Analyzing tickets",
};

export type Exchange = {
  id: string;
  question: string;
  answer: string; // accumulated streamed text; overwritten by the authoritative answer on done
  status: string; // live "working" line shown until the first token
  streaming: boolean; // request in flight
  response?: AgentResponse; // final payload (links, caveats) — present once done
  error?: string;
};

let _seq = 0;

// Owns the chat turns and drives the streamed turn (tool status + answer tokens)
// with a blocking fallback if the stream can't open.
export function useConversation() {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const busy = exchanges.some((e) => e.streaming);

  const patch = useCallback((id: string, fn: (e: Exchange) => Exchange) => {
    setExchanges((prev) => prev.map((e) => (e.id === id ? fn(e) : e)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q) return;
      const id = `x${_seq++}`;
      let history: { role: string; content: string }[] = [];
      setExchanges((prev) => {
        history = prev
          .filter((e) => e.response)
          .flatMap((e) => [
            { role: "user", content: e.question },
            { role: "assistant", content: e.response!.answer },
          ]);
        return [...prev, { id, question: q, answer: "", status: "Planning…", streaming: true }];
      });

      try {
        await api.askCopilotStream(q, history, {
          onPlan: () => patch(id, (e) => (e.answer ? e : { ...e, status: "Planning…" })),
          onToolStart: (t) => patch(id, (e) => ({ ...e, status: `${TOOL_LABEL[t.tool] ?? t.tool}…` })),
          onToolEnd: () => {},
          onSynth: () => patch(id, (e) => (e.answer ? e : { ...e, status: "Writing the answer…" })),
          onToken: (text) => patch(id, (e) => ({ ...e, answer: e.answer + text, status: "" })),
          onDone: (response) =>
            patch(id, (e) => ({ ...e, response, answer: response.answer, status: "", streaming: false })),
          onError: (message) => patch(id, (e) => ({ ...e, error: message, streaming: false })),
        });
      } catch {
        // Stream couldn't open — fall back to the blocking endpoint once.
        try {
          const response = await api.askCopilot(q, history);
          patch(id, (e) => ({ ...e, response, answer: response.answer, status: "", streaming: false }));
        } catch (err) {
          const error = err instanceof Error ? err.message : String(err);
          patch(id, (e) => ({ ...e, error, streaming: false }));
        }
      }
    },
    [patch],
  );

  return { exchanges, ask, busy };
}
