import { useState } from "react";
import type { Portfolio } from "../api";
import { Badge, detail } from "./Badge";
import { Spark } from "./Spark";
import { day, pct, price, sign } from "../format";

type Sort = "weight" | "move" | "volume";
// Phone: name | trend | move+close | volume.  Tablet/desktop adds sector and filings columns.
const GRID = "grid grid-cols-[minmax(0,1fr)_50px_72px_42px] sm:grid-cols-[minmax(0,1fr)_56px_78px_46px] md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_104px_96px_84px_minmax(0,1.1fr)] items-center gap-x-2 sm:gap-x-3 md:gap-x-5";

export function PortfolioView({ data, error, onOpen, onRetry }: { data: Portfolio | null; error: string | null; onOpen: (s: string) => void; onRetry: () => void }) {
  const [sort, setSort] = useState<Sort>("weight");
  if (error) return (
    <div className="py-10"><p className="font-semibold">Couldn't load the portfolio.</p>
      <p className="mt-1 text-sm text-mute">The FINN server didn't respond ({error}).</p>
      <button onClick={onRetry} className="mt-3 rounded-[3px] border border-ink px-3 py-1.5 text-sm font-medium">Try again</button></div>);
  if (!data) return <p className="py-10 text-mute">Loading holdings…</p>;

  const h = [...data.holdings].sort((a, b) =>
    sort === "weight" ? b.weight - a.weight
    : sort === "move" ? Math.abs(b.stats?.pct ?? 0) - Math.abs(a.stats?.pct ?? 0)
    : (b.stats?.vol_x ?? 0) - (a.stats?.vol_x ?? 0));
  const flagged = data.holdings.filter((x) => x.flags.price || x.flags.volume).length;
  const t = data.status.thresholds, px = data.status.prices;
  const asOf = data.holdings.find((x) => x.stats)?.stats?.date;

  return (
    <div>
      <div className="pb-4 pt-5 lg:pt-6">
        <h1 className="text-[24px] font-semibold leading-[1.15] tracking-[-0.01em] sm:text-[26px] md:text-[30px]">
          {asOf ? (flagged ? `${flagged} ${flagged === 1 ? "holding" : "holdings"} moved unusually.` : "Nothing unusual in the last session.") : "No prices loaded yet."}
        </h1>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] sm:text-[13.5px] text-mute">
          {asOf ? <>Close for {day(asOf)} <Badge status={px.status} detail={detail(px)} small /> Flagged beyond ±{t.price_move_pct}% or {t.volume_mult}× average volume. Not intraday.</>
            : "Run the price ingest to load end-of-day data."}
        </p>
      </div>
      <div role="group" aria-label="Sort holdings" className="flex border-b border-rule text-[13px] overflow-x-auto no-scrollbar">
        {([["weight", "Weight"], ["move", "Biggest move"], ["volume", "Volume spike"]] as [Sort, string][]).map(([k, l]) => (
          <button key={k} aria-pressed={sort === k} onClick={() => setSort(k)}
            className={`-mb-px mr-4 shrink-0 border-b-2 py-2 transition-colors ${sort === k ? "border-accent font-semibold text-ink" : "border-transparent text-mute hover:text-ink"}`}>{l}</button>
        ))}
      </div>
      <div className={`${GRID} hidden border-b border-rule py-2 pl-3 text-[12.5px] text-mute md:grid`} aria-hidden="true">
        <span>Holding</span><span>Sector</span><span>30 days</span><span className="text-right">Day move · close</span>
        <span className="text-right">Volume vs avg</span><span>Filings, last 7 days</span>
      </div>
      <ul>
        {h.map((x) => {
          const s = x.stats, hot = x.flags.price || x.flags.volume, f = x.filings_7d;
          return (
            <li key={x.symbol}>
              <button onClick={() => onOpen(x.symbol)} className={`${GRID} w-full border-b border-rule py-3 pl-3 text-left hover:bg-raised ${hot ? "border-l-[4px] border-l-accent" : "border-l-2 border-l-transparent"}`}
                aria-label={`${x.name}. ${f.act} need you, ${f.know} worth knowing in the last 7 days. Open filings.`}>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[15px] font-semibold">{x.symbol}
                    {f.act > 0 && <span title={`${f.act} need you`} className="h-1.5 w-1.5 rounded-full bg-accent md:hidden" />}
                    <span className="text-[12px] font-normal text-faint">{x.weight}%</span></span>
                  <span className="block truncate text-[12.5px] text-mute">{x.name}</span>
                </span>
                <span className="hidden truncate text-[13px] text-mute md:block">{x.sector}<span className="block text-faint">{x.size} cap</span></span>
                <Spark data={x.spark} />
                <span className="text-right">
                  <span className={`block text-[15px] ${x.flags.price ? "font-bold" : "font-medium"} ${sign(s?.pct)}`}>{pct(s?.pct)}</span>
                  <span className="block text-[12px] text-mute">{s ? price(s.close) : "—"}</span>
                </span>
                <span className={`text-right text-[13px] ${x.flags.volume ? "font-bold text-accent" : "text-mute"}`}>{s?.vol_x != null ? `${s.vol_x.toFixed(1)}×` : "—"}</span>
                <span className="hidden text-[13px] md:block">
                  {f.act + f.know + f.skim === 0 ? <span className="text-faint">None</span> : <>
                    {f.act > 0 && <b className="mr-2 font-semibold text-accent">{f.act} need{f.act === 1 ? "s" : ""} you</b>}
                    {f.know > 0 && <span className="mr-2">{f.know} to know</span>}
                    {f.skim > 0 && <span className="text-faint">{f.skim} routine</span>}</>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="py-4 text-[12.5px] text-faint md:hidden">Dot: a filing in the last 7 days needs you. Right column: volume against its 20-day average. Tap a holding to see its filings.</p>
    </div>
  );
}
