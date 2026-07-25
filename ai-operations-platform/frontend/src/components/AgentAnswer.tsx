import ReactMarkdown from "react-markdown";
import type { AgentResponse, AnalyticsLink } from "../types";

// One assistant turn: the grounded markdown answer + report links + caveats.
// (The tool trace now lives in the right-hand Thinking-process bar.)
export default function AgentAnswer({
  response,
  onOpenAnalytics,
}: {
  response: AgentResponse;
  onOpenAnalytics: (link: AnalyticsLink) => void;
}) {
  return (
    <div className="answer">
      <div className="answer-body">
        <ReactMarkdown>{response.answer}</ReactMarkdown>
      </div>

      {response.analytics_links.length > 0 && (
        <div className="answer-links">
          {response.analytics_links.map((l) => (
            <button key={l.href} className="link-btn" onClick={() => onOpenAnalytics(l)}>
              {l.label} ↗
            </button>
          ))}
        </div>
      )}

      {response.caveats.length > 0 && (
        <ul className="answer-caveats">
          {response.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
