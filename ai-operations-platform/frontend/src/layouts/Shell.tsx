import { useState } from "react";
import { useReports } from "../hooks/useReports";
import { useConversation } from "../hooks/useConversation";
import ReportsBar from "../components/ReportsBar";
import ThinkingBar from "../components/ThinkingBar";
import AnalyticsModal from "../components/AnalyticsModal";
import CopilotPage from "../pages/CopilotPage";

// App shell: reports bar (left) · chat (center) · thinking process (right).
export default function Shell() {
  const { bundle, syncing, error, sync } = useReports();
  const convo = useConversation();
  const [view, setView] = useState<string | null>(null);

  return (
    <div className="shell">
      <ReportsBar bundle={bundle} syncing={syncing} error={error} onSync={sync} onOpen={setView} />
      <main className="shell-main">
        <CopilotPage
          bundle={bundle}
          syncing={syncing}
          onSync={sync}
          onOpenView={setView}
          exchanges={convo.exchanges}
          ask={convo.ask}
          busy={convo.busy}
        />
      </main>
      <ThinkingBar exchanges={convo.exchanges} />
      <AnalyticsModal view={view} bundle={bundle} onClose={() => setView(null)} />
    </div>
  );
}
