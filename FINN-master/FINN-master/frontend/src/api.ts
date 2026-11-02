export type Tier = "act" | "know" | "skim";
// EOD = official end-of-day close. Live is reserved: FINN has no real-time feed, so it is never shown today.
export type FeedStatus = "LIVE" | "EOD" | "DELAYED" | "CACHED" | "MOCK" | "UNAVAILABLE";

export interface Feed {
  feed: string; status: FeedStatus; as_of: string | null; fetched_at: string | null;
  age_hours: number | null; note: string;
}
export interface Status {
  prices: Feed; announcements: Feed;
  counts: { announcements: number; symbols_with_prices: number; ingest_issues: number };
  classification: { needs_reclassify: number };
  thresholds: { price_move_pct: number; volume_mult: number };
  tiers: { act: number; know: number };
}
export interface Why { label: string; kind: "category" | "weight" | "market" | "flag" }
export interface Point { label: string; points: number; kind: "base" | "weight" | "market" | "flag" | "confidence" | "cap" }
export interface Item {
  id: string; symbol: string; name: string; sector: string | null; ts: string;
  headline: string; detail: string | null; category: string; category_label: string;
  subtype: string | null; confidence: number; classified_by: string;
  score: number; tier: Tier; why: Why[]; breakdown: Point[]; gate: string | null;
  pdf_url: string | null; source: "NSE" | "MOCK";
  reaction: { date: string; pct: number | null; vol_x: number | null } | null;
  has_results?: boolean;
  result_id?: string | null;
}
export interface Brief {
  window: { label: string; from: string; to: string; is_snapshot?: boolean; snapshot_as_of?: string | null };
  counts: { act: number; know: number; skim: number; total: number };
  items: Item[]; status: Status;
}
export interface Holding {
  symbol: string; name: string; sector: string; size: string; weight: number;
  stats: { date: string; close: number; prev_close: number; pct: number | null; vol_x: number | null; source: string } | null;
  spark: number[]; flags: { volume: boolean; price: boolean };
  filings_7d: { act: number; know: number; skim: number };
  price_status: FeedStatus;
}
export interface Portfolio { holdings: Holding[]; status: Status }
export interface Scoring {
  formula: string; thresholds: { act: number; know: number }; gates: string[];
  examples: { label: string; base: number }[]; market_note: string;
}

export type MetricChangeStatus =
  | "GROWTH"
  | "DECLINE"
  | "FLAT"
  | "TURNAROUND"
  | "SWING_TO_LOSS"
  | "LOSS_NARROWED"
  | "LOSS_WIDENED"
  | "NOT_APPLICABLE"
  | "UNIT_MISMATCH"
  | "UNAVAILABLE";

export interface MetricChange {
  pct: number | null;
  label: string;
  status: MetricChangeStatus;
  abs_change: number | null;
}

export interface MetricComparisonItem {
  current: number | null;
  previous: number | null;
  yoy: number | null;
  qoq: MetricChange;
  yoy_cmp: MetricChange;
  method?: string | null;
  note?: string | null;
  share_of_associates?: number | null;
}

export interface ResultsCardStatement {
  id: string;
  symbol: string;
  filing_id: string | null;
  period_label: string;
  period_end_date: string;
  nature: "consolidated" | "standalone";
  currency: string;
  unit: string;
  metrics: {
    gross_revenue: MetricComparisonItem;
    revenue: MetricComparisonItem;
    derived_ebitda: MetricComparisonItem;
    reported_ebitda: MetricComparisonItem;
    pbt: MetricComparisonItem;
    pat: MetricComparisonItem;
    share_of_associates: number | null;
    pat_with_associates: MetricComparisonItem;
    pat_attributable_to_owners: MetricComparisonItem;
  };
  reconciliation: {
    ebitda_note: string | null;
    revenue_breakdown: string | null;
    pat_breakdown: string | null;
  };
  source: {
    doc_url: string | null;
    page: number | null;
    table_name: string | null;
    extracted_at: string;
  };
}

export interface FilingResultsResponse {
  filing_id: string;
  symbol: string;
  period_label: string;
  primary_nature: "consolidated" | "standalone";
  statements: Record<string, ResultsCardStatement>;
}

// ------------------------------------------------------------------ P1.2 Research Types
export interface ResearchSearchItem {
  symbol: string;
  name: string;
  sector: string;
  size_bucket: string;
  weight: number;
  in_portfolio: boolean;
  has_research: boolean;
  as_of_period: string | null;
  as_of_date: string | null;
  generated_at: string | null;
}

export interface ResearchSearchResponse {
  query: string;
  count: number;
  results: ResearchSearchItem[];
}

export interface CitationItem {
  id: string;
  doc_title: string;
  doc_type: "annual_report" | "concall_transcript" | "results_pdf" | "investor_presentation" | string;
  page: number;
  section: string;
  claim: string;
  url: string;
  verbatim_text?: string;
  speaker_name?: string;
  speaker_designation?: string;
  speaker_role?: "MANAGEMENT" | "ANALYST" | string;
  statement_type?: string;
  confidence?: number;
  needs_review?: boolean;
  review_reason?: string | null;
}

export interface SourceDocument {
  doc_name: string;
  doc_type: string;
  url: string;
  ir_url?: string;
  verified_pages?: number[];
  verified_slides?: number[];
}

export interface ResearchDossier {
  id: string;
  symbol: string;
  company_name: string;
  sector: string;
  size_bucket: string;
  as_of_period: string;
  as_of_date: string;
  generated_at: string;
  needs_review: boolean;
  review_reason: string | null;
  source_documents: SourceDocument[];
  business_snapshot: {
    company_name: string;
    description: string;
    segments: Array<{
      name: string;
      revenue_cr: number;
      contribution_pct: number;
      is_elimination: boolean;
    }>;
    core_platforms: Array<{ platform: string; role: string }>;
    annual_report_operational_scale_fy26?: {
      retail_scale?: string;
      digital_services_scale?: string;
      media_and_entertainment?: string;
      o2c_refining_and_petchem?: string;
      oil_and_gas_upstream?: string;
      new_energy_gigafactories?: string;
    };
    citations: string[];
  };
  financial_snapshot: {
    period: string;
    gross_revenue_cr: number;
    revenue_from_operations_cr: number;
    total_segment_ebitda_cr: number;
    reported_ebitda_cr: number;
    derived_operating_ebitda_cr: number;
    pbt_cr: number;
    headline_pat_cr: number;
    owners_pat_cr: number;
    net_profit_margin_pct: number;
    operating_margin_pct: number;
    retail_performance?: {
      gross_revenue_cr: number;
      gross_revenue_yoy_pct: number;
      ebitda_before_impairment_cr: number;
      ebitda_after_impairment_cr: number;
      ebitda_after_impairment_yoy_pct: number;
      margin_pct: number;
      impairment_charge_cr: number;
      notes: string;
    };
    annual_report_fy26_financials?: {
      period?: string;
      gross_revenue_cr?: number;
      ebitda_cr?: number;
      pat_cr?: number;
      reported_ebitda_margin_pct?: number;
      net_profit_margin_pct?: number;
      gross_fixed_assets_cr?: number;
      pat_milestone_note?: string;
      citations?: string[];
    };
    concall_q2_fy26_commentary?: {
      period?: string;
      speaker?: string;
      jio_ebitda_growth_pct?: number;
      retail_ebitda_growth_pct?: number;
      retail_revenue_growth_pct?: number;
      commentary_note?: string;
      citations?: string[];
    };
    ebitda_reconciliation_note?: string;
    reconciliation_summary: string;
    citations: string[];
  };
  trajectory: {
    headline_direction: string;
    growing_segments: Array<{
      segment: string;
      trend: string;
      yoy_ebitda_growth_pct: number;
      drivers: string;
    }>;
    compressing_segments: Array<{
      segment: string;
      trend: string;
      yoy_ebitda_growth_pct: number;
      drivers: string;
    }>;
    multi_year_structural_trajectory?: {
      revenue_cagr_narrative?: string;
      concall_pacing_trend?: string;
      citations?: string[];
    };
    citations: string[];
  };
  balance_sheet: {
    as_of_date: string;
    gross_debt_cr: number;
    non_current_borrowings_cr: number;
    current_borrowings_cr: number;
    cash_and_equivalents_cr: number;
    current_investments_cr: number;
    total_liquid_assets_cr: number;
    statutory_net_debt_cr: number;
    management_reported_net_debt_cr: number;
    management_net_debt_to_ebitda: number;
    debt_equity_ratio: number;
    dscr: number;
    iscr: number;
    current_ratio: number;
    total_equity_cr: number;
    net_worth_cr: number;
    finance_costs_pnl_q2_cr?: number;
    finance_costs_pnl_h1_cr?: number;
    cash_interest_paid_h1_cr?: number;
    annual_report_fy26_debt_and_capital_structure?: {
      as_of_date?: string;
      total_assets_cr?: number;
      total_equity_cr?: number;
      non_current_borrowings_cr?: number;
      current_borrowings_maturities_cr?: number;
      secured_ncd_cr?: number;
      unsecured_ncd_cr?: number;
      unsecured_bonds_cr?: number;
      term_loans_from_banks_cr?: number;
      deferred_spectrum_liabilities_cr?: number;
      capital_commitments_contracts_remaining_cr?: number;
      investment_commitments_cr?: number;
      dscr_fy26?: number;
      samurai_loan_jpy_bn?: number;
      nexi_facility?: string;
      citations?: string[];
    };
    concall_q2_fy26_debt_commentary?: {
      speaker?: string;
      statement?: string;
      citations?: string[];
    };
    net_debt_reconciliation_note?: string;
    equity_reconciliation_note?: string;
    interest_reconciliation_note?: string;
    working_capital_summary: string;
    citations: string[];
  };
  cash_quality: {
    period: string;
    period_scope_note?: string;
    cfo_cr: number;
    pbt_h1_cr: number;
    capex_h1_cr: number;
    fcf_h1_cr: number;
    cfo_to_pbt_ratio: number;
    cfo_to_pbt_pct: number;
    cash_conversion_status: string;
    fcf_status: string;
    closing_cash_cr: number;
    net_cash_increase_cr: number;
    cash_quality_verdict: string;
    annual_report_fy26_cash_flows?: {
      period?: string;
      cash_generated_from_operations_cr?: number;
      cfo_cr?: number;
      pbt_fy26_cr?: number;
      cfo_to_pbt_ratio?: number;
      cfo_to_pbt_pct?: number;
      cash_conversion_verdict?: string;
      citations?: string[];
    };
    concall_q2_fy26_cash_reinvestment?: {
      statement?: string;
      citations?: string[];
    };
    citations: string[];
  };
  narrative_vs_numbers: Array<{
    dimension: string;
    management_narrative: string;
    statutory_number: string;
    verdict: "Agreement" | "Divergence" | "Qualified Agreement" | "Caution" | "Auditor Scrutiny" | string;
    analysis: string;
    citations: string[];
    reporting_period?: string;
    needs_review?: boolean;
    review_reason?: string | null;
  }>;
  guidance: Array<{
    metric_or_area: string;
    commitment: string;
    target_period: string;
    reported_actual: string;
    status: "Delivered" | "In Progress" | "Not Delivered" | "Future Target" | "Operational Target" | string;
    citations: string[];
    relative_time_context?: string;
    confidence?: number;
    needs_review?: boolean;
    review_reason?: string | null;
  }>;
  bull_vs_bear: {
    bull_case: Array<{
      point: string;
      detail: string;
      citations: string[];
      source_period?: string;
      needs_review?: boolean;
      review_reason?: string | null;
    }>;
    bear_case: Array<{
      point: string;
      detail: string;
      citations: string[];
      source_period?: string;
      needs_review?: boolean;
      review_reason?: string | null;
    }>;
  };
  citations: CitationItem[];
}

export interface ResearchResponse {
  status: "AVAILABLE" | "UNAVAILABLE" | "NOT_FOUND";
  symbol: string;
  company_name: string | null;
  sector?: string;
  size_bucket?: string;
  has_research: boolean;
  as_of_period?: string;
  as_of_date?: string;
  generated_at?: string;
  needs_review?: boolean;
  review_reason?: string | null;
  message?: string;
  dossier: ResearchDossier | null;
}

// ------------------------------------------------------------------ P1.3 Commitments Types
export interface QuarterEvaluationItem {
  quarter: string;
  disclosed_value: number | null;
  disclosed_unit: string | null;
  status: string;
  commentary: string;
  source_doc: string;
  source_page_or_slide: string;
  source_url: string;
}

export interface CommitmentSourceCitation {
  doc_title: string;
  doc_type: string;
  page_or_slide: string;
  url: string;
}

export interface CommitmentActualCitation {
  doc_title: string;
  page_or_slide: string;
  url: string;
  reported_period: string | null;
}

export interface CommitmentCardItem {
  id: string;
  symbol: string;
  commitment_type: "EXPLICIT_COMMITMENT" | "FORWARD_GUIDANCE" | "STRATEGIC_INTENTION" | "OPERATIONAL_MILESTONE";
  category: "capex" | "capacity_commissioning" | "revenue_margin" | "operational_targets" | "strategic_milestone";
  title: string;
  statement: string;
  speaker: string | null;
  commitment_date: string;
  commitment_period: string;
  target_period: string;
  target: {
    value: number | null;
    unit: string | null;
    tolerance_pct: number;
  };
  source_citation: CommitmentSourceCitation;
  actual_performance: string | null;
  actual: {
    value: number | null;
    unit: string | null;
  };
  actual_citation: CommitmentActualCitation | null;
  quarter_evaluations: QuarterEvaluationItem[];
  status: "ACHIEVED" | "PARTIALLY_ACHIEVED" | "IN_PROGRESS" | "DELAYED" | "MISSED" | "UNVERIFIABLE" | "NEEDS_REVIEW";
  evaluation_reasoning: string;
  is_quantified: boolean;
  contributes_to_score: boolean;
  needs_review: boolean;
  review_reason: string | null;
  created_at: string;
}

export interface CommitmentsSummaryData {
  total_commitments: number;
  explicit_commitments_count: number;
  forward_guidance_count: number;
  strategic_intentions_count: number;
  operational_milestones_count: number;
  excluded_count: number;
  total_achieved_count: number;
  total_partially_achieved_count: number;
  total_delayed_count: number;
  total_missed_count: number;
  total_in_progress_count: number;
  total_unverifiable_count: number;
  total_needs_review_count: number;
  eligible_count: number;
  eligible_evaluated_count: number;
  eligible_achieved_count: number;
  eligible_partially_achieved_count: number;
  eligible_delayed_count: number;
  eligible_missed_count: number;
  eligible_in_progress_count: number;
  eligible_unverifiable_count: number;
  eligible_needs_review_count: number;
  delivery_score: number | null;
  score_label: string;
  methodology_note: string;
  stat_caveat: string;
  evaluated_count: number;
  achieved_count: number;
  in_progress_count: number;
  unverifiable_count: number;
  needs_review_count: number;
}

export interface CommitmentsResponse {
  status: "OK" | "UNAVAILABLE" | "NOT_FOUND";
  symbol: string;
  company_name: string | null;
  count: number;
  summary: CommitmentsSummaryData | null;
  commitments: CommitmentCardItem[];
  message?: string;
}

export interface CommitmentsSummaryResponse {
  status: "OK" | "UNAVAILABLE" | "NOT_FOUND";
  symbol: string;
  company_name: string | null;
  count: number;
  summary: CommitmentsSummaryData | null;
  message?: string;
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
export const api = {
  brief: (qs: URLSearchParams) => get<Brief>(`/api/brief?${qs}`),
  portfolio: () => get<Portfolio>("/api/portfolio"),
  status: () => get<Status>("/api/status"),
  scoring: () => get<Scoring>("/api/scoring"),
  filingResults: (filingId: string) => get<FilingResultsResponse>(`/api/results/filing/${filingId}`),
  symbolResults: (symbol: string, nature = "consolidated") =>
    get<{ symbol: string; count: number; results: ResultsCardStatement[] }>(`/api/results/${symbol}?nature=${nature}`),
  researchSearch: (q = "") => get<ResearchSearchResponse>(`/api/research/search?q=${encodeURIComponent(q)}`),
  researchGet: (symbol: string) => get<ResearchResponse>(`/api/research/${symbol}`),
  commitments: (symbol: string) => get<CommitmentsResponse>(`/api/commitments/${symbol}`),
  commitmentsSummary: (symbol: string) => get<CommitmentsSummaryResponse>(`/api/commitments/${symbol}/summary`),
};
