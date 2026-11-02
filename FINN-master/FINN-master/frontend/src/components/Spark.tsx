/** Scales to its container width (56px on phones, wider on desktop) via CSS classes. */
export function Spark({ data, className = "w-14 md:w-[88px]" }: { data: number[]; className?: string }) {
  if (data.length < 2) return <span className="text-xs text-faint">—</span>;
  const W = 100, H = 24, lo = Math.min(...data), hi = Math.max(...data), r = hi - lo || 1;
  const pts = data.map((v, i) => `${((i / (data.length - 1)) * (W - 2) + 1).toFixed(1)},${(H - 2 - ((v - lo) / r) * (H - 4)).toFixed(1)}`).join(" ");
  const up = data[data.length - 1] >= data[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true" className={`h-[22px] ${className}`}>
      <polyline points={pts} fill="none" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"
        vectorEffect="non-scaling-stroke" className={up ? "stroke-up" : "stroke-down"} />
    </svg>
  );
}
