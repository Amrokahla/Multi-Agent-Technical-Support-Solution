import { useState } from "react";
import { useWfm } from "../hooks/useWfm";
import type { AnalyzeResult } from "../types";
import Masthead from "../components/Masthead";
import UploadBar from "../components/UploadBar";
import KpiStrip from "../components/KpiStrip";
import Stage from "../components/Stage";
import ForecastPanel from "../components/ForecastPanel";
import IntradayPanel from "../components/IntradayPanel";
import CoveragePanel from "../components/CoveragePanel";
import RealignmentPanel from "../components/RealignmentPanel";

// The workforce dashboard: one section per pipeline stage, hero -> KPIs ->
// forecast -> capacity -> coverage -> the reallocation plan. An uploaded CSV
// (or the sample) swaps the whole analysis in place.
export default function WorkforcePage() {
  const { data, error } = useWfm();
  const [upload, setUpload] = useState<AnalyzeResult | null>(null);

  if (error && !upload) {
    return (
      <div className="wfm-status err">
        Backend not reachable — {error}
        <br />
        Start it with: make dev (backend on port 8000)
      </div>
    );
  }

  const bundle = upload ?? data;
  if (!bundle) {
    return <div className="wfm-status">Running the workforce analysis…</div>;
  }

  const { summary, forecast, capacity, coverage, optimizer } = bundle;

  return (
    <>
      <Masthead s={summary} upload={upload?.meta ?? null} />
      <div className="wrap">
        <section className="stage" style={{ paddingTop: 28 }}>
          <UploadBar meta={upload?.meta ?? null} onLoaded={setUpload} onReset={() => setUpload(null)} />
        </section>

        <section className="stage" style={{ paddingTop: 24 }}>
          <KpiStrip s={summary} />
        </section>

        <Stage num="01" kicker="Demand" title="Forecasting the volume"
          note={<>The signal is <b>weekly seasonality</b>, and it's already captured.</>}>
          <ForecastPanel f={forecast} />
        </Stage>

        <Stage num="02" kicker="Capacity" title="Matching agents to the clock"
          note={<>Required agents vs who is actually <b>on shift</b>, hour by hour.</>}>
          <IntradayPanel c={capacity} />
        </Stage>

        <Stage num="03" kicker="Coverage" title="Where the roster breaks"
          note={<>The same headcount, but the <b>skill mix</b> is wrong.</>}>
          <CoveragePanel c={coverage} />
        </Stage>

        <Stage num="04" kicker="Optimize" title="The realignment"
          note={<>The minimal set of moves that closes the <b>gap</b>.</>}>
          <RealignmentPanel o={optimizer} />
        </Stage>
      </div>
    </>
  );
}
