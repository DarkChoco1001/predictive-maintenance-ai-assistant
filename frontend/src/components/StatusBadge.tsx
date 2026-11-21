import type { Status } from "../api";

// Status is never shown by color alone: every state has an icon and a text label.
const META: Record<Status, { icon: string; label: string }> = {
  healthy: { icon: "✓", label: "Healthy" },
  watch: { icon: "!", label: "Watch" },
  alert: { icon: "▲", label: "Alert" },
  critical: { icon: "‼", label: "Critical" },
  failed: { icon: "✕", label: "Failed" },
};

export function StatusBadge({ status }: { status: Status }) {
  const m = META[status];
  return (
    <span className={`badge badge-${status}`}>
      <span className="badge-icon" aria-hidden="true">{m.icon}</span>
      {m.label}
    </span>
  );
}

export const STATUS_ORDER: Status[] = ["critical", "alert", "watch", "healthy", "failed"];
export const statusLabel = (s: Status) => META[s].label;
