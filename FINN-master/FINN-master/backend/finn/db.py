"""SQLite schema and helpers. One file, no server, ships inside the repo.

Every row that comes from outside carries `source` and a fetch timestamp so the
UI can label it LIVE / DELAYED / CACHED / MOCK / UNAVAILABLE honestly.
"""
import sqlite3
from contextlib import contextmanager
from .config import DB_PATH, PORTFOLIO

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  symbol TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sector TEXT,
  size_bucket TEXT,
  weight REAL DEFAULT 0,
  in_portfolio INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prices_eod (
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,              -- YYYY-MM-DD (exchange date)
  open REAL, high REAL, low REAL, close REAL,
  volume INTEGER,
  source TEXT NOT NULL,            -- 'yfinance' | 'MOCK'
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,             -- stable hash of source + exchange reference
  symbol TEXT NOT NULL,
  ts TEXT NOT NULL,                -- ISO8601 with offset, IST
  headline TEXT NOT NULL,
  detail TEXT,                     -- exchange-provided text, trimmed (no LLM)
  category TEXT NOT NULL,
  subtype TEXT,                    -- e.g. 'intimation', 'downgrade'
  category_method TEXT NOT NULL,   -- 'rules' now; 'llm' later for ambiguous ones
  pdf_url TEXT,
  source TEXT NOT NULL,            -- 'NSE' | 'MOCK'
  fetched_at TEXT NOT NULL,
  confidence REAL,                 -- classifier confidence 0-1; NULL = classified by the pre-v2 rules
  reason TEXT                      -- which rule decided, for audit
);
CREATE INDEX IF NOT EXISTS idx_ann_ts ON announcements(ts);
CREATE INDEX IF NOT EXISTS idx_ann_symbol ON announcements(symbol, ts);

-- One row per data feed; the UI status pill reads this.
CREATE TABLE IF NOT EXISTS feed_status (
  feed TEXT PRIMARY KEY,           -- 'prices' | 'announcements'
  status TEXT NOT NULL,            -- 'LIVE' | 'DELAYED' | 'CACHED' | 'MOCK' | 'UNAVAILABLE'
  fetched_at TEXT,
  note TEXT
);

-- Per-symbol failures from ingest, so gaps are explicit rather than silent.
CREATE TABLE IF NOT EXISTS ingest_issues (
  feed TEXT, symbol TEXT, at TEXT, message TEXT
);

-- P1.1: Quarterly Financial Results intelligence
CREATE TABLE IF NOT EXISTS quarterly_results (
  id TEXT PRIMARY KEY,               -- sha1(symbol + period_label + nature)
  symbol TEXT NOT NULL,
  filing_id TEXT,                    -- foreign reference to announcements(id) if matched
  period_label TEXT NOT NULL,        -- e.g. 'Q2 FY27', 'Q1 FY27', 'Q2 FY26'
  period_end_date TEXT NOT NULL,     -- YYYY-MM-DD
  nature TEXT NOT NULL,              -- 'consolidated' | 'standalone'
  currency TEXT DEFAULT 'INR',
  unit TEXT NOT NULL,                -- 'crore' | 'lakh' | 'million'
  gross_revenue REAL,                -- Value of Sales & Services (Gross)
  gst_recovered REAL,                -- GST Recovered
  revenue REAL,                      -- Revenue from operations (Statutory Top Line)
  other_income REAL,                 -- Other income
  total_income REAL,                 -- Total income
  finance_costs REAL,                -- Finance / interest costs
  depreciation REAL,                 -- Depreciation & amortisation
  pbt_before_exceptional REAL,       -- PBT before exceptional items
  exceptional_items REAL,            -- Exceptional items (positive or negative)
  pbt REAL,                          -- Reported PBT (after exceptional items)
  tax_expense REAL,                  -- Tax expense
  pat REAL,                          -- Reported PAT before share of associates
  share_of_associates REAL,          -- Share of Profit / (Loss) of Associates and JVs
  pat_with_associates REAL,          -- PAT including share of associates and JVs (Headline IR PAT)
  pat_attributable_to_owners REAL,   -- Net Profit attributable to owners of the parent
  reported_ebitda REAL,              -- Explicitly disclosed by company, else NULL
  derived_ebitda REAL,               -- Deterministically calculated operating EBITDA
  derived_ebitda_method TEXT,        -- Explanation of components used
  ebitda_reconciliation_note TEXT,   -- Reconciles reported vs derived operating EBITDA
  raw_figures TEXT,                  -- JSON string of raw extracted dictionary
  source_doc_url TEXT,
  source_page INTEGER,
  source_table_name TEXT,
  needs_review INTEGER DEFAULT 0,
  review_reason TEXT,
  extracted_at TEXT NOT NULL,
  FOREIGN KEY(symbol) REFERENCES companies(symbol)
);
CREATE INDEX IF NOT EXISTS idx_qr_symbol_period ON quarterly_results(symbol, period_end_date);
CREATE INDEX IF NOT EXISTS idx_qr_filing ON quarterly_results(filing_id);

-- P1.2: Pull Research Engine (8 dimensions & primary source citations)
CREATE TABLE IF NOT EXISTS company_research (
  id TEXT PRIMARY KEY,               -- sha1(symbol + as_of_period)
  symbol TEXT NOT NULL,
  as_of_period TEXT NOT NULL,        -- e.g. 'Q2 FY27'
  as_of_date TEXT,                  -- YYYY-MM-DD
  source_documents TEXT,             -- JSON list of {doc_name, doc_type, url, sha256}
  business_snapshot TEXT,            -- JSON object (segments, revenue mix %, description)
  financial_snapshot TEXT,           -- JSON object (headline numbers, ratios, margins)
  trajectory TEXT,                   -- JSON object (multi-period directional trends)
  balance_sheet TEXT,                -- JSON object (debt, cash, net debt, leverage, working capital)
  cash_quality TEXT,                 -- JSON object (cash flow, cash conversion, FCF)
  narrative_vs_numbers TEXT,         -- JSON object/array (management commentary vs reality)
  guidance TEXT,                     -- JSON object/array (explicit forward guidance & status)
  bull_vs_bear TEXT,                 -- JSON object (bull points & bear points with citations)
  citations TEXT,                    -- JSON list of citations
  needs_review INTEGER DEFAULT 0,
  review_reason TEXT,
  generated_at TEXT NOT NULL,
  FOREIGN KEY(symbol) REFERENCES companies(symbol)
);
CREATE INDEX IF NOT EXISTS idx_research_symbol ON company_research(symbol);
CREATE INDEX IF NOT EXISTS idx_research_period ON company_research(symbol, as_of_period);

-- P1.3: Promise vs Delivered Engine (Management Commitments Tracking)
CREATE TABLE IF NOT EXISTS commitments (
  id TEXT PRIMARY KEY,                 -- sha1(symbol + source_doc + page + target_period + title)
  symbol TEXT NOT NULL,
  commitment_type TEXT NOT NULL,       -- 'EXPLICIT_COMMITMENT' | 'FORWARD_GUIDANCE' | 'STRATEGIC_INTENTION' | 'OPERATIONAL_MILESTONE'
  category TEXT NOT NULL,              -- 'capex' | 'capacity_commissioning' | 'revenue_margin' | 'operational_targets' | 'strategic_milestone'
  title TEXT NOT NULL,                 -- Short title
  statement TEXT NOT NULL,             -- Exact verbatim quote
  speaker TEXT,                        -- Speaker and designation
  source_doc_title TEXT NOT NULL,      -- e.g. 'Reliance Q2 FY27 Investor Presentation'
  source_doc_type TEXT NOT NULL,       -- 'investor_presentation' | 'results_filing' | 'agm_speech'
  source_page_or_slide TEXT NOT NULL,  -- e.g. 'Slide 14', 'Page 14 (Note 3)'
  source_url TEXT NOT NULL,            -- Official NSE archive link
  commitment_date TEXT NOT NULL,       -- YYYY-MM-DD
  commitment_period TEXT NOT NULL,     -- e.g. 'Q2 FY26', 'Q1 FY27'
  target_period TEXT NOT NULL,         -- e.g. 'Q2 FY27', 'FY27', 'FY28-FY29'
  target_value REAL,                   -- Numeric target if quantified
  target_unit TEXT,                    -- e.g. 'crore', 'mn_subscribers', 'stores'
  target_tolerance_pct REAL DEFAULT 0.0,
  actual_performance TEXT,            -- Nullable: actual disclosed text
  actual_value REAL,                   -- Nullable: numeric actual
  actual_unit TEXT,                    -- Nullable
  actual_source_doc TEXT,              -- Nullable
  actual_source_page_or_slide TEXT,    -- Nullable
  actual_source_url TEXT,              -- Nullable
  actual_reported_period TEXT,         -- Nullable: period when reported
  quarter_evaluations TEXT,            -- JSON array of quarterly progress updates across 4+ quarters
  status TEXT NOT NULL,                -- 'ACHIEVED' | 'PARTIALLY_ACHIEVED' | 'IN_PROGRESS' | 'DELAYED' | 'MISSED' | 'UNVERIFIABLE' | 'NEEDS_REVIEW'
  evaluation_reasoning TEXT NOT NULL,  -- Objective rationale for status
  is_quantified INTEGER DEFAULT 0,
  contributes_to_score INTEGER DEFAULT 1, -- 1 for genuine commitments, 0 for intentions/milestones
  needs_review INTEGER DEFAULT 0,
  review_reason TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(symbol) REFERENCES companies(symbol)
);
CREATE INDEX IF NOT EXISTS idx_commitments_symbol ON commitments(symbol);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_commitments_period ON commitments(symbol, target_period);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def session():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


ADDITIVE_COLUMNS = {
    "announcements": [("confidence", "REAL"), ("reason", "TEXT")],
    "quarterly_results": [
        ("gross_revenue", "REAL"),
        ("gst_recovered", "REAL"),
        ("share_of_associates", "REAL"),
        ("pat_with_associates", "REAL"),
        ("pat_attributable_to_owners", "REAL"),
        ("ebitda_reconciliation_note", "TEXT"),
    ],
}


def migrate(con) -> None:
    """Additive-only migration: add missing columns, never drop or rewrite data."""
    existing_tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "companies" in existing_tables and "company_research" not in existing_tables:
        con.execute("""
        CREATE TABLE IF NOT EXISTS company_research (
          id TEXT PRIMARY KEY,
          symbol TEXT NOT NULL,
          as_of_period TEXT NOT NULL,
          as_of_date TEXT,
          source_documents TEXT,
          business_snapshot TEXT,
          financial_snapshot TEXT,
          trajectory TEXT,
          balance_sheet TEXT,
          cash_quality TEXT,
          narrative_vs_numbers TEXT,
          guidance TEXT,
          bull_vs_bear TEXT,
          citations TEXT,
          needs_review INTEGER DEFAULT 0,
          review_reason TEXT,
          generated_at TEXT NOT NULL,
          FOREIGN KEY(symbol) REFERENCES companies(symbol)
        );
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_research_symbol ON company_research(symbol);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_research_period ON company_research(symbol, as_of_period);")
        existing_tables.add("company_research")

    if "companies" in existing_tables and "commitments" not in existing_tables:
        con.execute("""
        CREATE TABLE IF NOT EXISTS commitments (
          id TEXT PRIMARY KEY,
          symbol TEXT NOT NULL,
          commitment_type TEXT NOT NULL,
          category TEXT NOT NULL,
          title TEXT NOT NULL,
          statement TEXT NOT NULL,
          speaker TEXT,
          source_doc_title TEXT NOT NULL,
          source_doc_type TEXT NOT NULL,
          source_page_or_slide TEXT NOT NULL,
          source_url TEXT NOT NULL,
          commitment_date TEXT NOT NULL,
          commitment_period TEXT NOT NULL,
          target_period TEXT NOT NULL,
          target_value REAL,
          target_unit TEXT,
          target_tolerance_pct REAL DEFAULT 0.0,
          actual_performance TEXT,
          actual_value REAL,
          actual_unit TEXT,
          actual_source_doc TEXT,
          actual_source_page_or_slide TEXT,
          actual_source_url TEXT,
          actual_reported_period TEXT,
          quarter_evaluations TEXT,
          status TEXT NOT NULL,
          evaluation_reasoning TEXT NOT NULL,
          is_quantified INTEGER DEFAULT 0,
          contributes_to_score INTEGER DEFAULT 1,
          needs_review INTEGER DEFAULT 0,
          review_reason TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(symbol) REFERENCES companies(symbol)
        );
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_commitments_symbol ON commitments(symbol);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);")
        con.execute("CREATE INDEX IF NOT EXISTS idx_commitments_period ON commitments(symbol, target_period);")
        existing_tables.add("commitments")

    for table, cols in ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        have = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
        for name, typ in cols:
            if name not in have:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def init_db() -> None:
    with session() as con:
        con.executescript(SCHEMA)
        migrate(con)
        for sym, name, sector, size, weight in PORTFOLIO:
            con.execute(
                """INSERT INTO companies(symbol,name,sector,size_bucket,weight,in_portfolio)
                   VALUES(?,?,?,?,?,1)
                   ON CONFLICT(symbol) DO UPDATE SET name=excluded.name, sector=excluded.sector,
                   size_bucket=excluded.size_bucket, weight=excluded.weight, in_portfolio=1""",
                (sym, name, sector, size, weight),
            )


def set_feed_status(con, feed: str, status: str, fetched_at: str | None, note: str = "") -> None:
    con.execute(
        """INSERT INTO feed_status(feed,status,fetched_at,note) VALUES(?,?,?,?)
           ON CONFLICT(feed) DO UPDATE SET status=excluded.status,
           fetched_at=excluded.fetched_at, note=excluded.note""",
        (feed, status, fetched_at, note),
    )
