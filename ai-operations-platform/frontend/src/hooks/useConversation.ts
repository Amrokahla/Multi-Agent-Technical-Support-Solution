import { useCallback, useState } from "react";
import { api } from "../services/api";
import type { AgentResponse } from "../types";

export type Exchange = { id: string; question: string; response?: AgentResponse; error?: string; pending: boolean };

let _seq = 0;

// Owns the chat turns so both the chat feed and the thinking bar can read them.
export function useConversation() {
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const busy = exchanges.some((e) => e.pending);

  const ask = useCallback(async (question: string) => {
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
      return [...prev, { id, question: q, pending: true }];
    });
    try {
      const response = await api.askCopilot(q, history);
      setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, response, pending: false } : e)));
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      setExchanges((prev) => prev.map((e) => (e.id === id ? { ...e, error, pending: false } : e)));
    }
  }, []);

  return { exchanges, ask, busy };
}
