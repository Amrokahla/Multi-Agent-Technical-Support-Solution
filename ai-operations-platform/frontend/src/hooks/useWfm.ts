import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { WfmBundle } from "../types";

type State = { data: WfmBundle | null; error: string | null };

// Loads the full workforce analysis (all four stages) in one pass.
export function useWfm(): State {
  const [state, setState] = useState<State>({ data: null, error: null });

  useEffect(() => {
    let active = true;
    api
      .wfmBundle()
      .then((data) => active && setState({ data, error: null }))
      .catch((e) => active && setState({ data: null, error: String(e) }));
    return () => {
      active = false;
    };
  }, []);

  return state;
}
