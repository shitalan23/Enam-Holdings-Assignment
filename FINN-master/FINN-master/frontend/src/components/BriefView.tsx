import { useMemo, useState } from "react";
import { api, type Brief, type FilingResultsResponse, type Item } from "../api";
import { Badge } from "./Badge";
import { Ribbon } from "./Ribbon";
import { ResultsCard } from "./ResultsCard";
import { ago, confPct, day, full, pct, sign, signed } from "../format";

export type Win = "24h" | "3d" | "7d" | "30d" | "custom";
const WINS: { k: Win; label: string }[] = [
  { k: "24h", label: "24h" }, { k: "3d", label: "3 days" }, { k: "7d", label: "7 days" },
  { k: "30d", label: "30 days" }, { k: "custom", label: "Custom" },
];
const ACT_LIMIT = 8;   // "Needs you" shows the top 8; the rest are one tap away
const GENERIC = /^(updates?|general updates?|others?|disclosures?|announcements?)$/i;
const TIER_NAME = { act: "Needs you", know: "Worth knowing", skim: "Routine" } as const;

interface Props {
  brief: Brief | null; loading: boolean; error: string | null; onRetry: () => void;
  win: Win; setWin: (w: Win) => void;
  range: { from: string; to: string }; setRange: (r: { from: string; to: string }) => void;
  symbol: string | null; setSymbol: (s: string | null) => void;
}

export function BriefView(p: Props) {
  const [cats, setCats] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [skimOpen, setSkimOpen] = useState(false);
  const [allAct, setAllAct] = useState(false);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  const toggle = (set: Set<string>, v: string) => { const n = new Set(set); n.has(v) ? n.delete(v) : n.add(v); return n; };

  const items = p.brief?.items ?? [];
  const catCounts = useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    items.forEach((i) => { const c = m.get(i.category) ?? { label: i.category_label, n: 0 }; c.n++; m.set(i.category, c); });
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [items]);

  // Stable mapping: ensure each result_id is surfaced on at most one filing in the feed
  const primaryResultFilingIds = useMemo(() => {
    const primaryIds = new Set<string>();
    const seenResults = new Set<string>();
    for (const item of items) {
      if (item.has_results && item.result_id && !seenResults.has(item.result_id)) {
        primaryIds.add(item.id);
        seenResults.add(item.result_id);
      }
    }
    return primaryIds;
  }, [items]);

  const shown = cats.size ? items.filter((i) => cats.has(i.category)) : items;
  const act = shown.filter((i) => i.tier === "act"), know = shown.filter((i) => i.tier === "know"), skim = shown.filter((i) => i.tier === "skim");
  const actShown = allAct ? act : act.slice(0, ACT_LIMIT);
  const row = (i: Item, v: "act" | "know") => (
    <Row
      key={i.id}
      i={i}
      v={v}
      tiers={p.brief!.status.tiers}
      open={open.has(i.id)}
      canShowResults={primaryResultFilingIds.has(i.id)}
      onToggle={() => setOpen(toggle(open, i.id))}
      onSymbol={p.setSymbol}
    />
  );

  return (
    <div className="mx-auto max-w-[760px] lg:max-w-none">
      <div role="tablist" aria-label="Time window" className="flex border-b border-rule overflow-x-auto no-scrollbar">
        {WINS.map((w) => (
          <button key={w.k} role="tab" aria-selected={p.win === w.k} onClick={() => p.setWin(w.k)}
            className={`-mb-px shrink-0 border-b-2 py-2.5 px-3 text-[13px] md:flex-none md:px-5 md:text-[13.5px] transition-colors ${p.win === w.k ? "border-accent font-semibold text-ink" : "border-transparent text-mute hover:text-ink"}`}>
            {w.label}
          </button>
        ))}
      </div>
      {p.win === "custom" && (
        <div className="flex flex-wrap items-center gap-2 border-b border-rule py-2.5 text-xs sm:text-sm">
          <input type="date" aria-label="From date" value={p.range.from} max={p.range.to}
            onChange={(e) => p.setRange({ ...p.range, from: e.target.value })} className="rounded-[3px] border border-rule bg-raised px-2 py-1.5 min-w-[130px] flex-1 sm:flex-none" />
          <span className="text-mute">to</span>
          <input type="date" aria-label="To date" value={p.range.to} min={p.range.from}
            onChange={(e) => p.setRange({ ...p.range, to: e.target.value })} className="rounded-[3px] border border-rule bg-raised px-2 py-1.5 min-w-[130px] flex-1 sm:flex-none" />
        </div>
      )}

      {p.brief && <SnapshotBanner brief={p.brief} win={p.win} />}

      {p.error ? (
        <div className="py-10">
          <p className="font-semibold">Couldn't load the brief.</p>
          <p className="mt-1 text-sm text-mute">The FINN server didn't respond ({p.error}). Check that the backend is running, then try again.</p>
          <button onClick={p.onRetry} className="mt-3 rounded-[3px] border border-ink px-3 py-1.5 text-sm font-medium">Try again</button>
        </div>
      ) : !p.brief ? (
        <p className="py-10 text-mute">Loading your brief…</p>
      ) : (
        /* Phone/tablet: one column in reading order. Desktop: feed left, ribbon + filters in a sticky right rail. */
        <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_300px] lg:gap-x-12">
          <div className="lg:col-start-1 lg:row-start-1"><Summary brief={p.brief} loading={p.loading} /></div>

          <aside className="lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:pt-6">
            <div className="lg:sticky lg:top-[76px]">
              {p.brief.counts.total > 0 && <div className="mb-4"><Ribbon items={items} from={p.brief.window.from} to={p.brief.window.to} /></div>}
              {p.symbol && (
                <button onClick={() => p.setSymbol(null)} className="mb-3 inline-flex items-center gap-1.5 rounded-[3px] bg-accent px-2.5 py-1 text-[13px] font-semibold text-paper">
                  {p.symbol} only <span aria-hidden>×</span><span className="sr-only">Clear company filter</span>
                </button>
              )}
              {catCounts.length > 1 && (<>
                {/* Mobile Collapsible Filter Toggle */}
                <div className="mb-2 flex items-center justify-between lg:hidden">
                  <button
                    type="button"
                    onClick={() => setMobileFilterOpen(!mobileFilterOpen)}
                    className="inline-flex items-center gap-1.5 rounded border border-rule bg-raised px-2.5 py-1 text-xs font-medium text-ink"
                  >
                    <span>🏷️ Filter by category</span>
                    {cats.size > 0 && (
                      <span className="rounded bg-accent px-1.5 py-0.2 text-[10px] font-bold text-paper">
                        {cats.size} active
                      </span>
                    )}
                    <span className="text-[10px] text-mute">{mobileFilterOpen ? "▲" : "▼"}</span>
                  </button>
                  {cats.size > 0 && (
                    <button
                      type="button"
                      onClick={() => setCats(new Set())}
                      className="text-[11px] text-accent font-medium hover:underline"
                    >
                      Clear filters
                    </button>
                  )}
                </div>

                <h3 className="mb-1 hidden text-[13px] font-semibold text-mute lg:block">Filter by type</h3>
                <div className={`${
                  mobileFilterOpen ? "flex" : "hidden lg:flex"
                } -mx-4 mb-2 flex-wrap gap-1.5 px-4 pb-2 md:mx-0 md:px-0 lg:flex-col lg:gap-0`}>
                  {catCounts.map(([c, v]) => (
                    <button key={c} aria-pressed={cats.has(c)} onClick={() => setCats(toggle(cats, c))}
                      className={`flex shrink-0 items-center justify-between gap-3 rounded-[3px] border px-2 py-1 text-[12px] sm:text-[12.5px] lg:rounded-none lg:border-0 lg:border-b lg:border-rule lg:px-1 lg:py-2 lg:text-[13.5px] transition-colors ${cats.has(c) ? "border-ink bg-ink font-semibold text-paper lg:bg-accent-soft lg:text-accent" : "border-rule text-mute hover:border-ink/40 lg:text-ink"}`}>
                      <span>{v.label}</span><span className="opacity-70 font-mono text-[11px]">{v.n}</span>
                    </button>
                  ))}
                </div>
              </>)}
            </div>
          </aside>

          <div className="lg:col-start-1 lg:row-start-2">
            {act.length > 0 && (
              <Section title="Needs you" n={act.length}>
                {actShown.map((i) => row(i, "act"))}
                {act.length > ACT_LIMIT && (
                  <button onClick={() => setAllAct(!allAct)} className="w-full border-b border-rule py-3 text-left text-[14px] font-medium text-accent">
                    {allAct ? "Show fewer" : `Show ${act.length - ACT_LIMIT} more that need you`}
                  </button>
                )}
              </Section>
            )}
            {know.length > 0 && <Section title="Worth knowing" n={know.length}>{know.map((i) => row(i, "know"))}</Section>}
            {skim.length > 0 && (
              <div className="mt-6">
                <button onClick={() => setSkimOpen(!skimOpen)} aria-expanded={skimOpen}
                  className="flex w-full items-center justify-between border-y border-rule py-3 text-left">
                  <span className="text-[14.5px] font-medium">{skim.length} routine filing{skim.length === 1 ? "" : "s"}</span>
                  <span className="text-sm text-mute">{skimOpen ? "Hide" : "Show"}</span>
                </button>
                <div className="reveal" data-open={skimOpen}><div>
                  {skim.map((i) => (
                    <div key={i.id} id={`it-${i.id}`} className="flex items-baseline gap-2 border-b border-rule/60 py-2 text-[13px]">
                      <button onClick={() => p.setSymbol(i.symbol)} className="w-[84px] shrink-0 truncate text-left font-semibold">{i.symbol}</button>
                      <span className="hidden w-[150px] shrink-0 truncate text-faint md:block">{i.category_label}</span>
                      <span className="min-w-0 flex-1 truncate text-mute">{i.headline}</span>
                      {i.source === "MOCK" && <Badge status="MOCK" small />}
                      <span className="shrink-0 text-faint">{ago(i.ts)}</span>
                    </div>
                  ))}
                </div></div>
              </div>
            )}
            {shown.length === 0 && p.brief.counts.total > 0 && <p className="py-8 text-mute">No filings match those filters.</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function formatSnapshotDate(ts: string | null | undefined): string {
  if (!ts) return "Unavailable";
  try {
    return (
      new Date(ts).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }) + " IST"
    );
  } catch {
    return ts;
  }
}

function formatPriceEodDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "Unavailable";
  try {
    const d = new Date(dateStr.includes("T") ? dateStr : `${dateStr}T00:00:00+05:30`);
    return (
      d.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      }) + " (EOD close)"
    );
  } catch {
    return `${dateStr} (EOD close)`;
  }
}

function SnapshotBanner({ brief, win }: { brief: Brief; win: Win }) {
  const annAsOf = brief.status?.announcements?.as_of;
  const priceAsOf = brief.status?.prices?.as_of;

  return (
    <aside aria-label="Database snapshot provenance" className="mt-3 mb-2 rounded border border-rule bg-raised/70 px-3.5 py-2.5 text-xs text-mute">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
        <div className="flex items-center gap-1.5 font-semibold text-ink">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
          <span>Data as of:</span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-ink/90 font-medium">
          <span>
            📰 <b>Filings:</b> {formatSnapshotDate(annAsOf)}
          </span>
          <span className="hidden sm:inline text-faint" aria-hidden="true">•</span>
          <span>
            📈 <b>Prices:</b> {formatPriceEodDate(priceAsOf)}
          </span>
        </div>
      </div>
      <p className="mt-1.5 text-[11.5px] leading-relaxed text-faint">
        Hosted deployment uses a preloaded historical data snapshot (NSE Q2 FY27) and is not continuously refreshed.
        Time windows ({win === "custom" ? "custom range" : win}) are relative to the newest available filing.
      </p>
    </aside>
  );
}

function Summary({ brief, loading }: { brief: Brief; loading: boolean }) {
  const { act, know, skim, total } = brief.counts;
  const none = total === 0;
  const head = none ? "Nothing filed in this window."
    : act === 0 ? "Nothing urgent." + (know ? ` ${know} worth knowing.` : "")
    : `${act} ${act === 1 ? "needs" : "need"} you.` + (know ? ` ${know} worth knowing.` : "");
  const unavailable = brief.status.announcements.status === "UNAVAILABLE";
  return (
    <div className={`pb-4 pt-5 lg:pt-6 ${loading ? "opacity-60" : ""}`}>
      <h1 className="text-[26px] font-semibold leading-[1.15] tracking-[-0.01em] md:text-[30px]">{unavailable ? "No filings loaded yet." : head}</h1>
      <p className="mt-1.5 text-[13.5px] text-mute">
        {unavailable ? "Run the announcements ingest to load filings."
          : none ? "Try a longer window."
          : `${brief.window.label}. ${total} filing${total === 1 ? "" : "s"}${skim ? `, ${skim} routine collapsed` : ""}.`}
      </p>
    </div>
  );
}

function Section({ title, n, children }: { title: string; n: number; children: React.ReactNode }) {
  return (
    <section className="mt-5 first:mt-1">
      <h2 className="mb-1 flex items-baseline gap-2 text-[13.5px] font-semibold text-mute">{title}<span className="font-normal text-faint">{n}</span></h2>
      <div>{children}</div>
    </section>
  );
}

function Row({ i, v, tiers, open, canShowResults, onToggle, onSymbol }: {
  i: Item; v: "act" | "know"; tiers: { act: number; know: number };
  open: boolean; canShowResults: boolean; onToggle: () => void; onSymbol: (s: string) => void;
}) {
  const act = v === "act";
  const title = GENERIC.test(i.headline) && i.detail ? (i.detail.length > 150 ? i.detail.slice(0, 147) + "…" : i.detail) : i.headline;
  const review = i.category === "needs_review";

  const [resultsData, setResultsData] = useState<FilingResultsResponse | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const toggleResults = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!resultsData && !loadingResults) {
      setLoadingResults(true);
      api.filingResults(i.id)
        .then(setResultsData)
        .catch((err) => console.error("Could not load quarterly results", err))
        .finally(() => setLoadingResults(false));
    }
    setShowResults((v) => !v);
  };

  return (
    <article id={`it-${i.id}`} className={`border-b border-rule ${act ? "border-l-[4px] border-l-accent pl-3" : "border-l-2 border-l-rule pl-3"}`}>
      <button onClick={onToggle} aria-expanded={open} className="block w-full py-3 text-left">
        <div className="flex items-baseline justify-between gap-2 text-[13px]">
          <span><b className="font-semibold">{i.symbol}</b> <span className="text-mute">{i.name}</span></span>
          <span className="flex shrink-0 items-center gap-1.5 text-faint">{i.source === "MOCK" && <Badge status="MOCK" small />}{ago(i.ts)}</span>
        </div>
        <p className={`mt-1 ${act ? "text-[17px] font-semibold leading-snug" : "text-[15px] font-medium leading-snug"}`}>{title}</p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {i.why.map((w, k) => (
            <span key={k} className={`rounded-[3px] px-1.5 py-[3px] text-[11.5px] leading-none ${w.kind === "category" ? (review ? "bg-warn-soft font-semibold text-warn" : "bg-accent-soft font-semibold text-accent") : "border border-rule text-mute"}`}>{w.label}</span>
          ))}

          {/* Quick results intelligence badge - strictly rendered on primary filing only */}
          {canShowResults && (
            <button
              type="button"
              onClick={toggleResults}
              className={`rounded-[3px] px-2 py-[2.5px] text-[11.5px] font-semibold transition border ${
                showResults
                  ? "bg-accent text-paper border-accent"
                  : "bg-accent/15 text-accent border-accent/30 hover:bg-accent/25"
              }`}
            >
              {loadingResults ? "Loading Results…" : showResults ? "Hide Results Intelligence" : "📊 Results Intelligence"}
            </button>
          )}
        </div>
      </button>

      {/* Embedded Results Card */}
      {showResults && resultsData && (
        <div className="pb-3 pr-2">
          <ResultsCard data={resultsData} onClose={() => setShowResults(false)} />
        </div>
      )}

      <div className="reveal" data-open={open}><div>
        <div className="space-y-3 pb-4 text-[13.5px]">
          {i.detail && !(GENERIC.test(i.headline)) && <p className="text-mute">{i.detail}</p>}
          {i.reaction ? (
            <p>End-of-day reaction, {day(i.reaction.date)}: <b className={sign(i.reaction.pct)}>{pct(i.reaction.pct)}</b>
              {i.reaction.vol_x != null && <> on <b>{i.reaction.vol_x.toFixed(1)}×</b> its 20-day average volume</>}. <span className="text-faint">Could be coincidence.</span></p>
          ) : (
            <p className="text-mute">No trading session since this filing, so there is no market reaction yet.</p>
          )}

          {/* If results card is not already shown above, offer it in expanded section as well */}
          {canShowResults && !showResults && (
            <div>
              <button
                type="button"
                onClick={toggleResults}
                className="inline-flex items-center gap-1.5 rounded bg-accent/15 px-2.5 py-1 text-[12px] font-semibold text-accent hover:bg-accent/25"
              >
                <span>📊 View Full Results Intelligence Card</span>
              </button>
            </div>
          )}

          <div className="rounded-[3px] border border-rule bg-raised p-3 md:max-w-[460px]">
            <p className="mb-1.5 text-[12.5px] font-semibold text-mute">How this scored</p>
            <ul>
              {i.breakdown.map((r, k) => (
                <li key={k} className="flex justify-between gap-4 py-0.5 text-[13px]">
                  <span className={r.kind === "cap" ? "text-warn" : r.kind === "base" ? "font-medium" : "text-mute"}>{r.label}</span>
                  <span className={`shrink-0 font-medium ${r.points < 0 ? "text-down" : ""}`}>{r.kind === "base" ? r.points : signed(r.points)}</span>
                </li>
              ))}
            </ul>
            <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1 border-t border-rule pt-1.5 text-[12.5px] font-semibold">
              <span>Score {i.score}: {{ act: "Needs you", know: "Worth knowing", skim: "Routine" }[i.tier]}</span>
              <span className="font-normal text-faint">Needs you ≥ {tiers.act} · Worth knowing ≥ {tiers.know}</span>
            </div>
            {i.gate && <p className="mt-1.5 text-[12.5px] text-warn">{i.gate}</p>}
          </div>

          <p className="text-[12.5px] text-faint">
            {review ? "Needs review: " : "Classified as "}{i.category_label}{i.subtype ? ` · ${i.subtype.replace(/_/g, " ")}` : ""} ({confPct(i.confidence)} sure). {i.classified_by}.
          </p>
          <p className="text-faint">Filed {full(i.ts)} · {i.source === "MOCK" ? "Mock data" : "Source: NSE"}</p>
          <div className="flex flex-wrap gap-4 pt-1 text-sm font-medium">
            {i.pdf_url ? <a href={i.pdf_url} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">Open filing</a>
              : <span className="text-faint">No document attached</span>}
            <button onClick={() => onSymbol(i.symbol)} className="underline underline-offset-2">All {i.symbol} filings</button>
          </div>
        </div>
      </div></div>
    </article>
  );
}
