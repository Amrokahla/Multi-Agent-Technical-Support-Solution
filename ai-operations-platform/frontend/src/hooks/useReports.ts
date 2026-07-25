import { useCallback, useState } from "react";
import { api } from "../services/api";
import type { ReportsBundle } from "../types";

// Reports are generated on command (Sync) and cached; the chat + tabs read them.
export function useReports() {
  const [bundle, setBundle] = useState<ReportsBundle | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      setBundle(await api.syncReports());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncing(false);
    }
  }, []);

  return { bundle, syncing, error, sync };
}
