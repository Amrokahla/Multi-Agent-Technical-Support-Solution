import type { ForecastResult } from "../types";
import { percentile, toPoints, WEEKDAYS } from "../utils/format";

const W = 640;
const H = 210;
const PAD = 12;

// Step 1 — actual vs forecast over the held-out second half, plus the weekday
// profile that carries the signal and the three-model bake-off.
export default function ForecastPanel({ f }: { f: ForecastResult }) {
  const actual = f.backtest.map((b) => b.actual);
  const forecast = f.backtest.map((b) => b.forecast);
  // Robust scale: one boundary-day outlier (~59 vs ~22 mean) would otherwise
  // flatten the whole series. Cap the axis near p97 and clamp that point.
  const hi = Math.max(percentile([...actual, ...forecast], 0.97), 30) * 1.08;
  const cap = (v: number) => Math.min(v, hi);

  const actualPts = toPoints(actual.map(cap), W, H, PAD, 0, hi);
  const forecastPts = toPoints(forecast.map(cap), W, H, PAD, 0, hi);
  const gridYs = [0.25, 0.5, 0.75].map((g) => PAD + (H - PAD * 2) * g);

  const wkMax = Math.max(...f.weekday_profile);

  return (
    <div className="split">
      <div className="panel">
        <div className="panel-title" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>Daily demand · H2 backtest</span>
          <span className="legend">
            <span>
              <i style={{ background: "var(--demand)" }} />
              actual
            </span>
            <span>
              <i style={{ background: "var(--signal)" }} />
              forecast
            </span>
          </span>
        </div>
        <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
          aria-label="Actual versus forecast daily ticket demand over the backtest window">
          {gridYs.map((y, i) => (
            <line key={i} className="gridline" x1={0} y1={y} x2={W} y2={y} />
          ))}
          <polyline points={actualPts} fill="none" stroke="var(--demand)" strokeWidth={1.4} opacity={0.7} />
          <polyline points={forecastPts} fill="none" stroke="var(--signal)" strokeWidth={2} />
        </svg>
        <p className="chart-caption">
          Trained on the first six months, tested on the last six. Gradient boosting lands at{" "}
          <b>{f.mean_per_day}</b> tickets/day mean demand.
        </p>
      </div>

      <div className="panel">
        <div className="panel-title">Model bake-off</div>
        <div className="models">
          {f.models.map((m) => (
            <div className={`model${m.model === f.chosen_model ? " win" : ""}`} key={m.model}>
              <span className="model-name">{m.model}</span>
              <span className="model-mae">
                MAE <b>{m.mae}</b>
              </span>
            </div>
          ))}
        </div>
        <div className="floor-note">
          MAE sits on the Poisson noise floor of <b>{f.noise_floor_mae}</b>. The weekly signal is
          fully captured — no model does better. So the lever isn't the forecast.
        </div>

        <div className="panel-title" style={{ margin: "18px 0 10px" }}>
          Weekday profile
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 54 }}>
          {f.weekday_profile.map((v, i) => (
            <div key={i} style={{ flex: 1, textAlign: "center" }}>
              <div
                style={{
                  height: `${(v / wkMax) * 44}px`,
                  background: i >= 5 ? "var(--grid)" : "var(--signal)",
                  borderRadius: 3,
                  opacity: i >= 5 ? 1 : 0.85,
                }}
                title={`${WEEKDAYS[i]}: ${v}`}
              />
              <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--faint)", marginTop: 5 }}>
                {WEEKDAYS[i][0]}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
