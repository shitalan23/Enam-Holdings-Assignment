import type { Item } from "../api";

/** One tick per filing across the chosen window. Tall = needs you, short = routine.
 *  Shows at a glance when things happened and how dense the window is; tap a tick to jump. */
export function Ribbon({ items, from, to }: { items: Item[]; from: string; to: string }) {
  const a = new Date(from).getTime(), b = new Date(to).getTime(), span = Math.max(1, b - a);
  const fmt = (t: number) => new Date(t).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short" });
  const ticks = [...items].sort((x, y) => ({ skim: 0, know: 1, act: 2 }[x.tier] - { skim: 0, know: 1, act: 2 }[y.tier]));
  const isRecent = Math.abs(Date.now() - b) < 2 * 36e5;
  return (
    <div aria-label={`${items.length} filings over the selected window`} role="img">
      <div className="relative h-9 border-b border-ink/70">
        {ticks.map((i) => {
          const left = Math.min(99.6, Math.max(0, ((new Date(i.ts).getTime() - a) / span) * 100));
          const cls = i.tier === "act" ? "h-9 w-[3px] bg-accent" : i.tier === "know" ? "h-5 w-[2px] bg-ink/55" : "h-2.5 w-px bg-faint";
          return (
            <button key={i.id} aria-label={`${i.symbol} ${i.category_label}`} tabIndex={-1}
              onClick={() => document.getElementById(`it-${i.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
              className={`absolute bottom-0 ${cls}`} style={{ left: `${left}%` }} />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-[11.5px] text-mute">
        <span>{fmt(a)}</span>
        <span>{isRecent ? "Now" : fmt(b)}</span>
      </div>
    </div>
  );
}
