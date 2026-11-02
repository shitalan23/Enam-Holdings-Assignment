import { useCallback, useEffect, useState } from "react";
import { CommitmentsSection } from "./CommitmentsSection";
import {
  api,
  type CitationItem,
  type CommitmentsResponse,
  type ResearchDossier,
  type ResearchResponse,
  type ResearchSearchItem,
} from "../api";

interface ResearchViewProps {
  onOpenCompany?: (symbol: string) => void;
  initialSymbol?: string;
}

const QUICK_TICKERS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC", "LT"];

const DIMENSIONS = [
  { id: "all", label: "All Dimensions" },
  { id: "business", label: "1. Business Snapshot" },
  { id: "financial", label: "2. Financial Snapshot" },
  { id: "trajectory", label: "3. Trajectory" },
  { id: "balance_sheet", label: "4. Balance Sheet" },
  { id: "cash_quality", label: "5. Cash Quality" },
  { id: "narrative", label: "6. Narrative vs Numbers" },
  { id: "guidance", label: "7. Guidance" },
  { id: "bull_bear", label: "8. Bull vs Bear" },
  { id: "commitments", label: "🎯 Promise vs Delivered (P1.3)" },
];

function fmtCr(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return `₹${val.toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`;
}

function CitationChip({
  id,
  citations,
  onSelect,
}: {
  id: string;
  citations: CitationItem[];
  onSelect: (c: CitationItem) => void;
}) {
  const cit = citations.find((c) => c.id === id);
  if (!cit) return null;

  let label: string;
  let icon = "📑";
  let colorClass = "bg-accent-soft/70 text-accent hover:bg-accent-soft border border-accent/20";

  if (cit.doc_type === "annual_report") {
    label = `Annual Report P.${cit.page}`;
    icon = "📘";
    colorClass = "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/25 hover:bg-indigo-500/20";
  } else if (cit.doc_type === "concall_transcript") {
    label = `Concall Transcript P.${cit.page}`;
    icon = "🎙️";
    colorClass = "bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/25 hover:bg-purple-500/20";
  } else if (cit.doc_type === "investor_presentation") {
    label = `Pres. Slide ${cit.page}`;
    icon = "📊";
    colorClass = "bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/25 hover:bg-amber-500/20";
  } else {
    label = `Results P.${cit.page}`;
    icon = "📑";
    colorClass = "bg-accent-soft/70 text-accent hover:bg-accent-soft border border-accent/20";
  }

  return (
    <button
      type="button"
      onClick={() => onSelect(cit)}
      title={`${cit.doc_title} (${cit.section}, Page/Slide ${cit.page}) — Click to inspect citation`}
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] font-medium transition-colors cursor-pointer ${colorClass}`}
    >
      <span>{icon}</span>
      <span>{label}</span>
      {cit.needs_review && (
        <span title={`Needs Review: ${cit.review_reason ?? 'Flagged for audit'}`} className="text-amber-600 font-bold ml-0.5">⚠️</span>
      )}
    </button>
  );
}

export function ResearchView({ onOpenCompany, initialSymbol = "RELIANCE" }: ResearchViewProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ResearchSearchItem[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);

  const [symbol, setSymbol] = useState<string>(initialSymbol);
  const [research, setResearch] = useState<ResearchResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [commitmentsResponse, setCommitmentsResponse] = useState<CommitmentsResponse | null>(null);
  const [commitmentsLoading, setCommitmentsLoading] = useState<boolean>(false);
  const [commitmentsError, setCommitmentsError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<string>("all");
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);
  const [showDocs, setShowDocs] = useState<boolean>(false);

  // Search autocomplete
  useEffect(() => {
    let active = true;
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    setSearchLoading(true);
    const timer = setTimeout(() => {
      api
        .researchSearch(searchQuery)
        .then((res) => {
          if (active) setSearchResults(res.results);
        })
        .catch(() => {
          if (active) setSearchResults([]);
        })
        .finally(() => {
          if (active) setSearchLoading(false);
        });
    }, 180);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [searchQuery]);

  // Fetch company research dossier and commitments
  const loadResearch = useCallback((sym: string) => {
    setLoading(true);
    setError(null);
    setActiveCitation(null);
    api
      .researchGet(sym)
      .then((res) => {
        setResearch(res);
      })
      .catch((e) => {
        setError(String(e.message ?? e));
        setResearch(null);
      })
      .finally(() => {
        setLoading(false);
      });

    // Also fetch commitments and summary for P1.3 Promise vs Delivered
    setCommitmentsLoading(true);
    setCommitmentsError(null);
    Promise.all([
      api.commitments(sym),
      api.commitmentsSummary(sym).catch(() => null),
    ])
      .then(([commRes, sumRes]) => {
        if (sumRes && sumRes.summary && commRes) {
          commRes.summary = sumRes.summary;
        }
        setCommitmentsResponse(commRes);
      })
      .catch((e) => {
        setCommitmentsError(String(e.message ?? e));
        setCommitmentsResponse(null);
      })
      .finally(() => {
        setCommitmentsLoading(false);
      });
  }, []);

  useEffect(() => {
    loadResearch(symbol);
  }, [symbol, loadResearch]);

  const selectCompany = (s: string) => {
    setSymbol(s);
    setSearchOpen(false);
    setSearchQuery("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const dossier: ResearchDossier | null = research?.dossier ?? null;
  const citations = dossier?.citations ?? [];

  return (
    <div className="pt-3 pb-8 text-ink">
      {/* Search Header Banner */}
      <div className="mb-4 rounded border border-rule bg-raised/80 p-3.5 md:p-5 shadow-xs">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold tracking-tight md:text-lg">
                Financial Research Intelligence
              </h1>
              <span className="rounded bg-accent px-1.5 py-0.5 text-[11px] font-semibold text-paper">
                Pull Engine
              </span>
            </div>
            <p className="mt-0.5 text-[12.5px] text-mute">
              On-demand fundamental research dossiers backed strictly by official primary filings (NSE/BSE & IR portals).
            </p>
          </div>

          {/* Quick Tickers */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11.5px] font-medium text-faint">Quick select:</span>
            {QUICK_TICKERS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => selectCompany(t)}
                className={`rounded border px-2 py-0.5 text-[12px] font-mono transition-colors ${
                  symbol === t
                    ? "border-accent bg-accent-soft font-semibold text-accent"
                    : "border-rule bg-paper/60 text-mute hover:border-ink/40 hover:text-ink"
                }`}
              >
                {t}
                {t === "RELIANCE" ? " ★" : ""}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar Input */}
        <div className="relative mt-3">
          <div className="flex items-center rounded border border-rule bg-paper px-3 py-2 focus-within:border-accent">
            <span className="mr-2 text-mute">🔍</span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              placeholder="Search NSE listed company (e.g. RELIANCE, TCS, INFY, HDFCBANK)..."
              className="w-full bg-transparent text-[13.5px] text-ink placeholder:text-faint focus:outline-hidden"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-mute hover:text-ink text-xs px-1"
              >
                ✕
              </button>
            )}
            {searchLoading && <span className="ml-2 text-xs text-mute animate-pulse">Searching...</span>}
          </div>

          {/* Autocomplete Dropdown */}
          {searchOpen && searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 z-50 mt-1 max-h-72 overflow-y-auto rounded border border-rule bg-raised p-1 shadow-lg">
              {searchResults.map((item) => (
                <button
                  key={item.symbol}
                  type="button"
                  onClick={() => selectCompany(item.symbol)}
                  className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-xs hover:bg-paper transition-colors"
                >
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-ink">{item.symbol}</span>
                      <span className="text-mute">{item.name}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-faint">
                      <span>{item.sector}</span>
                      <span>•</span>
                      <span>{item.size_bucket} Cap</span>
                      {item.in_portfolio && (
                        <>
                          <span>•</span>
                          <span className="text-accent font-medium">Portfolio ({item.weight}%)</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div>
                    {item.has_research ? (
                      <span className="rounded bg-up/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-up">
                        Research Ready ({item.as_of_period})
                      </span>
                    ) : (
                      <span className="rounded bg-rule/50 px-1.5 py-0.5 text-[10.5px] font-medium text-mute">
                        Ingest Required
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="flex flex-col items-center justify-center rounded border border-rule bg-raised/40 py-16 text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <p className="mt-3 text-xs text-mute">Synthesizing evidence-backed fundamentals for {symbol}...</p>
        </div>
      ) : error ? (
        <div className="rounded border border-down/30 bg-down/5 p-4 text-center">
          <p className="text-xs font-semibold text-down">Unable to load research dossier</p>
          <p className="mt-1 text-xs text-mute">{error}</p>
          <button
            type="button"
            onClick={() => loadResearch(symbol)}
            className="mt-3 rounded bg-down/10 px-3 py-1 text-xs font-medium text-down hover:bg-down/20"
          >
            Retry
          </button>
        </div>
      ) : research?.status === "UNAVAILABLE" ? (
        /* Honest UNAVAILABLE State */
        <div className="space-y-6">
          <div className="rounded border border-dashed border-rule bg-raised/40 p-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-paper text-xl text-mute">
              📄
            </div>
            <h2 className="mt-3 text-base font-semibold text-ink">
              Research Dossier Unavailable for {research.symbol}
            </h2>
            <p className="mx-auto mt-1 max-w-md text-xs text-mute">
              {research.message ?? "Primary exchange filings have not yet been extracted for this company."}
            </p>

            <div className="mt-5 mx-auto max-w-lg rounded border border-rule bg-paper/60 p-4 text-left">
              <p className="text-xs font-semibold text-ink">Evidence-First Research with Explicit Uncertainty:</p>
              <p className="mt-1 text-[12px] text-mute">
                FINN strictly produces financial research grounded in primary official disclosures. To synthesize this company's dossier:
              </p>
              <ul className="mt-2 space-y-1 text-[11.5px] text-faint list-disc list-inside">
                <li>Unaudited / Audited Quarterly Results PDF (Regulation 33 Statement)</li>
                <li>Official Investor Presentation slide deck</li>
                <li>Earnings Conference Call Transcript</li>
              </ul>
            </div>

            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => selectCompany("RELIANCE")}
                className="rounded bg-accent px-3 py-1.5 text-xs font-semibold text-paper hover:bg-accent/90"
              >
                View RELIANCE Demonstration Dossier ★
              </button>
            </div>
          </div>

          {/* Promise vs Delivered UNAVAILABLE Component */}
          <div className="rounded border border-rule bg-raised/50 p-4 md:p-5">
            <div className="mb-3 flex items-center justify-between border-b border-rule pb-2">
              <div className="flex items-center gap-2">
                <span className="text-base">🎯</span>
                <h3 className="text-sm font-semibold tracking-tight md:text-base">
                  Promise vs Delivered
                </h3>
              </div>
              <span className="rounded bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
                P1.3 Delivery Engine
              </span>
            </div>

            <CommitmentsSection
              symbol={symbol}
              companyName={research.company_name ?? symbol}
              summary={commitmentsResponse?.summary ?? null}
              commitments={commitmentsResponse?.commitments ?? []}
              loading={commitmentsLoading}
              error={commitmentsError}
              onSelectReliance={() => selectCompany("RELIANCE")}
            />
          </div>
        </div>
      ) : dossier ? (
        /* AVAILABLE Research Dossier */
        <div>
          {/* Dossier Header */}
          <div className="rounded border border-rule bg-raised p-4 md:p-5 shadow-xs">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold tracking-tight text-ink md:text-xl break-words">
                    {dossier.company_name}
                  </h2>
                  <span className="rounded bg-paper px-2 py-0.5 font-mono text-xs font-semibold text-ink border border-rule">
                    {dossier.symbol}
                  </span>
                  <span className="rounded bg-up/10 px-2 py-0.5 text-xs font-semibold text-up">
                    {dossier.as_of_period}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-mute">
                  <span>{dossier.sector}</span>
                  <span>•</span>
                  <span>{dossier.size_bucket} Cap</span>
                  <span>•</span>
                  <span>As of {dossier.as_of_date}</span>
                  <span>•</span>
                  <span className="text-faint">
                    Generated {new Date(dossier.generated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                  </span>
                </div>
              </div>

              {/* Source Document Trigger */}
              <div className="flex items-center gap-2 pt-1 md:pt-0">
                <button
                  type="button"
                  onClick={() => setShowDocs(!showDocs)}
                  className="inline-flex items-center gap-1.5 rounded border border-rule bg-paper px-2.5 py-1 text-xs font-medium text-mute hover:border-ink/40 hover:text-ink"
                >
                  <span>📂</span>
                  <span>Verified Primary Sources ({dossier.source_documents.length})</span>
                  <span className="text-[10px]">{showDocs ? "▲" : "▼"}</span>
                </button>
              </div>
            </div>

            {/* Expandable Primary Sources Manifest */}
            {showDocs && (
              <div className="mt-3.5 rounded border border-rule/80 bg-paper/80 p-3 text-xs">
                <p className="font-semibold text-ink">Primary Documents Verified in this Dossier:</p>
                <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
                  {dossier.source_documents.map((doc, idx) => {
                    const isAR = doc.doc_type === "annual_report";
                    const isConcall = doc.doc_type === "concall_transcript";
                    const isPres = doc.doc_type === "investor_presentation";
                    const docLabel = isAR
                      ? "Annual Report (FY26)"
                      : isConcall
                      ? "Concall Transcript (Q2 FY26)"
                      : isPres
                      ? "Investor Presentation"
                      : "Quarterly Results";
                    const badgeClass = isAR
                      ? "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-500/25"
                      : isConcall
                      ? "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/25"
                      : isPres
                      ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25"
                      : "bg-accent-soft text-accent border-accent/25";

                    return (
                      <div key={idx} className="flex flex-col justify-between rounded border border-rule bg-raised p-2.5">
                        <div>
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-mono font-medium text-ink truncate text-[11.5px]">{doc.doc_name}</span>
                            <span className={`rounded border px-1.5 py-0.2 text-[10px] font-semibold shrink-0 ${badgeClass}`}>
                              {docLabel}
                            </span>
                          </div>
                          <p className="mt-1 text-[11px] text-mute">
                            Verified: {(doc.verified_pages ? `Pages ${doc.verified_pages.join(", ")}` : doc.verified_slides ? `Slides ${doc.verified_slides.join(", ")}` : "All pages")}
                          </p>
                        </div>
                        <div className="mt-2 flex gap-2">
                          <a
                            href={doc.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] font-semibold text-accent hover:underline"
                          >
                            Official Document ↗
                          </a>
                          {doc.ir_url && (
                            <a
                              href={doc.ir_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] text-mute hover:underline"
                            >
                              Company IR Portal ↗
                            </a>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Active Citation Detail Pill */}
            {activeCitation && (
              <div className="mt-3.5 rounded border border-accent/40 bg-paper/95 p-3 text-xs text-ink shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-rule/60 pb-2">
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                    <span className="font-semibold text-accent flex items-center gap-1">
                      <span>{activeCitation.doc_type === "annual_report" ? "📘" : activeCitation.doc_type === "concall_transcript" ? "🎙️" : "📌"}</span>
                      <span>Citation Inspector:</span>
                    </span>
                    <span className={`rounded px-1.5 py-0.2 text-[10px] font-semibold border ${
                      activeCitation.doc_type === "annual_report"
                        ? "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-500/25"
                        : activeCitation.doc_type === "concall_transcript"
                        ? "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/25"
                        : activeCitation.doc_type === "investor_presentation"
                        ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25"
                        : "bg-accent-soft text-accent border-accent/25"
                    }`}>
                      {activeCitation.doc_type === "annual_report"
                        ? "Annual Report"
                        : activeCitation.doc_type === "concall_transcript"
                        ? "Concall Transcript"
                        : activeCitation.doc_type === "investor_presentation"
                        ? "Investor Presentation"
                        : "Results Statement"}
                    </span>
                    <span className="font-medium text-ink break-words">{activeCitation.doc_title}</span>
                    <span className="text-mute font-mono text-[11px]">
                      ({activeCitation.section}, Page/Slide {activeCitation.page})
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
                    <a
                      href={activeCitation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded bg-accent px-2.5 py-1 text-[11px] font-semibold text-paper hover:bg-accent/90"
                    >
                      Open Source PDF ↗
                    </a>
                    <button
                      type="button"
                      onClick={() => setActiveCitation(null)}
                      className="text-mute hover:text-ink px-1.5 py-0.5 rounded hover:bg-raised"
                      aria-label="Close citation inspector"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {/* Speaker details for transcripts */}
                {activeCitation.speaker_name && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-semibold text-purple-700 dark:text-purple-300 flex items-center gap-1">
                      <span>🎙️ Speaker:</span>
                      <span>{activeCitation.speaker_name}</span>
                    </span>
                    {activeCitation.speaker_designation && (
                      <span className="text-mute italic text-[11.5px]">({activeCitation.speaker_designation})</span>
                    )}
                    {activeCitation.speaker_role && (
                      <span className={`rounded px-1.5 py-0.2 text-[9.5px] font-semibold uppercase ${
                        activeCitation.speaker_role === "MANAGEMENT"
                          ? "bg-up/10 text-up border border-up/25"
                          : "bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/25"
                      }`}>
                        {activeCitation.speaker_role}
                      </span>
                    )}
                    {activeCitation.statement_type && (
                      <span className="rounded bg-raised px-1.5 py-0.2 text-[9.5px] font-mono text-faint border border-rule">
                        {activeCitation.statement_type}
                      </span>
                    )}
                  </div>
                )}

                {/* Analytical Claim */}
                <div className="mt-2 text-[12px] text-ink leading-relaxed break-words">
                  <span className="font-semibold text-mute">Core Disclosed Finding: </span>
                  <span>{activeCitation.claim}</span>
                </div>

                {/* Verbatim Excerpt */}
                {activeCitation.verbatim_text && (
                  <div className="mt-2 rounded bg-raised/70 p-2.5 border border-rule/50 font-serif italic text-[11.5px] text-ink/90 leading-relaxed break-words">
                    <span className="not-italic font-sans text-[10px] font-semibold uppercase tracking-wider text-faint block mb-1">
                      Primary Source Verbatim Excerpt:
                    </span>
                    "{activeCitation.verbatim_text}"
                  </div>
                )}

                {/* Confidence & Needs Review Warnings */}
                <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[11px]">
                  {typeof activeCitation.confidence === "number" && (
                    <div className="flex items-center gap-1 text-mute">
                      <span className="font-medium">Confidence:</span>
                      <span className={`font-mono font-semibold ${activeCitation.confidence >= 0.9 ? "text-up" : "text-warn"}`}>
                        {(activeCitation.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}

                  {activeCitation.needs_review && (
                    <div className="flex items-center gap-1 rounded bg-warn/15 border border-warn/30 px-2 py-0.5 text-warn font-semibold text-[11px]">
                      <span>⚠️ Needs Review</span>
                      {activeCitation.review_reason && (
                        <span className="font-normal text-ink text-[11px] ml-1">— {activeCitation.review_reason}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 8-Dimension Navigation Pills */}
          <div className="sticky top-0 z-20 mt-4 -mx-4 overflow-x-auto no-scrollbar border-y border-rule bg-paper px-4 py-2 md:mx-0 md:rounded md:border">
            <div className="flex min-w-max items-center gap-1.5">
              {DIMENSIONS.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => setActiveTab(d.id)}
                  className={`rounded-full px-3 py-1 text-xs transition-colors ${
                    activeTab === d.id
                      ? "bg-accent font-semibold text-paper"
                      : "bg-raised text-mute hover:text-ink hover:bg-raised/80"
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>

          {/* Dimension Cards */}
          <div className="mt-4 space-y-4">
            {/* DIMENSION 1: BUSINESS SNAPSHOT */}
            {(activeTab === "all" || activeTab === "business") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🏢</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      1. Business Snapshot
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dossier.business_snapshot.citations.map((cId) => (
                      <CitationChip
                        key={cId}
                        id={cId}
                        citations={citations}
                        onSelect={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>

                <p className="mt-3 text-xs leading-relaxed text-mute">
                  {dossier.business_snapshot.description}
                </p>

                {/* Segment Mix Visualizer */}
                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-ink">
                    <span>Segment Revenue Mix (Gross Value of Sales & Services)</span>
                    <span className="text-mute font-normal text-[11px]">Source: Statutory Results Page 17</span>
                  </div>

                  {/* Horizontal Bar */}
                  <div className="mt-2 flex h-5 w-full overflow-hidden rounded bg-paper border border-rule text-[10px] text-paper font-semibold">
                    <div
                      style={{ width: "57.5%" }}
                      className="bg-amber-600 flex items-center justify-center truncate px-1"
                      title="Oil to Chemicals: 57.5%"
                    >
                      O2C 57.5%
                    </div>
                    <div
                      style={{ width: "22.8%" }}
                      className="bg-emerald-600 flex items-center justify-center truncate px-1"
                      title="Retail: 22.8%"
                    >
                      Retail 22.8%
                    </div>
                    <div
                      style={{ width: "12.0%" }}
                      className="bg-teal-600 flex items-center justify-center truncate px-1"
                      title="Digital / Jio: 12.0%"
                    >
                      Jio 12%
                    </div>
                    <div
                      style={{ width: "6.3%" }}
                      className="bg-indigo-600 flex items-center justify-center truncate px-1"
                      title="Others: 6.3%"
                    >
                      6.3%
                    </div>
                    <div
                      style={{ width: "1.5%" }}
                      className="bg-rose-600 flex items-center justify-center truncate px-1"
                      title="Gas: 1.5%"
                    >
                      1.5%
                    </div>
                  </div>

                  {/* Segments Table */}
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-left text-xs min-w-[320px]">
                      <thead>
                        <tr className="border-b border-rule/60 text-[11px] text-faint">
                          <th className="py-1.5 font-medium">Segment</th>
                          <th className="py-1.5 text-right font-medium">Revenue (₹ Cr)</th>
                          <th className="py-1.5 text-right font-medium">Mix %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-rule/40 font-mono text-[12px]">
                        {dossier.business_snapshot.segments.map((seg, idx) => (
                          <tr key={idx} className={seg.is_elimination ? "text-faint italic" : ""}>
                            <td className="py-1.5 font-sans font-medium text-ink">{seg.name}</td>
                            <td className="py-1.5 text-right">{fmtCr(seg.revenue_cr)}</td>
                            <td className="py-1.5 text-right">
                              {seg.is_elimination ? "—" : `${seg.contribution_pct}%`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Core Platforms Grid */}
                <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  {dossier.business_snapshot.core_platforms.map((p, idx) => (
                    <div key={idx} className="rounded border border-rule/70 bg-paper/50 p-2.5 text-xs">
                      <span className="font-semibold text-ink">{p.platform}</span>
                      <p className="mt-0.5 text-[11.5px] text-mute">{p.role}</p>
                    </div>
                  ))}
                </div>

                {/* FY26 Operational Scale & Moats (Integrated Annual Report) */}
                {dossier.business_snapshot.annual_report_operational_scale_fy26 && (
                  <div className="mt-4 rounded border border-indigo-500/25 bg-indigo-500/5 p-3.5">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-indigo-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">📘</span>
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-700 dark:text-indigo-300">
                          Operational Scale & Moats (Annual Report FY2025–26)
                        </h4>
                      </div>
                      <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 dark:text-indigo-300 border border-indigo-500/20">
                        Audited AR Disclosures
                      </span>
                    </div>

                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.retail_scale && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">Reliance Retail Scale</span>
                            <CitationChip id="cit-ar-p7-retail-scale" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.retail_scale}
                          </p>
                        </div>
                      )}
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.digital_services_scale && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">Jio Telecom & AI Scale</span>
                            <CitationChip id="cit-ar-p9-jio-scale" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.digital_services_scale}
                          </p>
                        </div>
                      )}
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.media_and_entertainment && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">Media (JioStar Platform)</span>
                            <CitationChip id="cit-ar-p11-media" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.media_and_entertainment}
                          </p>
                        </div>
                      )}
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.o2c_refining_and_petchem && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">O2C Jamnagar Integration</span>
                            <CitationChip id="cit-ar-p13-o2c" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.o2c_refining_and_petchem}
                          </p>
                        </div>
                      )}
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.oil_and_gas_upstream && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">Oil & Gas (KG D6 Deepwater)</span>
                            <CitationChip id="cit-ar-p14-oilgas" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.oil_and_gas_upstream}
                          </p>
                        </div>
                      )}
                      {dossier.business_snapshot.annual_report_operational_scale_fy26.new_energy_gigafactories && (
                        <div className="rounded bg-paper/85 p-2.5 border border-rule/60 text-xs">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-semibold text-ink">Jamnagar Green Energy Complex</span>
                            <CitationChip id="cit-ar-p15-solar-10gwp" citations={citations} onSelect={setActiveCitation} />
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute leading-relaxed">
                            {dossier.business_snapshot.annual_report_operational_scale_fy26.new_energy_gigafactories}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* DIMENSION 2: FINANCIAL SNAPSHOT */}
            {(activeTab === "all" || activeTab === "financial") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">📊</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      2. Financial Snapshot
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dossier.financial_snapshot.citations.map((cId) => (
                      <CitationChip
                        key={cId}
                        id={cId}
                        citations={citations}
                        onSelect={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>

                {/* Headline Metrics Grid */}
                <div className="mt-3.5 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Revenue from Operations</span>
                    <span className="mt-1 font-mono text-base font-bold text-ink block">
                      {fmtCr(dossier.financial_snapshot.revenue_from_operations_cr)}
                    </span>
                    <span className="text-[10px] text-faint">Statutory Top Line</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Reported EBITDA</span>
                    <span className="mt-1 font-mono text-base font-bold text-up block">
                      {fmtCr(dossier.financial_snapshot.reported_ebitda_cr)}
                    </span>
                    <span className="text-[10px] text-faint">Deck Disclosure</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Derived Operating EBITDA</span>
                    <span className="mt-1 font-mono text-base font-bold text-ink block">
                      {fmtCr(dossier.financial_snapshot.derived_operating_ebitda_cr)}
                    </span>
                    <span className="text-[10px] text-faint">Excluding Other Income</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Headline PAT</span>
                    <span className="mt-1 font-mono text-base font-bold text-up block">
                      {fmtCr(dossier.financial_snapshot.headline_pat_cr)}
                    </span>
                    <span className="text-[10px] text-faint">Incl. Associates (₹300 Cr)</span>
                  </div>
                </div>

                {/* Margins */}
                <div className="mt-3 flex flex-wrap gap-4 text-xs font-mono text-mute bg-paper/40 p-2.5 rounded border border-rule/60">
                  <div>
                    <span className="text-faint font-sans">Operating Margin: </span>
                    <span className="font-semibold text-ink">{dossier.financial_snapshot.operating_margin_pct}%</span>
                  </div>
                  <div>
                    <span className="text-faint font-sans">Net Profit Margin: </span>
                    <span className="font-semibold text-ink">{dossier.financial_snapshot.net_profit_margin_pct}%</span>
                  </div>
                  <div>
                    <span className="text-faint font-sans">Owners' PAT: </span>
                    <span className="font-semibold text-ink">{fmtCr(dossier.financial_snapshot.owners_pat_cr)}</span>
                  </div>
                </div>

                {/* Reconciliation Note Card */}
                {dossier.financial_snapshot.ebitda_reconciliation_note && (
                  <div className="mt-3 rounded border border-accent/20 bg-accent-soft/20 p-2.5 text-[11.5px] text-ink">
                    <span className="font-semibold text-accent">Financial Line Item Reconciliation: </span>
                    {dossier.financial_snapshot.ebitda_reconciliation_note}
                  </div>
                )}

                {/* Full-Year FY26 Financials from Annual Report */}
                {dossier.financial_snapshot.annual_report_fy26_financials && (
                  <div className="mt-3.5 rounded border border-indigo-500/25 bg-indigo-500/5 p-3.5 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-indigo-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">📘</span>
                        <span className="font-semibold text-indigo-700 dark:text-indigo-300">
                          Full-Year FY26 Audited Milestones (Integrated Annual Report)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.financial_snapshot.annual_report_fy26_financials.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10.5px] text-mute block">FY26 Gross Turnover</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-ink block">
                          {fmtCr(dossier.financial_snapshot.annual_report_fy26_financials.gross_revenue_cr)}
                        </span>
                        <span className="text-[9.5px] text-faint">Consolidated Top Line</span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10.5px] text-mute block">FY26 Consolidated EBITDA</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-up block">
                          {fmtCr(dossier.financial_snapshot.annual_report_fy26_financials.ebitda_cr)}
                        </span>
                        <span className="text-[9.5px] text-faint">
                          {dossier.financial_snapshot.annual_report_fy26_financials.reported_ebitda_margin_pct}% Margin
                        </span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10.5px] text-mute block">FY26 Consolidated PAT</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-up block">
                          {fmtCr(dossier.financial_snapshot.annual_report_fy26_financials.pat_cr)}
                        </span>
                        <span className="text-[9.5px] text-up font-semibold">$10B Milestone</span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10.5px] text-mute block">Gross Fixed Assets</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-ink block">
                          {fmtCr(dossier.financial_snapshot.annual_report_fy26_financials.gross_fixed_assets_cr)}
                        </span>
                        <span className="text-[9.5px] text-faint">Note 1 PP&E</span>
                      </div>
                    </div>

                    {dossier.financial_snapshot.annual_report_fy26_financials.pat_milestone_note && (
                      <p className="mt-2 text-[11px] text-mute italic">
                        ★ {dossier.financial_snapshot.annual_report_fy26_financials.pat_milestone_note}
                      </p>
                    )}
                  </div>
                )}

                {/* Q2 FY26 Earnings Call Management Commentary (Concall Transcript) */}
                {dossier.financial_snapshot.concall_q2_fy26_commentary && (
                  <div className="mt-3 rounded border border-purple-500/25 bg-purple-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-purple-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">🎙️</span>
                        <span className="font-semibold text-purple-700 dark:text-purple-300">
                          Q2 FY26 Earnings Call Management Commentary (Concall Transcript)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.financial_snapshot.concall_q2_fy26_commentary.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11.5px]">
                      {dossier.financial_snapshot.concall_q2_fy26_commentary.speaker && (
                        <span className="rounded bg-purple-500/10 px-2 py-0.5 font-semibold text-purple-700 dark:text-purple-300 border border-purple-500/20">
                          🎙️ {dossier.financial_snapshot.concall_q2_fy26_commentary.speaker}
                        </span>
                      )}
                      {dossier.financial_snapshot.concall_q2_fy26_commentary.jio_ebitda_growth_pct && (
                        <span className="rounded bg-paper px-2 py-0.5 font-mono text-ink border border-rule">
                          Jio EBITDA YoY: <strong className="text-up">+{dossier.financial_snapshot.concall_q2_fy26_commentary.jio_ebitda_growth_pct}%</strong>
                        </span>
                      )}
                      {dossier.financial_snapshot.concall_q2_fy26_commentary.retail_ebitda_growth_pct && (
                        <span className="rounded bg-paper px-2 py-0.5 font-mono text-ink border border-rule">
                          Retail EBITDA YoY: <strong className="text-up">+{dossier.financial_snapshot.concall_q2_fy26_commentary.retail_ebitda_growth_pct}%</strong>
                        </span>
                      )}
                    </div>

                    {dossier.financial_snapshot.concall_q2_fy26_commentary.commentary_note && (
                      <p className="mt-2 text-[11.5px] text-mute leading-relaxed font-serif italic">
                        "{dossier.financial_snapshot.concall_q2_fy26_commentary.commentary_note}"
                      </p>
                    )}
                  </div>
                )}
              </section>
            )}

            {/* DIMENSION 3: TRAJECTORY */}
            {(activeTab === "all" || activeTab === "trajectory") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">📈</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      3. Trajectory & Direction
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dossier.trajectory.citations.map((cId) => (
                      <CitationChip
                        key={cId}
                        id={cId}
                        citations={citations}
                        onSelect={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>

                <p className="mt-2.5 text-xs text-mute font-medium">
                  {dossier.trajectory.headline_direction}
                </p>

                <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                  {/* Growing Platforms */}
                  <div className="rounded border border-up/30 bg-up/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-up">
                      <span>▲</span>
                      <span>Growing Segments</span>
                    </div>
                    <div className="mt-2 space-y-2">
                      {dossier.trajectory.growing_segments.map((seg, idx) => (
                        <div key={idx} className="rounded bg-paper/80 p-2.5 text-xs border border-up/20">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-ink">{seg.segment}</span>
                            <span className="font-mono font-bold text-up">+{seg.yoy_ebitda_growth_pct}% YoY</span>
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute">{seg.drivers}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Compressing Platforms */}
                  <div className="rounded border border-warn/30 bg-warn/5 p-3">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-warn">
                      <span>▼</span>
                      <span>Compressing / Margin Headwinds</span>
                    </div>
                    <div className="mt-2 space-y-2">
                      {dossier.trajectory.compressing_segments.map((seg, idx) => (
                        <div key={idx} className="rounded bg-paper/80 p-2.5 text-xs border border-warn/20">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-ink">{seg.segment}</span>
                            <span className="font-mono font-bold text-warn">{seg.yoy_ebitda_growth_pct}% YoY</span>
                          </div>
                          <p className="mt-1 text-[11.5px] text-mute">{seg.drivers}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Multi-Year Structural Trajectory (Annual Report & Concall Evidence) */}
                {dossier.trajectory.multi_year_structural_trajectory && (
                  <div className="mt-3.5 rounded border border-indigo-500/25 bg-indigo-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-indigo-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">📘</span>
                        <span className="font-semibold text-indigo-700 dark:text-indigo-300">
                          Multi-Year Compounding & Trajectory (Annual Report & Concall Evidence)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.trajectory.multi_year_structural_trajectory.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>
                    <div className="mt-2.5 space-y-1.5 text-[11.5px] text-mute leading-relaxed">
                      {dossier.trajectory.multi_year_structural_trajectory.revenue_cagr_narrative && (
                        <p>• {dossier.trajectory.multi_year_structural_trajectory.revenue_cagr_narrative}</p>
                      )}
                      {dossier.trajectory.multi_year_structural_trajectory.concall_pacing_trend && (
                        <p>• {dossier.trajectory.multi_year_structural_trajectory.concall_pacing_trend}</p>
                      )}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* DIMENSION 4: BALANCE SHEET */}
            {(activeTab === "all" || activeTab === "balance_sheet") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🏛️</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      4. Balance Sheet & Leverage
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dossier.balance_sheet.citations.map((cId) => (
                      <CitationChip
                        key={cId}
                        id={cId}
                        citations={citations}
                        onSelect={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>

                {/* Mobile scroll hint */}
                <p className="mt-2 text-[11px] text-faint sm:hidden">
                  ↔ Swipe table horizontally to view full breakdown
                </p>

                {/* Balance Sheet Line Items Table */}
                <div className="mt-2 sm:mt-3.5 overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[480px]">
                    <thead>
                      <tr className="border-b border-rule/60 text-[11px] text-faint">
                        <th className="py-1.5 font-medium">Metric</th>
                        <th className="py-1.5 text-right font-medium">Disclosed Figure</th>
                        <th className="py-1.5 text-right font-medium">Nature / Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule/40 font-mono text-[12px]">
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Statutory Gross Borrowings</td>
                        <td className="py-1.5 text-right font-bold text-ink">{fmtCr(dossier.balance_sheet.gross_debt_cr)}</td>
                        <td className="py-1.5 text-right text-mute font-sans">NC (₹289,744) + Current (₹95,208)</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Cash & Current Investments</td>
                        <td className="py-1.5 text-right text-up">{fmtCr(dossier.balance_sheet.total_liquid_assets_cr)}</td>
                        <td className="py-1.5 text-right text-mute font-sans">Cash (₹181,723) + Inv (₹78,591)</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Statutory Net Debt</td>
                        <td className="py-1.5 text-right font-bold text-ink">{fmtCr(dossier.balance_sheet.statutory_net_debt_cr)}</td>
                        <td className="py-1.5 text-right text-mute font-sans">Balance Sheet (Page 12)</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Management Reported Net Debt</td>
                        <td className="py-1.5 text-right text-accent font-bold">{fmtCr(dossier.balance_sheet.management_reported_net_debt_cr)}</td>
                        <td className="py-1.5 text-right text-mute font-sans">Presentation Slide 12 ($12.2 Bn)</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Net Debt to EBITDA (Annualized)</td>
                        <td className="py-1.5 text-right font-bold text-up">{dossier.balance_sheet.management_net_debt_to_ebitda}x</td>
                        <td className="py-1.5 text-right text-mute font-sans">Reduced from 0.57x in Jun-26</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Debt to Equity Ratio</td>
                        <td className="py-1.5 text-right">{dossier.balance_sheet.debt_equity_ratio}x</td>
                        <td className="py-1.5 text-right text-mute font-sans">Page 11 Statutory Ratio</td>
                      </tr>
                      <tr>
                        <td className="py-1.5 font-sans font-medium text-ink">Total Equity vs Net Worth</td>
                        <td className="py-1.5 text-right">{fmtCr(dossier.balance_sheet.total_equity_cr)}</td>
                        <td className="py-1.5 text-right text-mute font-sans">Net Worth: {fmtCr(dossier.balance_sheet.net_worth_cr)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Reconciliation Footnotes */}
                <div className="mt-3 space-y-1.5 text-[11px] text-mute bg-paper/50 p-2.5 rounded border border-rule/50">
                  <p>• {dossier.balance_sheet.net_debt_reconciliation_note}</p>
                  <p>• {dossier.balance_sheet.equity_reconciliation_note}</p>
                  <p>• {dossier.balance_sheet.interest_reconciliation_note}</p>
                </div>

                {/* Statutory Notes on Debt, Spectrum & Capital Commitments (Annual Report FY26) */}
                {dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure && (
                  <div className="mt-3.5 rounded border border-indigo-500/25 bg-indigo-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-indigo-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">📘</span>
                        <span className="font-semibold text-indigo-700 dark:text-indigo-300">
                          Statutory Notes on Debt, Spectrum & Capex Contracts (Annual Report FY26)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded bg-paper/85 p-2 border border-rule/50">
                        <span className="text-[10px] text-mute block">Note 16 Non-Current Borrowings</span>
                        <span className="font-mono text-xs font-bold text-ink">
                          {fmtCr(dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.non_current_borrowings_cr)}
                        </span>
                      </div>
                      <div className="rounded bg-paper/85 p-2 border border-rule/50">
                        <span className="text-[10px] text-mute block">Current Maturities of Long-Term Debt</span>
                        <span className="font-mono text-xs font-bold text-ink">
                          {fmtCr(dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.current_borrowings_maturities_cr)}
                        </span>
                      </div>
                      <div className="rounded bg-paper/85 p-2 border border-rule/50">
                        <span className="text-[10px] text-mute block">Note 17 Spectrum Liabilities</span>
                        <span className="font-mono text-xs font-bold text-warn">
                          {fmtCr(dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.deferred_spectrum_liabilities_cr)}
                        </span>
                      </div>
                      <div className="rounded bg-paper/85 p-2 border border-rule/50">
                        <span className="text-[10px] text-mute block">Note 34 Unexecuted Capex Contracts</span>
                        <span className="font-mono text-xs font-bold text-down">
                          {fmtCr(dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.capital_commitments_contracts_remaining_cr)}
                        </span>
                      </div>
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px] text-mute">
                      <span className="rounded bg-paper px-2 py-0.5 border border-rule">
                        DSCR: <strong className="text-ink font-mono">{dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.dscr_fy26}x</strong>
                      </span>
                      {dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.samurai_loan_jpy_bn && (
                        <span className="rounded bg-paper px-2 py-0.5 border border-rule">
                          Samurai Loan: <strong className="text-ink font-mono">¥{dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.samurai_loan_jpy_bn}B</strong>
                        </span>
                      )}
                      {dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.nexi_facility && (
                        <span className="rounded bg-paper px-2 py-0.5 border border-rule">
                          NEXI Facility: <span className="text-ink">{dossier.balance_sheet.annual_report_fy26_debt_and_capital_structure.nexi_facility}</span>
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Concall Capital Allocation Commentary */}
                {dossier.balance_sheet.concall_q2_fy26_debt_commentary && (
                  <div className="mt-3 rounded border border-purple-500/25 bg-purple-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-purple-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">🎙️</span>
                        <span className="font-semibold text-purple-700 dark:text-purple-300">
                          Compute Capex & Balance Sheet Insulation (Concall Transcript)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.balance_sheet.concall_q2_fy26_debt_commentary.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>
                    <div className="mt-2 text-[11.5px] text-mute leading-relaxed">
                      <span className="font-semibold text-purple-700 dark:text-purple-300">
                        {dossier.balance_sheet.concall_q2_fy26_debt_commentary.speaker}:
                      </span>{" "}
                      <span className="italic font-serif text-ink">"{dossier.balance_sheet.concall_q2_fy26_debt_commentary.statement}"</span>
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* DIMENSION 5: CASH QUALITY */}
            {(activeTab === "all" || activeTab === "cash_quality") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">💧</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      5. Cash Quality & Conversion
                    </h3>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {dossier.cash_quality.citations.map((cId) => (
                      <CitationChip
                        key={cId}
                        id={cId}
                        citations={citations}
                        onSelect={setActiveCitation}
                      />
                    ))}
                  </div>
                </div>

                {/* Period Badge */}
                <div className="mt-2.5 inline-flex items-center gap-1.5 rounded bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
                  <span>📅</span>
                  <span>{dossier.cash_quality.period}</span>
                </div>
                <p className="mt-1 text-[11px] text-faint">
                  {dossier.cash_quality.period_scope_note}
                </p>

                {/* Conversion KPIs */}
                <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">H1 Operating Cash Flow (CFO)</span>
                    <span className="mt-1 font-mono text-base font-bold text-up block">
                      {fmtCr(dossier.cash_quality.cfo_cr)}
                    </span>
                    <span className="text-[10px] text-faint">Core Operations</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">H1 Capital Expenditure</span>
                    <span className="mt-1 font-mono text-base font-bold text-down block">
                      {fmtCr(dossier.cash_quality.capex_h1_cr)}
                    </span>
                    <span className="text-[10px] text-faint">PPE, Spectrum, Assets</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Free Cash Flow (FCF)</span>
                    <span className="mt-1 font-mono text-base font-bold text-up block">
                      {fmtCr(dossier.cash_quality.fcf_h1_cr)}
                    </span>
                    <span className="text-[10px] text-up font-semibold">Self-Funding Surplus</span>
                  </div>

                  <div className="rounded border border-rule bg-paper/70 p-3 text-center">
                    <span className="text-[11px] font-medium text-mute block">Cash Conversion (CFO / PBT)</span>
                    <span className="mt-1 font-mono text-base font-bold text-up block">
                      {dossier.cash_quality.cfo_to_pbt_pct}%
                    </span>
                    <span className="text-[10px] text-up font-semibold">High Quality</span>
                  </div>
                </div>

                <div className="mt-3 rounded border border-up/20 bg-up/5 p-2.5 text-xs text-ink">
                  <span className="font-semibold text-up">Cash Conversion Verdict: </span>
                  {dossier.cash_quality.cash_quality_verdict}
                </div>

                {/* Full-Year FY26 Statutory Cash Flows (Annual Report) */}
                {dossier.cash_quality.annual_report_fy26_cash_flows && (
                  <div className="mt-3.5 rounded border border-indigo-500/25 bg-indigo-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-indigo-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">📘</span>
                        <span className="font-semibold text-indigo-700 dark:text-indigo-300">
                          Full-Year FY26 Statutory Cash Quality (Integrated Annual Report)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.cash_quality.annual_report_fy26_cash_flows.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10px] text-mute block">Cash from Operations (Pre-Tax)</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-ink block">
                          {fmtCr(dossier.cash_quality.annual_report_fy26_cash_flows.cash_generated_from_operations_cr)}
                        </span>
                        <span className="text-[9.5px] text-faint">Before Tax & Working Cap</span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10px] text-mute block">FY26 Operating Cash Flow (CFO)</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-up block">
                          {fmtCr(dossier.cash_quality.annual_report_fy26_cash_flows.cfo_cr)}
                        </span>
                        <span className="text-[9.5px] text-up font-semibold">Post Working Cap</span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10px] text-mute block">FY26 Profit Before Tax (PBT)</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-ink block">
                          {fmtCr(dossier.cash_quality.annual_report_fy26_cash_flows.pbt_fy26_cr)}
                        </span>
                        <span className="text-[9.5px] text-faint">Consolidated PBT</span>
                      </div>
                      <div className="rounded bg-paper/85 p-2.5 border border-rule/50 text-center">
                        <span className="text-[10px] text-mute block">CFO / PBT Cash Conversion</span>
                        <span className="mt-0.5 font-mono text-sm font-bold text-up block">
                          {dossier.cash_quality.annual_report_fy26_cash_flows.cfo_to_pbt_pct}%
                        </span>
                        <span className="text-[9.5px] text-up font-semibold">High Quality Conversion</span>
                      </div>
                    </div>

                    {dossier.cash_quality.annual_report_fy26_cash_flows.cash_conversion_verdict && (
                      <p className="mt-2 text-[11.5px] text-mute leading-relaxed">
                        <span className="font-semibold text-ink">FY26 Cash Audit Verdict: </span>
                        {dossier.cash_quality.annual_report_fy26_cash_flows.cash_conversion_verdict}
                      </p>
                    )}
                  </div>
                )}

                {/* Concall Cash Reinvestment Commentary */}
                {dossier.cash_quality.concall_q2_fy26_cash_reinvestment && (
                  <div className="mt-3 rounded border border-purple-500/25 bg-purple-500/5 p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-1 border-b border-purple-500/20 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">🎙️</span>
                        <span className="font-semibold text-purple-700 dark:text-purple-300">
                          Reinvestment & Internal Accruals Guidance (Concall Transcript)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1">
                        {(dossier.cash_quality.concall_q2_fy26_cash_reinvestment.citations ?? []).map((cId) => (
                          <CitationChip key={cId} id={cId} citations={citations} onSelect={setActiveCitation} />
                        ))}
                      </div>
                    </div>
                    <p className="mt-2 text-[11.5px] text-mute italic font-serif leading-relaxed">
                      "{dossier.cash_quality.concall_q2_fy26_cash_reinvestment.statement}"
                    </p>
                  </div>
                )}
              </section>
            )}

            {/* DIMENSION 6: NARRATIVE VS NUMBERS */}
            {(activeTab === "all" || activeTab === "narrative") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">⚖️</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      6. Narrative vs. Numbers (Management Audit)
                    </h3>
                  </div>
                </div>

                <p className="mt-2 text-xs text-mute">
                  Evaluating what management promised or claimed in their investor presentations against the verified statutory numbers.
                </p>

                <div className="mt-3.5 space-y-3">
                  {dossier.narrative_vs_numbers.map((item, idx) => {
                    const verdictClass =
                      item.verdict === "Agreement"
                        ? "bg-up/10 text-up border border-up/25"
                        : item.verdict === "Divergence"
                        ? "bg-down/10 text-down border border-down/25"
                        : item.verdict === "Qualified Agreement"
                        ? "bg-warn/10 text-warn border border-warn/25"
                        : item.verdict === "Caution"
                        ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/25"
                        : item.verdict === "Auditor Scrutiny"
                        ? "bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/25"
                        : "bg-rule text-mute border border-rule";

                    return (
                      <div
                        key={idx}
                        className="rounded border border-rule bg-paper/60 p-3.5 transition-colors"
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-ink text-xs">{item.dimension}</span>
                            {item.reporting_period && (
                              <span className="rounded bg-paper px-1.5 py-0.2 text-[10px] font-mono text-faint border border-rule/60">
                                📅 {item.reporting_period}
                              </span>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-2 shrink-0">
                            <span className={`rounded px-2 py-0.5 text-[10.5px] font-semibold ${verdictClass}`}>
                              {item.verdict}
                            </span>
                            <div className="flex flex-wrap gap-1">
                              {item.citations.map((cId) => (
                                <CitationChip
                                  key={cId}
                                  id={cId}
                                  citations={citations}
                                  onSelect={setActiveCitation}
                                />
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* Needs Review Warning Banner (Req 4) */}
                        {item.needs_review && (
                          <div className="mt-2.5 rounded bg-warn/15 border border-warn/30 p-2 text-[11px] text-warn flex items-start gap-1.5 font-medium">
                            <span className="text-xs">⚠️</span>
                            <div>
                              <strong className="font-semibold">Needs Review:</strong> {item.review_reason}
                            </div>
                          </div>
                        )}

                        <div className="mt-2.5 grid grid-cols-1 gap-2 md:grid-cols-2 text-xs">
                          <div className="rounded bg-raised p-2 border border-rule/50">
                            <span className="text-[10.5px] font-medium text-mute block">Management Narrative:</span>
                            <p className="mt-0.5 text-ink italic font-serif text-[12px] leading-relaxed">"{item.management_narrative}"</p>
                          </div>
                          <div className="rounded bg-raised p-2 border border-rule/50">
                            <span className="text-[10.5px] font-medium text-mute block">Statutory Financial Fact:</span>
                            <p className="mt-0.5 text-ink font-mono text-[12px] leading-relaxed">{item.statutory_number}</p>
                          </div>
                        </div>

                        <div className="mt-2 text-[11.5px] text-mute leading-relaxed">
                          <span className="font-medium text-ink">Analytical Breakdown: </span>
                          {item.analysis}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* DIMENSION 7: GUIDANCE */}
            {(activeTab === "all" || activeTab === "guidance") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🎯</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      7. Explicit Management Guidance & Commitments
                    </h3>
                  </div>
                </div>

                {/* Mobile scroll hint */}
                <p className="mt-2 text-[11px] text-faint sm:hidden">
                  ↔ Swipe table horizontally for targets and actuals
                </p>

                <div className="mt-2 sm:mt-3.5 overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[560px]">
                    <thead>
                      <tr className="border-b border-rule/60 text-[11px] text-faint">
                        <th className="py-2 font-medium">Metric / Initiative</th>
                        <th className="py-2 font-medium">Forward Target / Horizon</th>
                        <th className="py-2 font-medium">Reported Performance</th>
                        <th className="py-2 text-right font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-rule/40 text-[12px]">
                      {dossier.guidance.map((item, idx) => {
                        const statusClass =
                          item.status === "Delivered"
                            ? "bg-up/10 text-up border border-up/25"
                            : item.status === "In Progress"
                            ? "bg-accent-soft text-accent border border-accent/25"
                            : item.status === "Operational Target"
                            ? "bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/25"
                            : item.status === "Future Target"
                            ? "bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/25"
                            : item.status === "Not Delivered"
                            ? "bg-down/10 text-down border border-down/25"
                            : "bg-rule text-mute border border-rule";

                        return (
                          <tr key={idx}>
                            <td className="py-2.5 font-medium text-ink align-top">
                              <div>{item.metric_or_area}</div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                {item.citations.map((cId) => (
                                  <CitationChip
                                    key={cId}
                                    id={cId}
                                    citations={citations}
                                    onSelect={setActiveCitation}
                                  />
                                ))}
                              </div>
                              {/* Needs Review Warning (Req 4) */}
                              {item.needs_review && (
                                <div className="mt-1.5 rounded bg-warn/15 border border-warn/30 p-1.5 text-[10.5px] text-warn leading-tight">
                                  <strong>⚠️ Needs Review:</strong> {item.review_reason}
                                </div>
                              )}
                            </td>
                            <td className="py-2.5 text-mute align-top">
                              <span className="font-semibold text-ink block">{item.target_period}</span>
                              <span className="text-[11.5px] block">{item.commitment}</span>
                              {item.relative_time_context && (
                                <span className="mt-0.5 inline-block text-[10.5px] text-faint font-mono">
                                  ⏱️ {item.relative_time_context}
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 text-mute text-[11.5px] align-top">{item.reported_actual}</td>
                            <td className="py-2.5 text-right align-top">
                              <span className={`inline-block rounded px-2 py-0.5 text-[10.5px] font-semibold ${statusClass}`}>
                                {item.status}
                              </span>
                              {typeof item.confidence === "number" && item.confidence < 1.0 && (
                                <span className="mt-0.5 block font-mono text-[9.5px] text-faint">
                                  {(item.confidence * 100).toFixed(0)}% conf
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Shortcut banner to Promise vs Delivered */}
                <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 rounded border border-accent/30 bg-accent-soft/40 p-3 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🎯</span>
                    <div>
                      <span className="font-semibold text-accent">Audited Multi-Quarter Tracking:</span>{" "}
                      <span className="text-mute">
                        Explore multi-quarter execution, source filings, and delivery score in the Promise vs Delivered engine.
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("commitments");
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                    className="rounded bg-accent px-2.5 py-1 text-[11px] font-semibold text-paper hover:bg-accent/90 shrink-0 self-start sm:self-auto"
                  >
                    View Promise vs Delivered →
                  </button>
                </div>
              </section>
            )}

            {/* DIMENSION 8: BULL VS BEAR */}
            {(activeTab === "all" || activeTab === "bull_bear") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🐂 🐻</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      8. Bull vs. Bear Case
                    </h3>
                  </div>
                </div>

                <div className="mt-3.5 grid grid-cols-1 gap-3.5 md:grid-cols-2">
                  {/* Bull Case */}
                  <div className="rounded border border-up/30 bg-up/5 p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-up">
                      <span>🐂</span>
                      <span>The Bull Case (Primary Strengths)</span>
                    </div>

                    <div className="mt-3 space-y-2.5">
                      {dossier.bull_vs_bear.bull_case.map((item, idx) => (
                        <div key={idx} className="rounded bg-paper p-3 text-xs border border-up/20">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold text-ink">{item.point}</span>
                              {item.source_period && (
                                <span className="rounded bg-raised px-1.5 py-0.2 text-[9.5px] font-mono text-faint border border-rule/50">
                                  📅 {item.source_period}
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-1 shrink-0">
                              {item.citations.map((cId) => (
                                <CitationChip
                                  key={cId}
                                  id={cId}
                                  citations={citations}
                                  onSelect={setActiveCitation}
                                />
                              ))}
                            </div>
                          </div>
                          {item.needs_review && (
                            <div className="mt-1.5 rounded bg-warn/15 border border-warn/30 p-1.5 text-[10.5px] text-warn">
                              <strong>⚠️ Needs Review:</strong> {item.review_reason}
                            </div>
                          )}
                          <p className="mt-1.5 text-[11.5px] text-mute leading-relaxed">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Bear Case */}
                  <div className="rounded border border-down/30 bg-down/5 p-3.5">
                    <div className="flex items-center gap-2 text-xs font-bold text-down">
                      <span>🐻</span>
                      <span>The Bear Case (Key Risks & Vulnerabilities)</span>
                    </div>

                    <div className="mt-3 space-y-2.5">
                      {dossier.bull_vs_bear.bear_case.map((item, idx) => (
                        <div key={idx} className="rounded bg-paper p-3 text-xs border border-down/20">
                          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-semibold text-ink">{item.point}</span>
                              {item.source_period && (
                                <span className="rounded bg-raised px-1.5 py-0.2 text-[9.5px] font-mono text-faint border border-rule/50">
                                  📅 {item.source_period}
                                </span>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-1 shrink-0">
                              {item.citations.map((cId) => (
                                <CitationChip
                                  key={cId}
                                  id={cId}
                                  citations={citations}
                                  onSelect={setActiveCitation}
                                />
                              ))}
                            </div>
                          </div>
                          {item.needs_review && (
                            <div className="mt-1.5 rounded bg-warn/15 border border-warn/30 p-1.5 text-[10.5px] text-warn">
                              <strong>⚠️ Needs Review:</strong> {item.review_reason}
                            </div>
                          )}
                          <p className="mt-1.5 text-[11.5px] text-mute leading-relaxed">{item.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* DIMENSION 9: PROMISE VS DELIVERED */}
            {(activeTab === "all" || activeTab === "commitments") && (
              <section className="rounded border border-rule bg-raised p-4 md:p-5">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-1.5 border-b border-rule pb-2.5">
                  <div className="flex items-center gap-2">
                    <span className="text-base">🎯</span>
                    <h3 className="text-sm font-semibold tracking-tight md:text-base">
                      9. Promise vs Delivered (Management Track Record)
                    </h3>
                  </div>
                  <span className="rounded bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent">
                    P1.3 Delivery Engine
                  </span>
                </div>

                <CommitmentsSection
                  symbol={symbol}
                  companyName={dossier.company_name}
                  summary={commitmentsResponse?.summary ?? null}
                  commitments={commitmentsResponse?.commitments ?? []}
                  loading={commitmentsLoading}
                  error={commitmentsError}
                  onSelectReliance={() => selectCompany("RELIANCE")}
                />
              </section>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
