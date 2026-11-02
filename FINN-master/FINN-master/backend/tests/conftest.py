import os, tempfile
# Set before finn.* is imported: tests only ever touch a throwaway database, never data/finn.db.
os.environ["FINN_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest

@pytest.fixture(autouse=True)
def clean_db():
    from finn.db import init_db, session
    init_db()
    with session() as con:
        for t in ("prices_eod", "announcements", "feed_status", "ingest_issues", "quarterly_results"):
            con.execute(f"DELETE FROM {t}")
    yield
