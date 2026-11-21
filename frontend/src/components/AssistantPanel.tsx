import { useEffect, useState } from "react";
import { api, ApiError, type DiagnoseResponse, type WorkOrder } from "../api";

interface Props {
  engineId: number;
  engineName: string;
  clock: number;
  onCreated: (order: WorkOrder) => void;
}

const MAX_QUESTION = 500;
const PROVIDER_LABEL = { "offline-rules": "Offline rules + FMEA", anthropic: "Claude", ollama: "Local LLM (Ollama)" };

export function AssistantPanel({ engineId, engineName, clock, onCreated }: Props) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<DiagnoseResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<string>("");

  useEffect(() => {
    setResult(null);
    setError("");
    setCreated("");
  }, [engineId]);

  async function diagnose() {
    setBusy(true);
    setError("");
    setCreated("");
    try {
      setResult(await api.diagnose(engineId, clock, question.trim()));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the assistant.");
    } finally {
      setBusy(false);
    }
  }

  async function createOrder() {
    if (!result) return;
    setBusy(true);
    setError("");
    try {
      const order = await api.createWorkOrder(engineId, result.diagnosis.work_order);
      setCreated(order.id);
      onCreated(order);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the work order.");
    } finally {
      setBusy(false);
    }
  }

  const d = result?.diagnosis;
  const wo = d?.work_order;

  return (
    <section aria-labelledby="assistant-h" className="panel">
      <div className="section-head">
        <h2 id="assistant-h">Maintenance assistant</h2>
      </div>
      <p className="hint">Diagnoses {engineName} from its sensor data, the FMEA and the troubleshooting guide, then drafts a work order for you to approve.</p>

      <label htmlFor="question" className="field-label">Question for the assistant (optional)</label>
      <textarea id="question" value={question} maxLength={MAX_QUESTION} rows={2}
                placeholder="e.g. Can this engine fly two more days before inspection?"
                onChange={(e) => setQuestion(e.target.value.slice(0, MAX_QUESTION))} />
      <div className="row">
        <span className="hint">{question.length}/{MAX_QUESTION}</span>
        <button type="button" className="primary" onClick={diagnose} disabled={busy}>
          {busy && !result ? "Diagnosing…" : `Diagnose ${engineName}`}
        </button>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      {result && d && wo && (
        <div className="diagnosis" aria-live="polite">
          {result.notice && <p className="notice">{result.notice}</p>}
          <div className="diag-head">
            <div>
              <div className="diag-k">Likely failure mode</div>
              <div className="diag-mode">{d.failure_mode_name}</div>
            </div>
            <span className={`conf conf-${d.confidence}`}>{d.confidence} confidence</span>
          </div>
          <p>{d.summary}</p>

          <h3>Evidence</h3>
          <ul>{d.evidence.map((x, i) => <li key={i}>{x}</li>)}</ul>

          <h3>Recommended actions</h3>
          <ol>{d.recommended_actions.map((x, i) => <li key={i}>{x}</li>)}</ol>

          <div className="wo-draft">
            <div className="wo-head">
              <span className={`prio prio-${wo.priority}`}>{wo.priority}</span>
              <b>{wo.title}</b>
            </div>
            <p className="hint">Draft work order · plan within {wo.due_within_cycles} cycles{wo.parts.length ? ` · parts: ${wo.parts.join(", ")}` : ""}</p>
            {created ? (
              <p className="success" role="status">Work order {created} created.</p>
            ) : (
              <button type="button" className="primary" onClick={createOrder} disabled={busy}>Approve &amp; create work order</button>
            )}
          </div>

          <p className="sources">Sources: {result.sources.join(" · ")} · Engine: {PROVIDER_LABEL[result.provider] ?? result.provider}</p>
        </div>
      )}
    </section>
  );
}
