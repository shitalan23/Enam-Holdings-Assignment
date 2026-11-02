"""EOD market maths. Pure, deterministic, no LLM. All numbers shown in the UI come from here."""
from datetime import datetime, timezone, timedelta
from .config import VOLUME_LOOKBACK

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE_MIN = 15 * 60 + 30  # NSE closes 15:30 IST


def now_ist() -> datetime:
    return datetime.now(IST)


def bars(con, symbol: str, limit: int = 60) -> list[dict]:
    rows = con.execute(
        "SELECT date, close, volume, source, fetched_at FROM prices_eod WHERE symbol=? "
        "AND close IS NOT NULL ORDER BY date DESC LIMIT ?", (symbol, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def _vol_multiple(series: list[dict], i: int) -> float | None:
    prior = [b["volume"] for b in series[max(0, i - VOLUME_LOOKBACK):i] if b["volume"]]
    if len(prior) < 5 or not series[i]["volume"]:
        return None
    avg = sum(prior) / len(prior)
    return round(series[i]["volume"] / avg, 2) if avg else None


def _pct(series: list[dict], i: int) -> float | None:
    if i < 1 or not series[i - 1]["close"]:
        return None
    return round((series[i]["close"] / series[i - 1]["close"] - 1) * 100, 2)


def latest_stats(series: list[dict]) -> dict | None:
    if len(series) < 2:
        return None
    i = len(series) - 1
    return {"date": series[i]["date"], "close": series[i]["close"],
            "prev_close": series[i - 1]["close"], "pct": _pct(series, i),
            "vol_x": _vol_multiple(series, i), "source": series[i]["source"],
            "fetched_at": series[i]["fetched_at"]}


def reaction(series: list[dict], ts_iso: str) -> dict | None:
    """The market's first full-session reaction to a filing.

    Filed during or before the session -> that day's bar. Filed after the 15:30
    close -> the next trading day's bar. If that bar doesn't exist yet, the market
    hasn't reacted and we return None rather than guess.
    """
    ts = datetime.fromisoformat(ts_iso).astimezone(IST)
    after_close = ts.hour * 60 + ts.minute >= MARKET_CLOSE_MIN
    day = ts.date().isoformat()
    for i, b in enumerate(series):
        if (b["date"] > day) if after_close else (b["date"] >= day):
            return {"date": b["date"], "pct": _pct(series, i), "vol_x": _vol_multiple(series, i)}
    return None
