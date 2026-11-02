import { useState } from "react";
import type { FilingResultsResponse, MetricChange, MetricComparisonItem, ResultsCardStatement } from "../api";

interface ResultsCardProps {
  data: FilingResultsResponse;
  onClose?: () => void;
}

function DeltaBadge({ change }: { change: MetricChange }) {
  if (change.status === "UNAVAILABLE" || change.status === "NOT_APPLICABLE") {
    return <span className="text-[11px] font-mono text-faint">{change.label}</span>;
  }
  if (change.status === "TURNAROUND") {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold bg-accent-soft text-accent">
        Turnaround
      </span>
    );
  }
  if (change.status === "SWING_TO_LOSS") {
    return (
      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold bg-warn-soft text-warn">
        Swing to Loss
      </span>
    );
  }
  if (change.status === "GROWTH") {
    return (
      <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11.5px] font-semibold font-mono text-up bg-up/10">
        {change.label}
      </span>
    );
  }
  if (change.status === "DECLINE") {
    return (
      <span className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11.5px] font-semibold font-mono text-down bg-down/10">
        {change.label}
      </span>
    );
  }
  return <span className="text-[11.5px] font-mono text-mute">{change.label}</span>;
}

function fmt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function ResultsCard({ data, onClose }: ResultsCardProps) {
  const [nature, setNature] = useState<"consolidated" | "standalone">(data.primary_nature);
  const [showReconciliation, setShowReconciliation] = useState(false);

  const statement: ResultsCardStatement | undefined = data.statements[nature] ?? Object.values(data.statements)[0];
  if (!statement) return null;

  const m = statement.metrics;
  const isConsol = statement.nature === "consolidated";

  return (
    <div className="mt-3 rounded border border-rule bg-raised/70 p-3.5 shadow-sm md:p-4 text-ink">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule/60 pb-2.5">
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          <span className="rounded bg-accent/15 px-2 py-0.5 text-[11px] sm:text-[12px] font-bold text-accent">
            QUARTERLY RESULTS INTELLIGENCE
          </span>
          <span className="text-[12px] sm:text-[13px] font-bold tracking-tight">
            {statement.symbol} · {statement.period_label}
          </span>
          <span className="rounded bg-paper px-1.5 py-0.5 text-[10px] sm:text-[11px] text-mute border border-rule">
            ₹ Crore
          </span>
        </div>

        {/* Consolidated vs Standalone toggle */}
        <div className="flex items-center gap-1.5">
          {Object.keys(data.statements).length > 1 && (
            <div className="inline-flex rounded border border-rule bg-paper p-0.5 text-[10.5px] sm:text-[11px]">
              <button
                type="button"
                onClick={() => setNature("consolidated")}
                className={`rounded px-2 py-0.5 font-medium transition ${
                  nature === "consolidated" ? "bg-accent font-semibold text-paper" : "text-mute hover:text-ink"
                }`}
              >
                Consolidated
              </button>
              <button
                type="button"
                onClick={() => setNature("standalone")}
                className={`rounded px-2 py-0.5 font-medium transition ${
                  nature === "standalone" ? "bg-accent font-semibold text-paper" : "text-mute hover:text-ink"
                }`}
              >
                Standalone
              </button>
            </div>
          )}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-[12px] text-mute hover:text-ink px-1.5 py-0.5"
              aria-label="Close Results Card"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Financial Comparison Table */}
      <div className="mt-3 overflow-x-auto [scrollbar-width:thin]">
        <div className="text-[10px] text-faint sm:hidden mb-1 flex items-center gap-1">
          <span>↔</span>
          <span>Swipe table horizontally for QoQ and YoY metrics</span>
        </div>
        <table className="w-full text-left text-[12.5px] border-collapse min-w-[460px]">
          <thead>
            <tr className="border-b border-rule text-[11px] text-mute uppercase tracking-wider">
              <th className="py-1.5 pr-3 font-semibold">Key Metric</th>
              <th className="py-1.5 px-3 text-right font-semibold">Current Quarter</th>
              <th className="py-1.5 px-3 text-right font-semibold">Preceding Q (QoQ)</th>
              <th className="py-1.5 pl-3 text-right font-semibold">Same Q Prev FY (YoY)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule/40 font-mono">
            {/* 1. Revenue from Operations */}
            <tr className="hover:bg-paper/40">
              <td className="py-2.5 pr-3 font-sans font-medium text-ink">
                <div>Revenue from Operations</div>
                {m.gross_revenue.current && m.gross_revenue.current !== m.revenue.current && (
                  <div className="text-[11px] font-sans text-mute font-normal">
                    Gross: ₹{fmt(m.gross_revenue.current)} Cr · GST: ₹{fmt(m.gross_revenue.current - (m.revenue.current ?? 0))} Cr
                  </div>
                )}
              </td>
              <td className="py-2.5 px-3 text-right font-semibold text-ink">
                ₹{fmt(m.revenue.current)}
              </td>
              <td className="py-2.5 px-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.revenue.previous)}</div>
                <DeltaBadge change={m.revenue.qoq} />
              </td>
              <td className="py-2.5 pl-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.revenue.yoy)}</div>
                <DeltaBadge change={m.revenue.yoy_cmp} />
              </td>
            </tr>

            {/* 2. EBITDA (Reported & Derived) */}
            {m.reported_ebitda.current && (
              <tr className="hover:bg-paper/40 bg-accent/5">
                <td className="py-2 pr-3 font-sans font-medium text-ink">
                  <div className="flex items-center gap-1.5">
                    <span>Reported EBITDA</span>
                    <span className="rounded bg-accent/20 px-1 py-0.2 text-[10px] text-accent font-semibold">
                      Company Disclosed
                    </span>
                  </div>
                  <div className="text-[10.5px] font-sans text-mute">Includes other income / IR presentation definition</div>
                </td>
                <td className="py-2 px-3 text-right font-semibold text-accent">
                  ₹{fmt(m.reported_ebitda.current)}
                </td>
                <td className="py-2 px-3 text-right">
                  <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.reported_ebitda.previous)}</div>
                  <DeltaBadge change={m.reported_ebitda.qoq} />
                </td>
                <td className="py-2 pl-3 text-right">
                  <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.reported_ebitda.yoy)}</div>
                  <DeltaBadge change={m.reported_ebitda.yoy_cmp} />
                </td>
              </tr>
            )}

            <tr className="hover:bg-paper/40">
              <td className="py-2 pr-3 font-sans font-medium text-ink">
                <div className="flex items-center gap-1.5">
                  <span>Derived Operating EBITDA</span>
                  <span className="rounded bg-paper px-1 py-0.2 text-[10px] text-mute border border-rule">
                    Core Operations
                  </span>
                </div>
                <div className="text-[10.5px] font-sans text-mute font-normal">
                  PBT + Finance Costs + Depr − Other Income
                </div>
              </td>
              <td className="py-2 px-3 text-right font-semibold text-ink">
                ₹{fmt(m.derived_ebitda.current)}
              </td>
              <td className="py-2 px-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.derived_ebitda.previous)}</div>
                <DeltaBadge change={m.derived_ebitda.qoq} />
              </td>
              <td className="py-2 pl-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.derived_ebitda.yoy)}</div>
                <DeltaBadge change={m.derived_ebitda.yoy_cmp} />
              </td>
            </tr>

            {/* 3. Profit Before Tax */}
            <tr className="hover:bg-paper/40">
              <td className="py-2 pr-3 font-sans font-medium text-ink">
                Profit Before Tax (PBT)
              </td>
              <td className="py-2 px-3 text-right font-semibold text-ink">
                ₹{fmt(m.pbt.current)}
              </td>
              <td className="py-2 px-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.pbt.previous)}</div>
                <DeltaBadge change={m.pbt.qoq} />
              </td>
              <td className="py-2 pl-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.pbt.yoy)}</div>
                <DeltaBadge change={m.pbt.yoy_cmp} />
              </td>
            </tr>

            {/* 4. Profit After Tax */}
            <tr className="hover:bg-paper/40">
              <td className="py-2 pr-3 font-sans font-medium text-ink">
                <div>Profit After Tax (PAT)</div>
                {isConsol && m.share_of_associates && (
                  <div className="text-[11px] font-sans text-mute font-normal">
                    Before JVs: ₹{fmt(m.pat.current)} Cr · Share of JVs: +₹{fmt(m.share_of_associates)} Cr
                  </div>
                )}
              </td>
              <td className="py-2 px-3 text-right font-semibold text-ink">
                ₹{fmt(m.pat_with_associates.current ?? m.pat.current)}
              </td>
              <td className="py-2 px-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.pat_with_associates.previous ?? m.pat.previous)}</div>
                <DeltaBadge change={m.pat_with_associates.qoq} />
              </td>
              <td className="py-2 pl-3 text-right">
                <div className="text-mute font-sans text-[11.5px]">₹{fmt(m.pat_with_associates.yoy ?? m.pat.yoy)}</div>
                <DeltaBadge change={m.pat_with_associates.yoy_cmp} />
              </td>
            </tr>

            {/* Attributable to Owners (Consolidated only) */}
            {isConsol && m.pat_attributable_to_owners.current && (
              <tr className="hover:bg-paper/40 text-[11.5px]">
                <td className="py-1.5 pr-3 font-sans text-mute pl-2">
                  ↳ Attributable to Owners of Parent
                </td>
                <td className="py-1.5 px-3 text-right text-mute">
                  ₹{fmt(m.pat_attributable_to_owners.current)}
                </td>
                <td className="py-1.5 px-3 text-right">
                  <DeltaBadge change={m.pat_attributable_to_owners.qoq} />
                </td>
                <td className="py-1.5 pl-3 text-right">
                  <DeltaBadge change={m.pat_attributable_to_owners.yoy_cmp} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Reconciliation details toggle */}
      <div className="mt-3 border-t border-rule/60 pt-2 text-[11.5px]">
        <button
          type="button"
          onClick={() => setShowReconciliation((s) => !s)}
          className="text-mute hover:text-ink underline decoration-dotted font-sans"
        >
          {showReconciliation ? "Hide Financial Reconciliation Notes" : "View Financial Reconciliation Notes (EBITDA & PAT)"}
        </button>

        {showReconciliation && (
          <div className="mt-2 space-y-1.5 rounded bg-paper/60 p-2.5 font-sans text-mute border border-rule/50">
            {statement.reconciliation.ebitda_note && (
              <div>
                <strong className="text-ink">EBITDA Reconciliation:</strong> {statement.reconciliation.ebitda_note}
              </div>
            )}
            {statement.reconciliation.pat_breakdown && (
              <div>
                <strong className="text-ink">PAT Reconciliation:</strong> {statement.reconciliation.pat_breakdown}
              </div>
            )}
            {statement.reconciliation.revenue_breakdown && (
              <div>
                <strong className="text-ink">Revenue Breakdown:</strong> {statement.reconciliation.revenue_breakdown}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Primary Source Citation Footer */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-rule/60 pt-2 text-[11px] text-mute">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-ink">Primary Source:</span>
          <span>{statement.source.table_name}</span>
          {statement.source.page && <span>(Page {statement.source.page})</span>}
        </div>

        {statement.source.doc_url && (
          <a
            href={statement.source.doc_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-semibold text-accent hover:underline"
          >
            <span>View Original NSE Filing (PDF)</span>
            <span>↗</span>
          </a>
        )}
      </div>
    </div>
  );
}
