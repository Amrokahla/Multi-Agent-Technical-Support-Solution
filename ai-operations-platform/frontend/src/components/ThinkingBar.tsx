import type { Exchange } from "../hooks/useConversation";
import { formatToolArgs, toolLabel } from "../utils/format";

// Right rail: the agent's thinking process for the latest turn — the tools it
// invoked, stacked in order, with status (running / success / failed).
export default function ThinkingBar({ exchanges }: { exchanges: Exchange[] }) {
  const last = exchanges[exchanges.length - 1];
  const trace = last?.response?.tool_trace ?? [];

  return (
    <aside className="thinking-bar">
      <p className="nav-label">Thinking process</p>

      {!last && <p className="thinking-empty">Tool activity appears here as you ask.</p>}

      {last?.pending && (
        <div className="think-step">
          <span className="think-dot running" />
          <div>
            <div className="think-tool">Planning…</div>
            <div className="think-args">running tools</div>
          </div>
        </div>
      )}

      {trace.map((t, i) => (
        <div className="think-step" style={{ animationDelay: `${i * 140}ms` }} key={i}>
          <span className={`think-dot ${t.ok ? "ok" : "fail"}`} />
          <div>
            <div className="think-tool">{toolLabel(t.tool)}</div>
            {formatToolArgs(t.arguments) && <div className="think-args">{formatToolArgs(t.arguments)}</div>}
            <div className={`think-status ${t.ok ? "ok" : "fail"}`}>{t.ok ? "success" : "failed"}</div>
          </div>
        </div>
      ))}

      {last && !last.pending && last.response && trace.length === 0 && (
        <div className="think-step">
          <span className="think-dot ok" />
          <div>
            <div className="think-tool">Answered from reports</div>
            <div className="think-args">no tools needed</div>
          </div>
        </div>
      )}
    </aside>
  );
}
