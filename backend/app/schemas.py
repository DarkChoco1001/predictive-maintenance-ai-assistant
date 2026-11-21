"""Request and response models.

All input is validated with strict types, ranges and length limits, and unknown fields
are rejected (OWASP A03 Injection, A04 Insecure Design).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_text(value: str) -> str:
    """Reject control characters (log/header injection) and trim whitespace."""
    if _CONTROL_CHARS.search(value):
        raise ValueError("contains control characters")
    return value.strip()


def Text(max_len: int, min_len: int = 0):  # noqa: N802 - reads like a type
    return Annotated[str, Field(min_length=min_len, max_length=max_len), AfterValidator(_clean_text)]


Status = Literal["healthy", "watch", "alert", "critical", "failed"]
Priority = Literal["P1", "P2", "P3", "P4"]
FailureModeId = Literal["HPC-EFF", "HPC-FLOW", "HPT-WEAR", "FAN-DMG", "SENSOR"]
EngineId = Annotated[int, Field(ge=1, le=99)]
Clock = Annotated[int, Field(ge=1, le=400)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- Fleet ----------
class EngineSummary(Strict):
    id: int
    name: str
    cycle: int
    health: float
    rul_pred: float
    fail_prob: float
    status: Status


class FleetResponse(Strict):
    clock: int
    max_clock: int
    alert_health: float
    rul_alert: int
    engines: list[EngineSummary]


class SensorDeviation(Strict):
    sensor: str
    label: str
    z: float


class EngineDetail(Strict):
    summary: EngineSummary
    cycles: list[int]
    health: list[float]
    rul_pred: list[float]
    top_deviations: list[SensorDeviation]


# ---------- Assistant ----------
class DiagnoseRequest(Strict):
    engine_id: EngineId
    clock: Clock
    question: Text(500) = ""


class WorkOrderDraft(Strict):
    title: Text(120, 5)
    priority: Priority
    description: Text(2000, 1)
    actions: Annotated[list[Text(300, 1)], Field(min_length=1, max_length=8)]
    parts: Annotated[list[Text(120, 1)], Field(max_length=8)] = []
    due_within_cycles: Annotated[int, Field(ge=0, le=400)]


class Diagnosis(Strict):
    likely_failure_mode: FailureModeId
    failure_mode_name: Text(120, 1)
    confidence: Literal["low", "medium", "high"]
    summary: Text(1200, 1)
    evidence: Annotated[list[Text(300, 1)], Field(max_length=8)]
    recommended_actions: Annotated[list[Text(300, 1)], Field(min_length=1, max_length=8)]
    work_order: WorkOrderDraft


class DiagnoseResponse(Strict):
    engine: EngineSummary
    diagnosis: Diagnosis
    sources: list[str]
    provider: Literal["offline-rules", "anthropic", "ollama"]
    notice: str = ""


# ---------- Work orders ----------
class WorkOrderCreate(WorkOrderDraft):
    engine_id: EngineId


class WorkOrder(WorkOrderCreate):
    id: str
    status: Literal["open"]
    created_at: datetime
