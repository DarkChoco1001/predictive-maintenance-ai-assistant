import { useState } from "react";
import type { EngineDetail as Detail } from "../api";
import { LineChart } from "./LineChart";
import { StatusBadge } from "./StatusBadge";

interface Props {
  detail: Detail;
  alertHealth: number;
  rulAlert: number;
}

export function EngineDetail({ detail, alertHealth, rulAlert }: Props) {
  const [showTable, setShowTable] = useState(false);
  const s = detail.summary;
  const failed = s.status === "failed";
  const rows = detail.cycles.map((c, i) => ({ c, h: detail.health[i] ?? 0, r: detail.rul_pred[i] ?? 0 })).slice(-25).reverse();
  const xMax = Math.max(...detail.cycles, 50);

  return (
    <section aria-labelledby="detail-h" className="panel">
      <div className="section-head">
        <h2 id="detail-h">{s.name}</h2>
        <StatusBadge status={s.status} />
      </div>

      <div className="tiles">
        <div className="tile"><div className="tile-k">Health index</div><div className="tile-v">{s.health.toFixed(0)}<small>/100</small></div></div>
        <div className="tile"><div className="tile-k">Predicted remaining life</div><div className="tile-v">{failed ? "–" : s.rul_pred.toFixed(0)}<small> cycles</small></div></div>
        <div className="tile"><div className="tile-k">Failure risk, next {rulAlert} cycles</div><div className="tile-v">{(s.fail_prob * 100).toFixed(0)}<small>%</small></div></div>
      </div>

      <LineChart title="Health index" unit="/ 100" x={detail.cycles} y={detail.health} yMax={100} tickStep={25} xDomainMax={xMax}
                 threshold={{ value: alertHealth, label: `Watch line (${alertHealth.toFixed(0)})` }} />
      <LineChart title="Predicted remaining useful life" unit="cycles" x={detail.cycles} y={detail.rul_pred} yMax={130} tickStep={30}
                 xDomainMax={xMax} threshold={{ value: rulAlert, label: `Alert line (${rulAlert} cycles)` }} />

      <h3>What the sensors show</h3>
      <ul className="devs">
        {detail.top_deviations.map((d) => (
          <li key={d.sensor}>
            <span className="dev-label">{d.label}</span>
            <span className="dev-bar" aria-hidden="true">
              <span className={`dev-fill ${d.z >= 0 ? "up" : "down"}`} style={{ width: `${Math.min(100, (Math.abs(d.z) / 6) * 100)}%` }} />
            </span>
            <span className="dev-v">{d.z >= 0 ? "▲" : "▼"} {Math.abs(d.z).toFixed(1)}σ</span>
          </li>
        ))}
      </ul>
      <p className="hint">σ = standard deviations away from a healthy engine's normal reading.</p>

      <button type="button" className="link" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}>
        {showTable ? "Hide data table" : "Show data table"}
      </button>
      {showTable && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Last 25 cycles for {s.name}</caption>
            <thead><tr><th scope="col">Cycle</th><th scope="col">Health</th><th scope="col">Predicted RUL</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.c}><td>{r.c}</td><td>{r.h.toFixed(1)}</td><td>{r.r.toFixed(1)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
