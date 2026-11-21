"""Replays the exported fleet as if engines were streaming data live.

A shared simulation clock drives all engines. Each engine has an offset, so engines
are at different life stages and their failures are spread out over the demo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schemas import EngineDetail, EngineSummary, FleetResponse, SensorDeviation, Status

DATA_FILE = Path(__file__).parent / "data" / "fleet.json"
PERSISTENCE = 5      # health must stay below the alert line this many cycles to raise "watch"
CRITICAL_RUL = 15


@dataclass(frozen=True)
class Engine:
    id: int
    name: str
    offset: int
    failure_cycle: int
    timeline: dict


class Fleet:
    def __init__(self, path: Path = DATA_FILE) -> None:
        raw = json.loads(path.read_text())
        meta = raw["meta"]
        self.alert_health: float = float(meta["alert_health"])
        self.rul_alert: int = int(meta["rul_alert"])
        self.sensor_names: dict[str, str] = dict(meta["sensor_names"])
        self.engines: dict[int, Engine] = {}
        for i, e in enumerate(raw["engines"]):
            target_failure_clock = 60 + 20 * i
            offset = max(0, int(e["failure_cycle"]) - target_failure_clock)
            self.engines[int(e["id"])] = Engine(int(e["id"]), str(e["name"]), offset,
                                                int(e["failure_cycle"]), e["timeline"])
        self.max_clock = max(e.failure_cycle - e.offset for e in self.engines.values()) + 10

    def _index(self, engine: Engine, clock: int) -> int:
        """Timeline index of the engine's latest cycle at this clock (-1 = past failure)."""
        cycle = min(clock + engine.offset, engine.failure_cycle + 1)
        return cycle - 1 if cycle <= engine.failure_cycle else -1

    def summary(self, engine: Engine, clock: int) -> EngineSummary:
        idx = self._index(engine, clock)
        t = engine.timeline
        if idx < 0:
            return EngineSummary(id=engine.id, name=engine.name, cycle=engine.failure_cycle,
                                 health=0.0, rul_pred=0.0, fail_prob=1.0, status="failed")
        return EngineSummary(id=engine.id, name=engine.name, cycle=t["cycle"][idx],
                             health=t["health"][idx], rul_pred=t["rul_pred"][idx],
                             fail_prob=t["fail_prob"][idx], status=self._status(engine, idx))

    def _status(self, engine: Engine, idx: int) -> Status:
        t = engine.timeline
        rul, prob = t["rul_pred"][idx], t["fail_prob"][idx]
        if rul <= CRITICAL_RUL:
            return "critical"
        if rul <= self.rul_alert or prob >= 0.5:
            return "alert"
        recent = t["health"][max(0, idx - PERSISTENCE + 1): idx + 1]
        if len(recent) == PERSISTENCE and all(h < self.alert_health for h in recent):
            return "watch"
        return "healthy"

    def get(self, engine_id: int) -> Engine | None:
        return self.engines.get(engine_id)

    def fleet(self, clock: int) -> FleetResponse:
        return FleetResponse(clock=clock, max_clock=self.max_clock, alert_health=self.alert_health,
                             rul_alert=self.rul_alert,
                             engines=[self.summary(e, clock) for e in self.engines.values()])

    def deviations(self, engine: Engine, clock: int, top: int = 4) -> list[SensorDeviation]:
        idx = self._index(engine, clock)
        idx = len(engine.timeline["cycle"]) - 1 if idx < 0 else idx
        devs = [SensorDeviation(sensor=s, label=self.sensor_names[s], z=float(engine.timeline["z"][s][idx]))
                for s in self.sensor_names]
        return sorted(devs, key=lambda d: abs(d.z), reverse=True)[:top]

    def detail(self, engine: Engine, clock: int) -> EngineDetail:
        idx = self._index(engine, clock)
        end = len(engine.timeline["cycle"]) if idx < 0 else idx + 1
        t = engine.timeline
        return EngineDetail(summary=self.summary(engine, clock), cycles=t["cycle"][:end],
                            health=t["health"][:end], rul_pred=t["rul_pred"][:end],
                            top_deviations=self.deviations(engine, clock))
