import type { WorkOrder } from "../api";

export function WorkOrders({ orders, names }: { orders: WorkOrder[]; names: Map<number, string> }) {
  return (
    <section aria-labelledby="wo-h" className="panel">
      <div className="section-head"><h2 id="wo-h">Work orders</h2></div>
      {orders.length === 0 ? (
        <p className="hint">No work orders yet. Diagnose an engine and approve its draft to create one.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">ID</th><th scope="col">Engine</th><th scope="col">Priority</th><th scope="col">Title</th><th scope="col">Due (cycles)</th><th scope="col">Created</th></tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td className="mono">{o.id}</td>
                  <td>{names.get(o.engine_id) ?? o.engine_id}</td>
                  <td><span className={`prio prio-${o.priority}`}>{o.priority}</span></td>
                  <td>{o.title}</td>
                  <td>{o.due_within_cycles}</td>
                  <td>{new Date(o.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
