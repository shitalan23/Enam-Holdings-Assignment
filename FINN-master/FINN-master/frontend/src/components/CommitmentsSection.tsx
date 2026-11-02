import { useState } from "react";
import {
  type CommitmentCardItem,
  type CommitmentsSummaryData,
  type QuarterEvaluationItem,
} from "../api";

interface CommitmentsSectionProps {
  symbol: string;
  companyName: string;
  summary: CommitmentsSummaryData | null;
  commitments: CommitmentCardItem[];
  loading?: boolean;
  error?: string | null;
  onOpenCitation?: (url: string, title: string, pageOrSlide: string) => void;
  onSelectReliance?: () => void;
}

export function CommitmentsSection({
  symbol,
  companyName,
  summary,
  commitments,
  loading,
  error,
  onOpenCitation,
  onSelectReliance,
}: CommitmentsSectionProps) {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [eligibilityFilter, setEligibilityFilter] = useState<string>("ALL");
  const [expandedHistories, setExpandedHistories] = useState<Record<string, boolean>>({});
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const toggleHistory = (id: string) => {
    setExpandedHistories((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const activeFilterCount =
    (selectedCategory !== "ALL" ? 1 : 0) +
    (selectedStatus !== "ALL" ? 1 : 0) +
    (eligibilityFilter !== "ALL" ? 1 : 0);

  // Filtered commitments list
  const filteredCommitments = commitments.filter((c) => {
    if (selectedCategory !== "ALL" && c.category !== selectedCategory) return false;
    if (selectedStatus !== "ALL" && c.status !== selectedStatus) return false;
    if (eligibilityFilter === "ELIGIBLE" && !c.contributes_to_score) return false;
    if (eligibilityFilter === "EXCLUDED" && c.contributes_to_score) return false;
    return true;
  });

  const getStatusBadge = (status: CommitmentCardItem["status"]) => {
    switch (status) {
      case "ACHIEVED":
        return { label: "✓ Delivered", bg: "bg-up/15 text-up border-up/30" };
      case "PARTIALLY_ACHIEVED":
        return { label: "◐ Partially Delivered", bg: "bg-warn/15 text-warn border-warn/30" };
      case "IN_PROGRESS":
        return { label: "⏳ In Progress", bg: "bg-accent/15 text-accent border-accent/30" };
      case "DELAYED":
        return { label: "⚠ Delayed", bg: "bg-warn/20 text-warn border-warn/40" };
      case "MISSED":
        return { label: "✗ Missed", bg: "bg-down/15 text-down border-down/30" };
      case "UNVERIFIABLE":
        return { label: "❓ Unverifiable", bg: "bg-mute/15 text-mute border-rule" };
      case "NEEDS_REVIEW":
        return { label: "🔍 Needs Review", bg: "bg-down/10 text-down border-down/30" };
      default:
        return { label: status, bg: "bg-raised text-mute border-rule" };
    }
  };

  const getTypeBadge = (type: CommitmentCardItem["commitment_type"]) => {
    switch (type) {
      case "EXPLICIT_COMMITMENT":
        return { label: "Explicit Commitment", eligible: true, bg: "bg-accent-soft text-accent border-accent/30" };
      case "FORWARD_GUIDANCE":
        return { label: "Forward Guidance", eligible: true, bg: "bg-accent-soft/70 text-accent border-accent/20" };
      case "STRATEGIC_INTENTION":
        return { label: "Strategic Intention (Excluded)", eligible: false, bg: "bg-raised text-mute border-rule" };
      case "OPERATIONAL_MILESTONE":
        return { label: "Operational Milestone (Excluded)", eligible: false, bg: "bg-raised text-mute border-rule" };
      default:
        return { label: type, eligible: false, bg: "bg-raised text-mute border-rule" };
    }
  };

  const getCategoryLabel = (cat: string) => {
    switch (cat) {
      case "capex":
        return "Capex & Investment";
      case "capacity_commissioning":
        return "Capacity & Commissioning";
      case "revenue_margin":
        return "Revenue & Margin Guidance";
      case "operational_targets":
        return "Operational Targets";
      case "strategic_milestone":
        return "Strategic Milestone";
      default:
        return cat;
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center rounded border border-rule bg-raised/40 py-16 text-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        <p className="mt-3 text-xs text-mute">Loading management commitments for {symbol}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-down/30 bg-down/5 p-4 text-center">
        <p className="text-xs font-semibold text-down">Unable to load commitments</p>
        <p className="mt-1 text-xs text-mute">{error}</p>
      </div>
    );
  }

  if (!commitments.length) {
    return (
      <div className="rounded border border-dashed border-rule bg-raised/40 p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-paper text-xl text-mute">
          🎯
        </div>
        <h3 className="mt-3 text-base font-semibold text-ink">
          Promise vs Delivered Unavailable for {symbol}
        </h3>
        <p className="mx-auto mt-1 max-w-md text-xs text-mute">
          Management commitments and forward-looking guidance have not yet been extracted from historical primary filings for {companyName || symbol}.
        </p>

        <div className="mt-5 mx-auto max-w-lg rounded border border-rule bg-paper/60 p-4 text-left">
          <p className="text-xs font-semibold text-ink">Zero-Fabrication Promise Tracking:</p>
          <p className="mt-1 text-[12px] text-mute">
            FINN never fabricates prior promises or treats historical KPIs as commitments without advance primary-source evidence. To track commitments, FINN requires:
          </p>
          <ul className="mt-2 space-y-1 text-[11.5px] text-faint list-disc list-inside">
            <li>Advance guidance statements from prior-period Investor Presentations</li>
            <li>AGM or earnings call transcripts establishing quantitative target gates</li>
            <li>Subsequent Regulation 33 Financial Results proving actual delivery or non-delivery</li>
          </ul>
        </div>

        {symbol !== "RELIANCE" && onSelectReliance && (
          <div className="mt-4 flex justify-center">
            <button
              type="button"
              onClick={onSelectReliance}
              className="rounded bg-accent px-3 py-1.5 text-xs font-semibold text-paper hover:bg-accent/90"
            >
              View RELIANCE Track Record Demonstration ★
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* SECTION HEADER & SCORECARD */}
      {summary && (
        <div className="rounded border border-rule bg-raised p-4 md:p-5 shadow-xs">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            {/* Primary Delivery Score */}
            <div className="flex flex-col sm:flex-row items-start gap-4">
              <div
                className={`flex flex-col items-center justify-center rounded border px-4 py-3 w-full sm:w-auto min-w-[120px] text-center shrink-0 ${
                  summary.delivery_score !== null ? "border-up/30 bg-up/10" : "border-rule bg-paper/80"
                }`}
              >
                <span
                  className={`text-[10.5px] font-bold tracking-wider uppercase ${
                    summary.delivery_score !== null ? "text-up" : "text-mute"
                  }`}
                >
                  Delivery Score
                </span>
                <span className="text-3xl font-extrabold tracking-tight text-ink font-mono mt-0.5">
                  {summary.delivery_score !== null ? `${summary.delivery_score.toFixed(1)}%` : "N/A"}
                </span>
                <span
                  className={`mt-1 rounded px-2 py-0.5 text-[11px] font-semibold ${
                    summary.delivery_score !== null ? "bg-up/20 text-up" : "bg-rule/60 text-mute"
                  }`}
                >
                  {summary.delivery_score !== null
                    ? `${summary.eligible_achieved_count} of ${summary.eligible_evaluated_count} delivered`
                    : `${summary.eligible_evaluated_count} of ${summary.eligible_count} evaluated`}
                </span>
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold tracking-tight text-ink md:text-lg">
                    Management Track Record: {companyName}
                  </h3>
                  <span className="rounded bg-paper px-2 py-0.5 font-mono text-xs font-semibold text-ink border border-rule">
                    {symbol}
                  </span>
                </div>
                <p className="mt-1 text-[12.5px] text-mute max-w-2xl">
                  Tracks forward-looking commitments made by leadership and audits them against subsequently published official primary filings (NSE/BSE).
                </p>

                {/* Score Formula note */}
                <p className="mt-1.5 text-[11px] font-mono text-faint">
                  Methodology: (Eligible Achieved + 0.5 × Partial) ÷ Eligible Evaluated Commitments ({summary.eligible_evaluated_count}).
                </p>
              </div>
            </div>

            {/* Quick KPI Counters */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 lg:pt-0">
              <div className="rounded border border-rule bg-paper/80 p-2 text-center">
                <span className="block text-[10.5px] font-medium text-mute">Score-Eligible</span>
                <span className="text-base font-bold font-mono text-ink">{summary.eligible_count}</span>
                <span className="block text-[9.5px] text-faint">
                  ({summary.eligible_evaluated_count} evaluated)
                </span>
              </div>
              <div className="rounded border border-rule bg-paper/80 p-2 text-center">
                <span className="block text-[10.5px] font-medium text-up">Achieved</span>
                <span className="text-base font-bold font-mono text-up">{summary.eligible_achieved_count}</span>
                <span className="block text-[9.5px] text-faint">
                  (total: {summary.total_achieved_count})
                </span>
              </div>
              <div className="rounded border border-rule bg-paper/80 p-2 text-center">
                <span className="block text-[10.5px] font-medium text-accent">In Progress</span>
                <span className="text-base font-bold font-mono text-accent">{summary.eligible_in_progress_count}</span>
                <span className="block text-[9.5px] text-faint">
                  (total: {summary.total_in_progress_count})
                </span>
              </div>
              <div className="rounded border border-rule bg-paper/80 p-2 text-center">
                <span className="block text-[10.5px] font-medium text-mute">Unverifiable</span>
                <span className="text-base font-bold font-mono text-mute">{summary.eligible_unverifiable_count}</span>
                <span className="block text-[9.5px] text-faint">(no follow-up)</span>
              </div>
            </div>
          </div>

          {/* Statistical Caveat Callout */}
          <div className="mt-3.5 rounded border border-warn/30 bg-warn-soft/60 p-2.5 text-xs text-warn">
            <div className="flex items-start gap-2">
              <span className="font-bold text-[13px]">⚠️</span>
              <div>
                <span className="font-semibold">Sample Size Transparency & Statistical Caveat:</span>{" "}
                <span className="text-[12px] text-warn/90">{summary.stat_caveat}</span>
              </div>
            </div>
          </div>

          {/* Excluded Non-Promissory Items Notice */}
          <div className="mt-2.5 flex flex-wrap items-center justify-between text-[11.5px] text-mute border-t border-rule/60 pt-2">
            <span>
              <strong className="text-ink">3 Non-Promissory Items Excluded from Score Denominator:</strong>{" "}
              {summary.strategic_intentions_count} directional strategic intention,{" "}
              {summary.operational_milestones_count} historical operational milestones.
            </span>
            <span className="text-[11px] text-faint">Strict ENAM Holding Standards</span>
          </div>
        </div>
      )}

      {/* FILTER CONTROLS */}
      <div className="rounded border border-rule bg-raised/70 p-3 space-y-3">
        {/* Mobile Filter Toggle */}
        <div className="flex md:hidden items-center justify-between">
          <button
            type="button"
            onClick={() => setMobileFiltersOpen((prev) => !prev)}
            className="flex items-center gap-1.5 rounded border border-rule bg-paper px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-paper/80"
            aria-expanded={mobileFiltersOpen}
          >
            <span>⚙️ Filters</span>
            {activeFilterCount > 0 && (
              <span className="rounded bg-accent/20 px-1.5 py-0.2 text-[10px] font-bold text-accent">
                {activeFilterCount} active
              </span>
            )}
            <span className="text-[10px] text-mute">{mobileFiltersOpen ? "▲" : "▼"}</span>
          </button>
          <span className="text-[11.5px] text-faint">
            {filteredCommitments.length} of {commitments.length} commitments
          </span>
        </div>

        {/* Filters content (always visible on md+, collapsible on mobile) */}
        <div
          className={`${
            mobileFiltersOpen ? "flex" : "hidden md:flex"
          } flex-wrap items-center justify-between gap-3 text-xs`}
        >
          <div className="flex flex-wrap items-center gap-2">
            {/* Category Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-mute font-medium">Category:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="rounded border border-rule bg-paper px-2 py-1 text-xs text-ink focus:border-accent focus:outline-hidden"
              >
                <option value="ALL">All Categories ({commitments.length})</option>
                <option value="capex">Capex & Investment</option>
                <option value="strategic_milestone">Strategic Milestones</option>
                <option value="revenue_margin">Revenue & Margins</option>
                <option value="operational_targets">Operational Targets</option>
                <option value="capacity_commissioning">Capacity & Commissioning</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-mute font-medium">Status:</span>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="rounded border border-rule bg-paper px-2 py-1 text-xs text-ink focus:border-accent focus:outline-hidden"
              >
                <option value="ALL">All Statuses</option>
                <option value="ACHIEVED">Delivered / Achieved</option>
                <option value="PARTIALLY_ACHIEVED">Partially Delivered</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="DELAYED">Delayed</option>
                <option value="MISSED">Missed</option>
                <option value="UNVERIFIABLE">Unverifiable (No Data)</option>
                <option value="NEEDS_REVIEW">Needs Review</option>
              </select>
            </div>

            {/* Eligibility Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-mute font-medium">Eligibility:</span>
              <select
                value={eligibilityFilter}
                onChange={(e) => setEligibilityFilter(e.target.value)}
                className="rounded border border-rule bg-paper px-2 py-1 text-xs text-ink focus:border-accent focus:outline-hidden"
              >
                <option value="ALL">All Types</option>
                <option value="ELIGIBLE">Score-Eligible Only ({summary?.eligible_count ?? 6})</option>
                <option value="EXCLUDED">Excluded Non-Promissory ({summary?.excluded_count ?? 3})</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden md:inline text-[11.5px] text-faint">
              Showing {filteredCommitments.length} of {commitments.length} commitments
            </span>
            {(selectedCategory !== "ALL" || selectedStatus !== "ALL" || eligibilityFilter !== "ALL") && (
              <button
                type="button"
                onClick={() => {
                  setSelectedCategory("ALL");
                  setSelectedStatus("ALL");
                  setEligibilityFilter("ALL");
                }}
                className="text-[11px] font-medium text-accent hover:underline"
              >
                Reset Filters
              </button>
            )}
          </div>
        </div>
      </div>

      {/* COMMITMENTS LIST */}
      <div className="space-y-3.5">
        {filteredCommitments.map((item, idx) => {
          const statusBadge = getStatusBadge(item.status);
          const typeBadge = getTypeBadge(item.commitment_type);
          const hasHistory = item.quarter_evaluations && item.quarter_evaluations.length > 0;
          const isHistoryExpanded = !!expandedHistories[item.id];

          return (
            <div
              key={item.id}
              className={`rounded border p-4 md:p-5 transition-shadow bg-raised ${
                item.contributes_to_score ? "border-rule" : "border-rule/60 opacity-95"
              }`}
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-rule/70 pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-paper px-1.5 py-0.5 font-mono text-[11px] font-bold text-mute border border-rule">
                    #{idx + 1}
                  </span>
                  <h4 className="text-sm md:text-base font-semibold text-ink tracking-tight break-words">
                    {item.title}
                  </h4>
                  <span className="rounded bg-paper px-2 py-0.5 text-[11px] font-medium text-mute border border-rule">
                    {getCategoryLabel(item.category)}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 shrink-0">
                  {/* Type Badge */}
                  <span
                    className={`rounded border px-2 py-0.5 text-[11px] font-semibold ${typeBadge.bg}`}
                    title={typeBadge.eligible ? "Contributes to Delivery Score" : "Excluded from Delivery Score"}
                  >
                    {typeBadge.label}
                  </span>

                  {/* Status Badge */}
                  <span
                    className={`rounded border px-2.5 py-0.5 text-xs font-bold ${statusBadge.bg}`}
                  >
                    {statusBadge.label}
                  </span>
                </div>
              </div>

              {/* Card Body: Promise vs Delivered comparison */}
              <div className="mt-3.5 grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* PROMISE SIDE */}
                <div className="rounded border border-rule/80 bg-paper/70 p-3.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between text-xs text-mute mb-1.5">
                      <span className="font-bold uppercase tracking-wider text-[10.5px] text-accent">
                        📢 Original Management Commitment
                      </span>
                      <span className="font-mono text-[11px]">
                        {item.commitment_date} ({item.commitment_period})
                      </span>
                    </div>

                    <blockquote className="text-[13px] text-ink font-serif italic border-l-2 border-accent pl-2.5 my-2">
                      "{item.statement}"
                    </blockquote>

                    {item.speaker && (
                      <p className="text-[11px] text-faint mt-1">
                        Speaker: <span className="text-mute font-medium">{item.speaker}</span>
                      </p>
                    )}

                    {/* Target & Period Details */}
                    <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      {item.target.value !== null && (
                        <div>
                          <span className="text-mute">Target Gate: </span>
                          <span className="font-semibold font-mono text-ink">
                            {item.target.value.toLocaleString("en-IN")} {item.target.unit}
                          </span>
                          {item.target.tolerance_pct > 0 && (
                            <span className="text-[10.5px] text-faint ml-1">
                              (±{item.target.tolerance_pct}% tolerance)
                            </span>
                          )}
                        </div>
                      )}
                      <div>
                        <span className="text-mute">Target Period: </span>
                        <span className="font-semibold text-ink">{item.target_period}</span>
                      </div>
                    </div>
                  </div>

                  {/* Promise Source Citation */}
                  <div className="mt-3 pt-2 border-t border-rule/60 flex items-center justify-between text-[11.5px]">
                    <div className="truncate mr-2">
                      <span className="text-faint">Promise Source: </span>
                      <span className="font-medium text-mute">
                        {item.source_citation.doc_title} ({item.source_citation.page_or_slide})
                      </span>
                    </div>
                    {item.source_citation.url && (
                      <a
                        href={item.source_citation.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-accent font-semibold hover:underline shrink-0 text-[11px]"
                      >
                        Source PDF ↗
                      </a>
                    )}
                  </div>
                </div>

                {/* DELIVERED / ACTUAL SIDE */}
                <div
                  className={`rounded border p-3.5 flex flex-col justify-between ${
                    item.status === "ACHIEVED"
                      ? "border-up/30 bg-up/5"
                      : item.status === "IN_PROGRESS"
                      ? "border-accent/30 bg-accent/5"
                      : item.status === "UNVERIFIABLE"
                      ? "border-rule/80 bg-paper/50"
                      : "border-down/30 bg-down/5"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between text-xs text-mute mb-1.5">
                      <span
                        className={`font-bold uppercase tracking-wider text-[10.5px] ${
                          item.status === "ACHIEVED"
                            ? "text-up"
                            : item.status === "IN_PROGRESS"
                            ? "text-accent"
                            : "text-mute"
                        }`}
                      >
                        📊 Subsequent Disclosed Performance
                      </span>
                      {item.actual_citation?.reported_period && (
                        <span className="font-mono text-[11px]">
                          Reported in {item.actual_citation.reported_period}
                        </span>
                      )}
                    </div>

                    {item.actual_performance ? (
                      <p className="text-[13px] text-ink my-2">
                        {item.actual_performance}
                      </p>
                    ) : (
                      <p className="text-[12.5px] text-mute italic my-2">
                        {item.status === "UNVERIFIABLE"
                          ? "Actual outcome was not disclosed in subsequent primary filings. Under FINN zero-fabrication rules, an unverified metric is never marked Missed without negative evidence."
                          : "Actual outcome is ongoing and actively monitored across subsequent quarters."}
                      </p>
                    )}

                    {/* Numeric Actual Details */}
                    {item.actual.value !== null && (
                      <div className="mt-2 text-xs">
                        <span className="text-mute">Disclosed Metric: </span>
                        <span className="font-semibold font-mono text-ink">
                          {item.actual.value.toLocaleString("en-IN")} {item.actual.unit}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Actual Source Citation */}
                  <div className="mt-3 pt-2 border-t border-rule/60 flex items-center justify-between text-[11.5px]">
                    {item.actual_citation ? (
                      <>
                        <div className="truncate mr-2">
                          <span className="text-faint">Actual Citation: </span>
                          <span className="font-medium text-mute">
                            {item.actual_citation.doc_title} ({item.actual_citation.page_or_slide})
                          </span>
                        </div>
                        {item.actual_citation.url && (
                          <a
                            href={item.actual_citation.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent font-semibold hover:underline shrink-0 text-[11px]"
                          >
                            Outcome Filing ↗
                          </a>
                        )}
                      </>
                    ) : (
                      <span className="text-[11px] text-faint italic">
                        No subsequent disclosure cited
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* EVALUATION REASONING & CHECKPOINTS FOOTER */}
              <div className="mt-3 rounded border border-rule/60 bg-paper/60 p-2.5 text-xs">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
                  <div className="flex items-start gap-1.5">
                    <span className="text-mute font-semibold">Evaluation Verdict:</span>
                    <span className="text-ink">{item.evaluation_reasoning}</span>
                  </div>

                  {hasHistory && (
                    <button
                      type="button"
                      onClick={() => toggleHistory(item.id)}
                      className="text-[11px] font-semibold text-accent hover:underline shrink-0 text-left sm:text-right"
                    >
                      {isHistoryExpanded
                        ? "Hide Quarterly Pacing ▲"
                        : `View ${item.quarter_evaluations.length}-Quarter Pacing ▼`}
                    </button>
                  )}
                </div>

                {/* EXPANDABLE QUARTERLY AUDIT PACING */}
                {hasHistory && isHistoryExpanded && (
                  <div className="mt-2.5 pt-2 border-t border-rule/60">
                    <p className="text-[11px] font-semibold text-mute uppercase tracking-wider mb-1.5">
                      Quarterly Pacing Audit Checkpoints:
                    </p>
                    <div className="space-y-1.5">
                      {item.quarter_evaluations.map((q: QuarterEvaluationItem, qIdx: number) => (
                        <div
                          key={qIdx}
                          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 rounded border border-rule/50 bg-raised/70 px-2.5 py-1.5 text-[11.5px]"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono font-bold text-ink shrink-0">{q.quarter}</span>
                            <span
                              className={`rounded px-1.5 py-0.2 text-[10px] font-bold shrink-0 ${
                                q.status === "COMPLETED"
                                  ? "bg-up/15 text-up"
                                  : "bg-accent/15 text-accent"
                              }`}
                            >
                              {q.status}
                            </span>
                            <span className="text-mute break-words">{q.commentary}</span>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-[10.5px] text-faint shrink-0 pt-0.5 sm:pt-0">
                            {q.disclosed_value !== null && (
                              <span className="font-mono font-medium text-ink">
                                {q.disclosed_value.toLocaleString("en-IN")} {q.disclosed_unit}
                              </span>
                            )}
                            <span>({q.source_page_or_slide})</span>
                            {q.source_url && (
                              <a
                                href={q.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-accent hover:underline"
                              >
                                ↗
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
