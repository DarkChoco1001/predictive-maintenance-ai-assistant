import type { EngineSummary, Status } from "../api";
import { STATUS_ORDER, StatusBadge, statusLabel } from "./StatusBadge";

interface Props {
  engines: EngineSummary[];
  selectedId: number;
  onSelect: (id: number) => void;
}

export function FleetGrid({ engines, selectedId, onSelect }: Props) {
  const counts = engines.reduce<Record<string, number>>((acc, e) => {
    acc[e.status] = (acc[e.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section aria-labelledby="fleet-h">
      <div className="section-head">
        <h2 id="fleet-h">Fleet</h2>
        <ul className="counts" aria-label="Engines by status">
          {STATUS_ORDER.filter((s) => counts[s]).map((s: Status) => (
            <li key={s} className={`count count-${s}`}>
              <span className="count-n">{counts[s]}</span> {statusLabel(s)}
            </li>
          ))}
        </ul>
      </div>
      <div className="fleet-grid">
        {engines.map((e) => (
          <button key={e.id} type="button" className={`engine-card status-${e.status}`}
                  aria-pressed={e.id === selectedId} onClick={() => onSelect(e.id)}>
            <div className="engine-card-top">
              <span className="engine-name">{e.name}</span>
              <StatusBadge status={e.status} />
            </div>
            <div className="meter" aria-label={`Health ${e.health.toFixed(0)} out of 100`}>
              <div className="meter-fill" style={{ width: `${Math.max(2, e.health)}%` }} />
            </div>
            <div className="engine-card-stats">
              <span>Health <b>{e.health.toFixed(0)}</b></span>
              <span>RUL <b>{e.status === "failed" ? "–" : e.rul_pred.toFixed(0)}</b></span>
              <span>Cycle <b>{e.cycle}</b></span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
