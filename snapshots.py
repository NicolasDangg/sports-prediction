"""Odds snapshots over time, for closing line value (CLV) and the timing study.

Prices move as a match approaches: news comes out, sharp money comes in, and the last
price before the start (the "closing" price) is the market's best guess. Two questions
need prices from more than one moment:
  - CLV: did we bet at a better price than the closing one? Beating the close on average
    is the fastest honest sign of a real edge (it settles in weeks, P&L takes months).
  - Timing: are early prices softer than late ones, so betting early pays?

Every odds response we get is appended to state/odds_snapshots.csv, one row per outcome.
The daily run's fetch is recorded for free. This file can also run on its own a few
times a day to catch prices nearer the start:

    uv run --env-file .env python snapshots.py        (writes state/; costs 1 credit per tournament)

Credit guard: The Odds API free plan has 500 credits a month and the daily run needs
about DAILY_COST a day. A snapshot run never spends credits the remaining daily runs
of the month will need.
"""

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

from odds_api import OddsAPI, price_summary

STATE = Path(__file__).parent / "state"
SNAPSHOTS = STATE / "odds_snapshots.csv"
FORECASTS = STATE / "forecasts.csv"
COLS = ["at", "source", "sport", "sport_key", "event_id", "commence_time", "outcome",
        "median_odds", "pinnacle_odds", "best_odds", "n_books"]
HORIZON_HOURS = 8  # a snapshot run only fetches tournaments with a match starting in the next 8 hours
DAILY_COST = 12  # credits a daily run can use (observed ~10), kept in reserve for every day left this month


def rows(events: list[dict], sport: str, sport_key: str, at: pd.Timestamp, source: str) -> list[dict]:
    out = []
    for e in events:
        prices, n_books = price_summary(e)
        best = {}
        for b in e.get("bookmakers", []):
            for m in b.get("markets", []):
                if m["key"] == "h2h":
                    for o in m["outcomes"]:
                        best[o["name"]] = max(best.get(o["name"], 0), float(o["price"]))
        for name, q in prices.items():
            out.append({"at": at.isoformat(timespec="seconds"), "source": source, "sport": sport,
                        "sport_key": sport_key, "event_id": e["id"], "commence_time": e["commence_time"],
                        "outcome": name, "median_odds": q["median"], "pinnacle_odds": q["pinnacle"],
                        "best_odds": best.get(name), "n_books": n_books})
    return out


def record(new_rows: list[dict]) -> int:
    """Append only: a snapshot is never rewritten, even if the same price shows up twice."""
    if not new_rows:
        return 0
    new = pd.DataFrame(new_rows, columns=COLS)
    STATE.mkdir(exist_ok=True)
    new.to_csv(SNAPSHOTS, mode="a", header=not SNAPSHOTS.exists(), index=False)
    return len(new)


def closing_prices(snaps: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per event outcome: the first price we ever saw (opening) and the last one before the start
    (closing), with how many minutes before the start that last snapshot was taken."""
    s = snaps if snaps is not None else (pd.read_csv(SNAPSHOTS) if SNAPSHOTS.exists() else pd.DataFrame(columns=COLS))
    if s.empty:
        return pd.DataFrame(columns=["event_id", "outcome", "open_odds", "open_at", "close_odds", "close_at",
                                     "close_pinnacle", "minutes_before", "n_snapshots"])
    s = s.assign(at_ts=pd.to_datetime(s["at"], utc=True), start=pd.to_datetime(s.commence_time, utc=True))
    s = s[s.at_ts < s.start].sort_values("at_ts")
    g = s.groupby(["event_id", "outcome"])
    first, last = g.first(), g.last()
    return pd.DataFrame({
        "open_odds": first.median_odds, "open_at": first["at"],
        "close_odds": last.median_odds, "close_at": last["at"], "close_pinnacle": last.pinnacle_odds,
        "minutes_before": ((last.start - last.at_ts).dt.total_seconds() / 60).round(), "n_snapshots": g.size(),
    }).reset_index()


def credits_reserved(now: pd.Timestamp) -> int:
    """Credits the daily runs still need this month (today's included)."""
    next_month = (now.normalize().replace(day=1) + pd.offsets.MonthBegin(1))
    return DAILY_COST * max(1, (next_month - now.normalize()).days)


def keys_starting_soon(now: pd.Timestamp) -> set[str]:
    """ATP tournaments with a forecast match starting within the horizon (known from the daily run)."""
    if not FORECASTS.exists():
        return set()
    f = pd.read_csv(FORECASTS, usecols=["sport", "sport_key", "commence_time"])
    start = pd.to_datetime(f.commence_time, utc=True)
    soon = (f.sport == "atp") & (start > now) & (start <= now + timedelta(hours=HORIZON_HOURS))
    return set(f.loc[soon, "sport_key"])


def run(api: OddsAPI | None = None, now: pd.Timestamp | None = None) -> None:
    api = api or OddsAPI()
    now = now or pd.Timestamp.now(tz="UTC")
    active = {s["key"] for s in api.active_atp_keys()}  # free call; also tells us credits left
    todo = sorted(keys_starting_soon(now) & active)
    reserve = credits_reserved(now)
    print(f"snapshot {now.isoformat(timespec='minutes')}: {len(todo)} ATP tournaments with matches in the next "
          f"{HORIZON_HOURS}h; credits left {api.remaining}, reserved for daily runs {reserve}")
    n = 0
    for key in todo:
        left = int(api.remaining) if api.remaining is not None else 0
        if left - 1 < reserve:
            print(f"  STOP: fetching {key} would dip into the credits the daily runs need")
            break
        n += record(rows(api.odds(key), "atp", key, now, "snapshot"))
    print(f"  recorded {n} prices; credits left {api.remaining}")


if __name__ == "__main__":
    run()
    sys.exit(0)
