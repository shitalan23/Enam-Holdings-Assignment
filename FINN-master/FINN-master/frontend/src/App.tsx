import { useCallback, useEffect, useState } from "react";
import { api, type Brief, type Portfolio, type Status } from "./api";
import { BriefView, type Win } from "./components/BriefView";
import { PortfolioView } from "./components/PortfolioView";
import { ResearchView } from "./components/ResearchView";
import { StatusSheet } from "./components/StatusSheet";
import { Badge, detail } from "./components/Badge";

type Tab = "brief" | "portfolio" | "research";
const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
// One content width for the whole app. Mobile: full width. Tablet: padded. Desktop: 1120px.
export const WRAP = "mx-auto w-full max-w-[1120px] px-4 md:px-6 lg:px-8";
const TABS: [Tab, string][] = [["brief", "Brief"], ["portfolio", "Portfolio"], ["research", "Research"]];

export default function App() {
  const [tab, setTab] = useState<Tab>("brief");
  const [win, setWin] = useState<Win>("24h");
  const [range, setRange] = useState({ from: iso(new Date(Date.now() - 7 * 864e5)), to: iso(new Date()) });
  const [symbol, setSymbol] = useState<string | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [briefErr, setBriefErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [pfErr, setPfErr] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [sheet, setSheet] = useState(false);

  useEffect(() => {
    api.status().then((s) => {
      setStatus(s);
      if (s.announcements.as_of) {
        const toD = s.announcements.as_of.slice(0, 10);
        const fromD = new Date(new Date(toD + "T00:00:00Z").getTime() - 7 * 864e5).toISOString().slice(0, 10);
        setRange({ from: fromD, to: toD });
      }
    }).catch(() => {});
  }, []);

  const loadBrief = useCallback(() => {
    const qs = new URLSearchParams();
    if (win === "custom") { qs.set("from_ts", range.from); qs.set("to_ts", range.to); } else qs.set("window", win);
    if (symbol) qs.set("symbol", symbol);
    let live = true;
    setLoading(true); setBriefErr(null);
    api.brief(qs).then((b) => { if (live) { setBrief(b); setStatus(b.status); } })
      .catch((e) => live && setBriefErr(String(e.message ?? e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [win, range, symbol]);
  useEffect(loadBrief, [loadBrief]);

  const loadPf = useCallback(() => {
    setPfErr(null);
    api.portfolio().then((p) => { setPf(p); setStatus(p.status); }).catch((e) => setPfErr(String(e.message ?? e)));
  }, []);
  useEffect(() => { if (tab === "portfolio") loadPf(); }, [tab, loadPf]);

  const openCompany = (s: string) => { setSymbol(s); setWin("7d"); setTab("brief"); window.scrollTo({ top: 0 }); };
  const go = (k: Tab) => { setTab(k); window.scrollTo({ top: 0 }); };
  const anyMock = status && (status.prices.status === "MOCK" || status.announcements.status === "MOCK");

  return (
    <div className="min-h-full overflow-x-hidden">
      <header className="sticky top-0 z-30 border-b border-rule bg-paper pt-[env(safe-area-inset-top)]">
        <div className={`${WRAP} flex items-center justify-between gap-3 py-2.5`}>
          <div className="flex items-center gap-6">
            <span className="text-[21px] font-bold tracking-[-0.03em]">FINN</span>
            <nav aria-label="Primary" className="hidden gap-1 md:flex">
              {TABS.map(([k, l]) => (
                <button key={k} onClick={() => go(k)} aria-current={tab === k ? "page" : undefined}
                  className={`rounded-[3px] px-3 py-1.5 text-[14px] transition-colors ${tab === k ? "bg-ink font-semibold text-paper" : "text-mute hover:text-ink"}`}>{l}</button>
              ))}
            </nav>
          </div>
          <button onClick={() => setSheet(true)} aria-label="Data sources and freshness"
            className="flex items-center gap-x-2 sm:gap-x-3 text-[11px] sm:text-[12px] text-mute shrink-0 py-1 px-1.5 rounded hover:bg-raised transition-colors">
            {status ? (<>
              <span className="flex items-center gap-1 sm:gap-1.5">
                <span className="hidden xs:inline">Prices</span>
                <Badge status={status.prices.status} detail={detail(status.prices)} small />
              </span>
              <span className="flex items-center gap-1 sm:gap-1.5">
                <span className="hidden xs:inline">Filings</span>
                <Badge status={status.announcements.status} detail={detail(status.announcements)} small />
              </span>
            </>) : "Data"}
          </button>
        </div>
      </header>

      {anyMock && (
        <p className="bg-warn-soft py-2 text-[12.5px] text-warn"><span className={WRAP + " block"}>
          You're looking at synthetic data for interface testing. Prices and filings marked Mock are not real.</span></p>
      )}
      {status?.prices.status === "CACHED" && (
        <p className="bg-warn-soft py-2 text-[12.5px] text-warn"><span className={WRAP + " block"}>{status.prices.note}</span></p>
      )}
      {!!status?.classification.needs_reclassify && (
        <p className="bg-accent-soft py-2 text-[12.5px] text-accent"><span className={WRAP + " block"}>
          {status.classification.needs_reclassify} saved filings still carry the old classification. They are already shown with the new rules.
          To save them, run <code className="font-semibold">python -m finn.cli reclassify --apply</code> (a backup is made first).</span></p>
      )}

      <main className={`${WRAP} pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-16`}>
        {tab === "brief" ? (
          <BriefView brief={brief} loading={loading} error={briefErr} onRetry={loadBrief}
            win={win} setWin={setWin} range={range} setRange={setRange} symbol={symbol} setSymbol={setSymbol} />
        ) : tab === "portfolio" ? (
          <PortfolioView data={pf} error={pfErr} onOpen={openCompany} onRetry={loadPf} />
        ) : (
          <ResearchView onOpenCompany={openCompany} initialSymbol={symbol ?? "RELIANCE"} />
        )}
      </main>

      <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-paper pb-[env(safe-area-inset-bottom)] md:hidden">
        <div className="flex">
          {TABS.map(([k, l]) => (
            <button key={k} onClick={() => go(k)} aria-current={tab === k ? "page" : undefined}
              className={`-mt-px flex-1 border-t-2 py-3 text-[13px] sm:text-[14px] transition-colors ${
                tab === k
                  ? "border-accent font-semibold text-accent bg-accent-soft/30"
                  : "border-transparent text-mute hover:text-ink"
              }`}>
              {l === "Brief" ? "📰 Brief" : l === "Portfolio" ? "💼 Portfolio" : "🔍 Research"}
            </button>
          ))}
        </div>
      </nav>

      {sheet && status && <StatusSheet status={status} onClose={() => setSheet(false)} />}
    </div>
  );
}
