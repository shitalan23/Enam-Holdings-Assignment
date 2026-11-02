import glob, os, sqlite3
from finn import cli
from finn.config import DB_PATH
from finn.db import migrate, session
from helpers import NOW, add_filing

def test_migration_is_additive_idempotent_and_keeps_rows():
    con = sqlite3.connect(":memory:"); con.row_factory = sqlite3.Row
    con.execute("CREATE TABLE announcements (id TEXT PRIMARY KEY, symbol TEXT, headline TEXT, category TEXT)")
    con.execute("INSERT INTO announcements VALUES ('a','TCS','Financial Results','results')")
    migrate(con); migrate(con)   # twice: must not fail
    cols = {r["name"] for r in con.execute("PRAGMA table_info(announcements)")}
    assert {"confidence", "reason"} <= cols
    assert con.execute("SELECT headline, category FROM announcements").fetchone()[:] == ("Financial Results", "results")

def _legacy():
    add_filing("TCS", 2, "Copy of Newspaper Publication", "Financial results published", "results", None, conf=None, fid="bad1")
    add_filing("TCS", 3, "Financial Results", "Unaudited results for the quarter ended", "results", None, conf=None, fid="good1")
    add_filing("TCS", 4, "Trading Window", "closure", "unclassified", None, conf=None, fid="mock1", source="MOCK")

def _cat(i):
    with session() as con:
        return con.execute("SELECT category, confidence FROM announcements WHERE id=?", (i,)).fetchone()

def test_dry_run_writes_nothing_and_makes_no_backup(capsys):
    _legacy()
    cli.cmd_reclassify(apply=False)
    assert "DRY RUN" in capsys.readouterr().out
    assert tuple(_cat("bad1")) == ("results", None)
    assert not glob.glob(str(DB_PATH) + ".bak-*")

def test_apply_backs_up_first_fixes_rows_and_never_touches_mock(capsys):
    _legacy()
    cli.cmd_reclassify(apply=True)
    assert _cat("bad1")["category"] == "routine_compliance" and _cat("bad1")["confidence"] is not None
    assert _cat("good1")["category"] == "results"
    assert tuple(_cat("mock1")) == ("unclassified", None)     # MOCK rows are left alone
    backups = glob.glob(str(DB_PATH) + ".bak-*")
    assert backups, "a backup must exist"
    old = sqlite3.connect(backups[-1]).execute("SELECT category FROM announcements WHERE id='bad1'").fetchone()[0]
    assert old == "results"                                   # the backup holds the pre-change data
    for b in backups: os.remove(b)

def test_reclassify_does_not_touch_prices():
    from helpers import add_bar
    add_bar("TCS", "2026-10-30", 123.0)
    _legacy(); cli.cmd_reclassify(apply=True)
    with session() as con:
        assert con.execute("SELECT close FROM prices_eod WHERE symbol='TCS'").fetchone()[0] == 123.0
    for b in glob.glob(str(DB_PATH) + ".bak-*"): os.remove(b)
