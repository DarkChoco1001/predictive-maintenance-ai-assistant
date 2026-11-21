import { useEffect, useRef, useState } from "react";

interface Props {
  title: string;
  unit: string;
  x: number[];
  y: number[];
  yMax: number;
  threshold?: { value: number; label: string };
  xDomainMax?: number;
  tickStep: number;
}

const H = 220;
const M = { top: 16, right: 16, bottom: 30, left: 44 };

/** Single-series line chart: one y-axis, recessive grid, crosshair tooltip on hover. */
export function LineChart({ title, unit, x, y, yMax, threshold, xDomainMax, tickStep }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [W, setW] = useState(640);

  // Draw at the real pixel width so axis text stays readable on small screens
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      if (entry) setW(Math.max(260, Math.round(entry.contentRect.width)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const x0 = x[0] ?? 1;
  const x1 = Math.max(xDomainMax ?? x[x.length - 1] ?? x0 + 1, x0 + 1);
  const sx = (v: number) => M.left + ((v - x0) / (x1 - x0)) * (W - M.left - M.right);
  const sy = (v: number) => M.top + (1 - Math.min(Math.max(v, 0), yMax) / yMax) * (H - M.top - M.bottom);

  const path = x.map((xi, i) => `${i === 0 ? "M" : "L"}${sx(xi).toFixed(1)},${sy(y[i] ?? 0).toFixed(1)}`).join("");
  const yTicks = Array.from({ length: Math.floor(yMax / tickStep) + 1 }, (_, i) => i * tickStep);
  const nx = W < 420 ? 3 : 5;
  const xTicks = Array.from({ length: nx }, (_, i) => Math.round(x0 + (i / (nx - 1)) * (x1 - x0)));

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const svg = svgRef.current;
    if (!svg || x.length === 0) return;
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const cycle = x0 + ((px - M.left) / (W - M.left - M.right)) * (x1 - x0);
    let best = 0;
    for (let i = 1; i < x.length; i++) {
      if (Math.abs((x[i] ?? 0) - cycle) < Math.abs((x[best] ?? 0) - cycle)) best = i;
    }
    setHover(best);
  }

  const hx = hover !== null ? x[hover] : undefined;
  const hy = hover !== null ? y[hover] : undefined;
  const last = y.length ? y[y.length - 1] : undefined;

  return (
    <figure className="chart">
      <figcaption>
        <span className="chart-title">{title}</span>
        {last !== undefined && <span className="chart-value">{last.toFixed(0)} {unit}</span>}
      </figcaption>
      <div className="chart-wrap" ref={wrapRef}>
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img"
             aria-label={`${title} over ${x.length} cycles. Latest value ${last?.toFixed(0) ?? "none"} ${unit}.`}>
          {yTicks.map((t) => (
            <g key={t}>
              <line className="grid" x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} />
              <text className="tick" x={M.left - 8} y={sy(t) + 4} textAnchor="end">{t}</text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} className="tick" x={sx(t)} y={H - 8} textAnchor="middle">{t}</text>
          ))}
          <text className="tick" x={W - M.right} y={H - 8} textAnchor="end" dy="-14">cycle</text>
          {threshold && (
            <g>
              <line className="threshold" x1={M.left} x2={W - M.right} y1={sy(threshold.value)} y2={sy(threshold.value)} />
              <text className="threshold-label" x={M.left + 6} y={sy(threshold.value) + 14} textAnchor="start">
                {threshold.label}
              </text>
            </g>
          )}
          <path className="series" d={path} />
          {hx !== undefined && hy !== undefined && (
            <g>
              <line className="crosshair" x1={sx(hx)} x2={sx(hx)} y1={M.top} y2={H - M.bottom} />
              <circle className="marker" cx={sx(hx)} cy={sy(hy)} r={5} />
            </g>
          )}
          <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom}
                fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
        </svg>
        {hx !== undefined && hy !== undefined && (
          <div className="tooltip" style={{ left: `${(sx(hx) / W) * 100}%`, top: `${(sy(hy) / H) * 100}%` }}>
            <div className="tooltip-k">Cycle {hx}</div>
            <div className="tooltip-v">{hy.toFixed(1)} {unit}</div>
          </div>
        )}
      </div>
    </figure>
  );
}
