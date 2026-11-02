"""Central config: paths, the demo portfolio, and default alert thresholds.

The portfolio below is a MOCK portfolio chosen to span sectors and market-cap
sizes. Weights are illustrative (they feed the priority score), not real holdings.
Symbols are verified at ingest time: if a ticker has been renamed or delisted,
ingest records it as UNAVAILABLE instead of guessing.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("FINN_DB", ROOT / "data" / "finn.db"))
STATIC_DIR = ROOT / "backend" / "static"

# symbol, display name, sector, size bucket, mock weight (%)
PORTFOLIO = [
    ("RELIANCE",   "Reliance Industries",       "Energy & Conglomerate",  "Large", 9.0),
    ("TCS",        "Tata Consultancy Services", "IT Services",            "Large", 8.0),
    ("HDFCBANK",   "HDFC Bank",                 "Banking",                "Large", 9.0),
    ("INFY",       "Infosys",                   "IT Services",            "Large", 6.0),
    ("ITC",        "ITC",                       "FMCG & Tobacco",         "Large", 6.0),
    ("LT",         "Larsen & Toubro",           "Infrastructure",         "Large", 6.0),
    ("SUNPHARMA",  "Sun Pharmaceutical",        "Pharma",                 "Large", 5.0),
    ("MARUTI",     "Maruti Suzuki",             "Auto",                   "Large", 5.0),
    ("TITAN",      "Titan Company",             "Consumer Discretionary", "Large", 5.0),
    ("BAJFINANCE", "Bajaj Finance",             "NBFC",                   "Large", 6.0),
    ("DIXON",      "Dixon Technologies",        "Electronics Mfg",        "Mid",   4.0),
    ("POLYCAB",    "Polycab India",             "Cables & Wires",         "Mid",   4.0),
    ("PERSISTENT", "Persistent Systems",        "IT Services",            "Mid",   4.0),
    ("TRENT",      "Trent",                     "Retail",                 "Mid",   4.0),
    ("ETERNAL",    "Eternal (ex-Zomato)",       "Consumer Internet",      "Mid",   4.0),
    ("KPITTECH",   "KPIT Technologies",         "Auto Software",          "Mid",   3.0),
    ("CDSL",       "Central Depository Services", "Capital Markets",      "Small", 2.0),
]

# Default unusual-move thresholds (user-configurable in the Alerts tab, built in P1).
DEFAULT_VOLUME_MULT = 2.0     # volume vs trailing average
DEFAULT_PRICE_MOVE_PCT = 5.0  # absolute 1-day close-to-close move
VOLUME_LOOKBACK = 20          # trading days for the volume average
