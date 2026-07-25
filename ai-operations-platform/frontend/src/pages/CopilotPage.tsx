import { useEffect, useRef, useState } from "react";
import type { Exchange } from "../hooks/useConversation";
import type { ReportsBundle } from "../types";
import AgentAnswer from "../components/AgentAnswer";
import Dots from "../components/Dots";

const SUGGESTIONS = [
  "If volume rises 30% tomorrow, can we still meet SLA with 24 agents?",
  "Which client is driving the most load, and why?",
  "What if we do nothing this week?",
  "Are ticket priorities set correctly in Billing?",
];

export default function CopilotPage({
  bundle,
  syncing,
  onSync,
  onOpenView,
  exchanges,
  ask,
  busy,
}: {
  bundle: ReportsBundle | null;
  syncing: boolean;
  onSync: () => void;
  onOpenView: (view: string) => void;
  exchanges: Exchange[];
  ask: (q: string) => void;
  busy: boolean;
}) {
  const [input, setInput] = useState("");
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: 1e9, behavior: "smooth" });
  }, [exchanges]);

  // Chat is locked until the first sync — the agent needs the reports.
  if (!bundle) {
    return (
      <div className="chat-locked">
        <div className="locked-inner">
          <div className="mast-eyebrow" style={{ justifyContent: "center" }}>
            <span className="dot" />
            AI Service Operations Copilot
          </div>
          <h1 className="copilot-title">Sync your data to start.</h1>
          <p className="copilot-sub">
            The copilot runs the analytics pipeline once, then answers from the reports — no re-runs
            per message.
          </p>
          <button className="btn big" onClick={onSync} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync your data to start chatting"}
          </button>
        </div>
      </div>
    );
  }

  const submit = () => {
    if (!input.trim() || busy) return;
    ask(input);
    setInput("");
  };

  return (
    <div className="copilot">
      <header className="copilot-head">
        <div className="mast-eyebrow">
          <span className="dot" />
          AI Service Operations Copilot
        </div>
        <h1 className="copilot-title">Ask the operation.</h1>
        <p className="copilot-sub">
          Answers come from your synced reports and <b>deterministic tools</b>. Open any report from
          the left; watch the tools run on the right.
        </p>
      </header>

      <div className="copilot-feed" ref={feedRef}>
        {exchanges.length === 0 && (
          <div className="suggestions">
            <div className="suggestions-label">Try asking</div>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion" onClick={() => ask(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        {exchanges.map((e) => (
          <div className="exchange" key={e.id}>
            <div className="q-bubble">{e.question}</div>
            {e.pending && <Dots />}
            {e.error && <div className="answer-error">Copilot unavailable — {e.error}</div>}
            {e.response && <AgentAnswer response={e.response} onOpenAnalytics={(link) => onOpenView(link.href.replace(/^.*#/, ""))} />}
          </div>
        ))}
      </div>

      <form
        className="composer"
        onSubmit={(ev) => {
          ev.preventDefault();
          submit();
        }}
      >
        <input
          className="composer-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about demand, SLA risk, staffing, clients, or trends…"
          disabled={busy}
        />
        <button className="btn" type="submit" disabled={busy || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
