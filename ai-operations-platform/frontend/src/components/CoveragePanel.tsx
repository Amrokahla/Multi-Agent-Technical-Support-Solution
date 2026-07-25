import type { CoverageResult } from "../types";
import { gapColor, shortSkill, signed } from "../utils/format";

const shortName = shortSkill;

// Step 3 — skill x hour gap grid (rows ordered worst-first so the shortfall reads
// top-down), the per-skill totals, and the clients most exposed to it.
export default function CoveragePanel({ c }: { c: CoverageResult }) {
  const { hours, skills, values } = c.gap_matrix;
  const ordered = c.skills; // already sorted by gap ascending (worst first)
  const maxAbs = Math.max(...ordered.map((s) => Math.abs(s.gap)));
  const maxExposure = Math.max(...c.client_risk.map((r) => r.exposure));

  return (
    <>
      <div className="panel">
        <div className="panel-title">Coverage gap · skill × hour</div>
        <div className="heat">
          <div className="heat-row">
            <span />
            {hours.map((h) => (
              <span className="heat-hours" key={h}>
                {h % 3 === 0 ? String(h).padStart(2, "0") : ""}
              </span>
            ))}
          </div>
          {ordered.map((sk) => {
            const si = skills.indexOf(sk.skill);
            return (
              <div className="heat-row" key={sk.group_id}>
                <span className="heat-skill" title={sk.skill}>
                  {shortName(sk.skill)}
                </span>
                {hours.map((h) => (
                  <span
                    className="heat-cell"
                    key={h}
                    style={{ background: gapColor(values[h][si]) }}
                    title={`${sk.skill} · ${String(h).padStart(2, "0")}:00 · ${signed(values[h][si], 1)}`}
                  />
                ))}
              </div>
            );
          })}
        </div>
        <div className="heat-scale">
          <span>understaffed</span>
          <span className="ramp" />
          <span>surplus</span>
          <span style={{ marginLeft: "auto", color: "var(--muted)" }}>
            {c.understaffed_cells}/{c.total_cells} cells short · net {c.net_shortage_agent_hours} agent-h/day
          </span>
        </div>
      </div>

      <div className="split" style={{ marginTop: 14 }}>
        <div className="panel">
          <div className="panel-title">Per-skill balance · agent-hours/day</div>
          <div className="gaplist">
            {ordered.map((s) => {
              const w = (Math.abs(s.gap) / maxAbs) * 50;
              const short = s.gap < 0;
              return (
                <div className="gap-row" key={s.group_id}>
                  <span className="gap-name" title={s.skill}>
                    {shortName(s.skill)}
                  </span>
                  <span className="gap-track">
                    <span className="gap-mid" />
                    <span
                      className="gap-fill"
                      style={{
                        width: `${w}%`,
                        left: short ? `${50 - w}%` : "50%",
                        background: short ? "var(--deficit)" : "var(--signal)",
                      }}
                    />
                  </span>
                  <span className="gap-val" style={{ color: short ? "var(--deficit)" : "var(--signal)" }}>
                    {signed(s.gap, 0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Clients most exposed</div>
          <div className="risk">
            {c.client_risk.slice(0, 7).map((r) => (
              <div className="risk-row" key={r.organization_id}>
                <span className="risk-name">{r.client}</span>
                {r.dedicated && <span className="risk-tag">dedicated</span>}
                <span className="risk-bar" style={{ width: `${Math.max((r.exposure / maxExposure) * 90, 8)}px` }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
