import type { UploadMeta, WfmSummary } from "../types";
import { round, shortSkill } from "../utils/format";

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

// Hero states the thesis in words; the outcome readout is the proof. In upload
// mode the copy becomes data-driven (the frozen-demo thesis no longer applies).
export default function Masthead({ s, upload }: { s: WfmSummary; upload: UploadMeta | null }) {
  const o = s.optimizer;
  const worst = shortSkill(s.coverage.worst_skill);

  return (
    <header className="mast">
      <div className="mast-inner">
        <div>
          {upload ? (
            <>
              <div className="mast-eyebrow">
                <span className="dot" />
                Uploaded analysis
                <span>· {upload.tickets_used.toLocaleString()} tickets</span>
                <span>· {upload.date_start} → {upload.date_end}</span>
                <span>· {upload.scale_factor}× scale</span>
              </div>
              <h1 className="mast-title">
                Your demand, matched to a
                <br />
                <em>modeled roster</em>.
              </h1>
              <p className="mast-sub">
                Demand comes straight from your upload. Until real shifts are connected we model an
                even-baseline roster of <b>{upload.agents_modeled} agents</b> — the shortfall lands in{" "}
                <b>{worst}</b>, and the plan below is what closes it.
              </p>
            </>
          ) : (
            <>
              <div className="mast-eyebrow">
                <span className="dot" />
                Workforce Optimization
                <span>· analysed {fmtDate(s.as_of)}</span>
                <span>· {s.window_days}-day window</span>
                <span>· {s.scale_factor}× scale</span>
              </div>
              <h1 className="mast-title">
                Demand pools in two queues.
                <br />
                The roster is spread across <em>nine</em>.
              </h1>
              <p className="mast-sub">
                The demand forecast is already at its statistical floor — accuracy isn't the lever.
                The workforce's <b>skill mix</b> is. Here is where coverage breaks and the exact
                moves that fix it.
              </p>
            </>
          )}
        </div>

        <div className="mast-outcome">
          <div className="big">
            −{round(o.reduction_pct)}
            <small>%</small>
          </div>
          <div className="cap">unmet demand removed by reallocating the current roster</div>
          <div className="flow">
            <b>{round(o.unmet_before)}</b>
            <span className="arrow">→</span>
            <b>{round(o.unmet_after)}</b>
            <span>agent-h/day short · {o.moves} moves</span>
          </div>
        </div>
      </div>
    </header>
  );
}
