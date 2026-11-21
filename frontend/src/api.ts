// Typed API client.
// - Same-origin relative URLs only: no API host or secret lives in the browser bundle.
// - Every request has a timeout and can be cancelled.
// - Responses are shape-checked before use (never trust the network blindly).
// - State-changing requests send the CSRF header the backend requires.

export type Status = "healthy" | "watch" | "alert" | "critical" | "failed";
export type Priority = "P1" | "P2" | "P3" | "P4";

export interface EngineSummary {
  id: number;
  name: string;
  cycle: number;
  health: number;
  rul_pred: number;
  fail_prob: number;
  status: Status;
}

export interface FleetResponse {
  clock: number;
  max_clock: number;
  alert_health: number;
  rul_alert: number;
  engines: EngineSummary[];
}

export interface SensorDeviation {
  sensor: string;
  label: string;
  z: number;
}

export interface EngineDetail {
  summary: EngineSummary;
  cycles: number[];
  health: number[];
  rul_pred: number[];
  top_deviations: SensorDeviation[];
}

export interface WorkOrderDraft {
  title: string;
  priority: Priority;
  description: string;
  actions: string[];
  parts: string[];
  due_within_cycles: number;
}

export interface Diagnosis {
  likely_failure_mode: string;
  failure_mode_name: string;
  confidence: "low" | "medium" | "high";
  summary: string;
  evidence: string[];
  recommended_actions: string[];
  work_order: WorkOrderDraft;
}

export interface DiagnoseResponse {
  engine: EngineSummary;
  diagnosis: Diagnosis;
  sources: string[];
  provider: "offline-rules" | "anthropic" | "ollama";
  notice: string;
}

export interface WorkOrder extends WorkOrderDraft {
  id: string;
  engine_id: number;
  status: "open";
  created_at: string;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

const TIMEOUT_MS = 60_000;
const CSRF_HEADER = { "X-Requested-With": "pdm-demo" };

async function request<T>(path: string, check: (v: unknown) => v is T, init: RequestInit = {},
                          signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  const res = await fetch(path, {
    ...init,
    credentials: "same-origin",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!res.ok) {
    // Show friendly messages only; details stay in server logs
    const message = res.status === 429 ? "Too many requests. Please wait a minute and try again."
      : res.status === 422 ? "Some input was not valid. Please check and try again."
      : "Something went wrong. Please try again.";
    throw new ApiError(message, res.status);
  }
  const data: unknown = await res.json();
  if (!check(data)) throw new ApiError("Unexpected response from server.", 502);
  return data;
}

// ---- Shape checks ----
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const isStrArr = (v: unknown): v is string[] => Array.isArray(v) && v.every(isStr);
const STATUSES: readonly string[] = ["healthy", "watch", "alert", "critical", "failed"];

function isSummary(v: unknown): v is EngineSummary {
  return isObj(v) && isNum(v.id) && isStr(v.name) && isNum(v.cycle) && isNum(v.health)
    && isNum(v.rul_pred) && isNum(v.fail_prob) && isStr(v.status) && STATUSES.includes(v.status);
}

function isFleet(v: unknown): v is FleetResponse {
  return isObj(v) && isNum(v.clock) && isNum(v.max_clock) && isNum(v.alert_health)
    && isNum(v.rul_alert) && Array.isArray(v.engines) && v.engines.every(isSummary);
}

function isDetail(v: unknown): v is EngineDetail {
  return isObj(v) && isSummary(v.summary) && Array.isArray(v.cycles) && v.cycles.every(isNum)
    && Array.isArray(v.health) && v.health.every(isNum) && Array.isArray(v.rul_pred)
    && v.rul_pred.every(isNum) && Array.isArray(v.top_deviations)
    && v.top_deviations.every((d) => isObj(d) && isStr(d.label) && isNum(d.z));
}

function isDraft(v: unknown): v is WorkOrderDraft {
  return isObj(v) && isStr(v.title) && isStr(v.priority) && isStr(v.description)
    && isStrArr(v.actions) && isStrArr(v.parts) && isNum(v.due_within_cycles);
}

function isDiagnose(v: unknown): v is DiagnoseResponse {
  if (!isObj(v) || !isSummary(v.engine) || !isStrArr(v.sources) || !isStr(v.provider)) return false;
  const d = v.diagnosis;
  return isObj(d) && isStr(d.failure_mode_name) && isStr(d.summary) && isStr(d.confidence)
    && isStrArr(d.evidence) && isStrArr(d.recommended_actions) && isDraft(d.work_order);
}

function isWorkOrder(v: unknown): v is WorkOrder {
  return isDraft(v) && isObj(v) && isStr(v.id) && isNum(v.engine_id) && isStr(v.created_at);
}

const isWorkOrders = (v: unknown): v is WorkOrder[] => Array.isArray(v) && v.every(isWorkOrder);

// ---- Endpoints ----
const int = (n: number) => String(Math.trunc(n));

export const api = {
  fleet: (clock: number, signal?: AbortSignal) =>
    request(`/api/fleet?clock=${int(clock)}`, isFleet, {}, signal),

  engine: (id: number, clock: number, signal?: AbortSignal) =>
    request(`/api/engines/${int(id)}?clock=${int(clock)}`, isDetail, {}, signal),

  diagnose: (engineId: number, clock: number, question: string) =>
    request("/api/assistant/diagnose", isDiagnose, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...CSRF_HEADER },
      body: JSON.stringify({ engine_id: engineId, clock, question: question.slice(0, 500) }),
    }),

  workOrders: () => request("/api/work-orders", isWorkOrders),

  createWorkOrder: (engineId: number, draft: WorkOrderDraft) =>
    request("/api/work-orders", isWorkOrder, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...CSRF_HEADER },
      body: JSON.stringify({ engine_id: engineId, ...draft }),
    }),
};
