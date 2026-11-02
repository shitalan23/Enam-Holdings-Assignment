"""EOD prices are never 'live'. Statuses are derived from the data, not from a stored label."""
from datetime import datetime, timedelta
import pytest
from finn import api
from finn.db import session
from finn.market import IST
from helpers import NOW, add_bar, add_filing

@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(api, "now_ist", lambda: NOW)

def st(fn):
    with session() as con:
        return fn(con)

def test_expected_last_session_handles_weekends_and_the_close():
    f = api.expected_last_session
    assert f(datetime(2026, 11, 1, 12, 0, tzinfo=IST)) == "2026-10-30"    # Sunday -> Friday
    assert f(datetime(2026, 10, 31, 12, 0, tzinfo=IST)) == "2026-10-30"   # Saturday -> Friday
    assert f(datetime(2026, 10, 26, 10, 0, tzinfo=IST)) == "2026-10-23"   # Monday before close -> Friday
    assert f(datetime(2026, 10, 26, 17, 0, tzinfo=IST)) == "2026-10-26"   # Monday after close -> Monday

def test_current_prices_are_EOD_never_live_or_delayed():
    add_bar("TCS", "2026-10-30", 100)
    p = st(api.prices_status)
    assert p["status"] == "EOD" and p["as_of"] == "2026-10-30"
    assert "not live" in p["note"].lower()
    assert p["status"] not in ("LIVE", "DELAYED")

def test_prices_missing_recent_sessions_are_cached():
    add_bar("TCS", "2026-10-28", 100)
    p = st(api.prices_status)
    assert p["status"] == "CACHED" and "2026-10-30" in p["note"]

def test_mock_prices_are_mock_and_empty_is_unavailable():
    assert st(api.prices_status)["status"] == "UNAVAILABLE"
    add_bar("TCS", "2026-10-30", 100, source="MOCK")
    assert st(api.prices_status)["status"] == "MOCK"

def test_real_data_wins_over_leftover_mock_in_the_label_only_when_real_exists():
    add_bar("TCS", "2026-10-30", 100, source="MOCK")
    add_bar("INFY", "2026-10-30", 100, source="yfinance")
    assert st(api.prices_status)["status"] == "EOD"

def test_filings_are_delayed_when_fresh_cached_when_old_and_never_live():
    add_filing("TCS", 5, "Financial Results", fetched=(NOW - timedelta(hours=2)).isoformat())
    f = st(api.filings_status)
    assert f["status"] == "DELAYED" and f["status"] != "LIVE"
    with session() as con:
        con.execute("UPDATE announcements SET fetched_at=?", ((NOW - timedelta(days=3)).isoformat(),))
    assert st(api.filings_status)["status"] == "CACHED"

def test_mock_filings_and_empty_feed():
    assert st(api.filings_status)["status"] == "UNAVAILABLE"
    add_filing("TCS", 5, "Financial Results", source="MOCK")
    assert st(api.filings_status)["status"] == "MOCK"

def test_stored_feed_labels_cannot_mislabel_the_data():
    # Old ingests stored LIVE for filings and DELAYED for prices. The API ignores stored labels.
    add_bar("TCS", "2026-10-30", 100)
    with session() as con:
        con.execute("INSERT INTO feed_status VALUES ('prices','LIVE',?, 'old label')", (NOW.isoformat(),))
    assert st(api.prices_status)["status"] == "EOD"
