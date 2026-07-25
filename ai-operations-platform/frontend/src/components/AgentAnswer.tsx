import ReactMarkdown from "react-markdown";
import type { AgentResponse, AnalyticsLink } from "../types";

// One assistant turn: the (possibly still-streaming) markdown answer + report
// links and caveats, which appear once the final payload lands.
export default function AgentAnswer({
  answer,
  streaming,
  response,
  onOpenAnalytics,
}: {
  answer: string;
  streaming: boolean;
  response?: AgentResponse;
  onOpenAnalytics: (link: AnalyticsLink) => void;
}) {
  return (
    <div className="answer">
      <div className={`answer-body${streaming ? " streaming" : ""}`}>
        <ReactMarkdown>{answer}</ReactMarkdown>
      </div>

      {response && response.analytics_links.length > 0 && (
        <div className="answer-links">
          {response.analytics_links.map((l) => (
            <button key={l.href} className="link-btn" onClick={() => onOpenAnalytics(l)}>
              {l.label} ↗
            </button>
          ))}
        </div>
      )}

      {response && response.caveats.length > 0 && (
        <ul className="answer-caveats">
          {response.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
