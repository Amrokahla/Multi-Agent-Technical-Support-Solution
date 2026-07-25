import type { CSSProperties } from "react";
import type { OptimizerResult, Recommendation } from "../types";
import { useInView } from "../hooks/useInView";
import { round, shortSkill, tightSkill } from "../utils/format";

// Step 4 — the signature. Each skill shows current supply (before) and the
// optimized supply (after), which animates from before -> demand on scroll-in:
// the roster visibly snapping into alignment. Then the exact moves to make it so.
export default function RealignmentPanel({ o }: { o: OptimizerResult }) {
  const { ref, inView } = useInView<HTMLDivElement>(0.25);
  const maxVal = Math.max(...o.skills.flatMap((s) => [s.demand, s.before, s.after]));
  const pct = (v: number) => `${(v / maxVal) * 100}%`;

  const half = Math.ceil(o.recommendations.length / 2);
  const columns = [o.recommendations.slice(0, half), o.recommendations.slice(half)];

  return (
    <>
      <div className="panel" ref={ref}>
        <div className="panel-title">Supply vs demand · before → after</div>
        <div className="rz-legend">
          <span>
            <i style={{ background: "rgba(199,123,114,0.42)", border: "1px solid rgba(199,123,114,0.6)" }} />
            current supply
          </span>
          <span>
            <i style={{ background: "rgba(134,185,176,0.75)" }} />
            optimized supply
          </span>
          <span>
            <i className="tick" />
            demand target
          </span>
        </div>

        <div className="rz">
          {o.skills.map((s) => {
            const delta = round(s.after - s.before);
            return (
              <div className="rz-row" key={s.group_id}>
                <span className="rz-name" title={s.skill}>
                  {shortSkill(s.skill)}
                </span>
                <span className="rz-track">
                  <span className="rz-bar rz-before" style={{ width: pct(s.before) }} />
                  {/* Resting width is always the final (after) value; the observer
                      only replays the grow-from-before animation on scroll-in. */}
                  <span
                    className={`rz-bar rz-after${inView ? " play" : ""}`}
                    style={{ width: pct(s.after), "--from": pct(s.before) } as CSSProperties}
                  />
                  <span className="rz-demand" style={{ left: pct(s.demand) }} />
                </span>
                <span className="rz-delta">
                  {delta > 0 ? (
                    <>
                      <b>+{delta}h</b> added
                    </>
                  ) : (
                    <span style={{ color: "var(--faint)" }}>{delta}h freed</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 14 }}>
        <div className="panel-title" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>Reassignment plan · {o.moves} moves</span>
          <span className="legend">
            <span>
              <i style={{ background: "rgba(134,185,176,0.5)" }} />
              {o.reassign} reassign
            </span>
            <span>
              <i style={{ background: "rgba(194,160,104,0.5)" }} />
              {o.cross_train} cross-train
            </span>
          </span>
        </div>
        <div className="recs-grid">
          {columns.map((col, ci) => (
            <PlanTable key={ci} rows={col} />
          ))}
        </div>
        <p className="recs-foot">
          Every move keeps the agent's timezone and client priority. Most land in{" "}
          <b>{Object.keys(o.moves_into)[0] && shortSkill(Object.keys(o.moves_into)[0])}</b> — unmet
          demand falls <b>{round(o.unmet_before)} → {round(o.unmet_after)}</b> agent-h/day (−
          {round(o.reduction_pct)}%).
        </p>
      </div>
    </>
  );
}

function PlanTable({ rows }: { rows: Recommendation[] }) {
  return (
    <table className="recs">
      <thead>
        <tr>
          <th>Agent</th>
          <th>Move</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.agent_id}>
            <td className="agent">#{r.agent_id}</td>
            <td>
              <span className="move">
                {tightSkill(r.from_skill)} <span className="arrow">→</span> {tightSkill(r.to_skill)}
              </span>
            </td>
            <td>
              <span className={`chip ${r.type === "reassign" ? "reassign" : "train"}`}>
                {r.type === "reassign" ? "reassign" : "cross-train"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
