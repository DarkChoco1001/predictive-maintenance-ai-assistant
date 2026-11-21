import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type EngineDetail as Detail, type FleetResponse, type WorkOrder } from "./api";
import { AssistantPanel } from "./components/AssistantPanel";
import { EngineDetail } from "./components/EngineDetail";
import { FleetGrid } from "./components/FleetGrid";
import { WorkOrders } from "./components/WorkOrders";

const START_CLOCK = 100;
const TICK_MS = 700;
const SPEEDS = [
  { label: "Slow", step: 1 },
  { label: "Normal", step: 3 },
  { label: "Fast", step: 6 },
];

export function App() {
  const [clock, setClock] = useState(START_CLOCK);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [fleet, setFleet] = useState<FleetResponse | null>(null);
  const [selectedId, setSelectedId] = useState(1);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [error, setError] = useState("");

  const maxClock = fleet?.max_clock ?? 300;

  // Advance the simulation clock while playing
  useEffect(() => {
    if (!playing) return;
    const step = SPEEDS[speed]?.step ?? 1;
    const id = window.setInterval(() => {
      setClock((c) => {
        const next = Math.min(c + step, maxClock);
        if (next >= maxClock) setPlaying(false);
        return next;
      });
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, [playing, speed, maxClock]);

  // Fetch fleet + selected engine for the current clock; cancel stale requests
  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([api.fleet(clock, ctrl.signal), api.engine(selectedId, clock, ctrl.signal)])
      .then(([f, d]) => {
        setFleet(f);
        setDetail(d);
        setError("");
      })
      .catch((e: unknown) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Could not load data.");
        setPlaying(false);
      });
    return () => ctrl.abort();
  }, [clock, selectedId]);

  const refreshOrders = useCallback(() => {
    api.workOrders().then(setOrders).catch(() => undefined);
  }, []);
  useEffect(refreshOrders, [refreshOrders]);

  const names = useMemo(() => new Map(fleet?.engines.map((e) => [e.id, e.name]) ?? []), [fleet]);

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <h1>Fleet Health Monitor</h1>
          <p>Predictive maintenance demo · NASA C-MAPSS turbofan sensor data replayed as a live stream</p>
        </div>
        <div className="controls" role="group" aria-label="Simulation controls">
          <button type="button" className="primary" onClick={() => setPlaying((p) => !p)} disabled={clock >= maxClock}>
            {playing ? "❚❚ Pause" : "▶ Play"}
          </button>
          <div className="seg" role="radiogroup" aria-label="Speed">
            {SPEEDS.map((s, i) => (
              <button key={s.label} type="button" role="radio" aria-checked={speed === i}
                      className={speed === i ? "on" : ""} onClick={() => setSpeed(i)}>{s.label}</button>
            ))}
          </div>
          <button type="button" onClick={() => { setPlaying(false); setClock(1); }}>Reset</button>
          <div className="clock" aria-live="off">
            <span className="clock-k">Simulation cycle</span>
            <span className="clock-v">{clock}<small> / {maxClock}</small></span>
          </div>
        </div>
      </header>

      {error && <p className="error banner" role="alert">{error}</p>}

      <main className="layout">
        <div className="col-left">
          {fleet && <FleetGrid engines={fleet.engines} selectedId={selectedId} onSelect={setSelectedId} />}
          <WorkOrders orders={orders} names={names} />
        </div>
        <div className="col-right">
          {detail && fleet && <EngineDetail detail={detail} alertHealth={fleet.alert_health} rulAlert={fleet.rul_alert} />}
          {detail && (
            <AssistantPanel engineId={selectedId} engineName={detail.summary.name} clock={clock}
                            onCreated={(o) => setOrders((prev) => [o, ...prev])} />
          )}
        </div>
      </main>

      <footer className="foot">
        Demo with simulated data (NASA C-MAPSS FD001). The FMEA and procedures are illustrative, not OEM guidance.
      </footer>
    </>
  );
}
