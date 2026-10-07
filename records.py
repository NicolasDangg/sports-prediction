"""Append-only research records, so every forecast can be evaluated later, not just the bets.

    state/forecasts.csv  every priced outcome on every run (passes included), with the
                         quotes seen, identity resolution and context. Never rewritten.
    state/outcomes.csv   final result per event (from The Odds API scores, or history files)
    state/closing.csv    closing prices per event outcome, for closing line value (CLV)

Historical files (football-data.co.uk for EPL, Kaggle for ATP) double as a second source
of results, so a missing API score is looked up before a bet is ever written off.
"""

from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt
import snapshots
from names import epl_team, player_profiles, tennis_player
from odds_api import winner_from_scores

STATE = Path(__file__).parent / "state"
FORECASTS, OUTCOMES, CLOSING = STATE / "forecasts.csv", STATE / "outcomes.csv", STATE / "closing.csv"


def _append(path: Path, rows: list[dict] | pd.DataFrame, key: list[str] | None = None) -> int:
    new = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if new.empty:
        return 0
    old = pd.read_csv(path, dtype=str) if path.exists() else pd.DataFrame()
    if key and len(old):
        seen = set(map(tuple, old[key].astype(str).to_numpy()))
        new = new[[tuple(map(str, k)) not in seen for k in new[key].to_numpy()]]
    if new.empty:
        return 0
    STATE.mkdir(exist_ok=True)
    pd.concat([old, new.astype(str)], ignore_index=True).to_csv(path, index=False)
    return len(new)


def append_forecasts(preds: pd.DataFrame, run_at: pd.Timestamp) -> int:
    if preds.empty:
        return 0
    return _append(FORECASTS, preds.assign(run_at=run_at.isoformat(timespec="seconds")))


def record_outcomes(score_cache: dict[str, list[dict]], now: pd.Timestamp) -> int:
    rows = []
    for key, events in score_cache.items():
        for e in events:
            winner = winner_from_scores(e)
            if winner is None:
                continue
            rows.append({"event_id": e["id"], "sport_key": key, "home": e["home_team"], "away": e["away_team"],
                         "commence_time": e["commence_time"], "winner": winner, "source": "odds_api",
                         "recorded_at": now.isoformat(timespec="seconds")})
    return _append(OUTCOMES, rows, key=["event_id"])


class History:
    """Find a live event in the historical files: result and closing odds."""

    def __init__(self) -> None:
        self.epl = bt.load_epl()
        self.epl_teams = set(self.epl.HomeTeam) | set(self.epl.AwayTeam)
        self.atp = bt.load_atp()
        self.profiles = player_profiles(self.atp)
        self.since = self.atp.date.max() - pd.Timedelta(days=365)

    def epl_event(self, home: str, away: str, commence: str) -> dict | None:
        h, a = epl_team(home, self.epl_teams), epl_team(away, self.epl_teams)
        if not h or not a:
            return None
        day = pd.Timestamp(commence).tz_convert(None).normalize()
        m = self.epl[(self.epl.HomeTeam == h) & (self.epl.AwayTeam == a)
                     & (self.epl.date.between(day - pd.Timedelta(days=1), day + pd.Timedelta(days=1)))]
        if m.empty:
            return None
        r = m.iloc[-1]
        winner = {"H": home, "D": "Draw", "A": away}[r.result]
        close, source = None, None
        for cols, src in ((("PSCH", "PSCD", "PSCA"), "pinnacle_close"), (("AvgCH", "AvgCD", "AvgCA"), "avg_close")):
            if all(c in r.index and pd.notna(r[c]) for c in cols):
                close, source = {home: r[cols[0]], "Draw": r[cols[1]], away: r[cols[2]]}, src
                break
        return {"winner": winner, "close": close, "close_source": source}

    def atp_event(self, p1: str, p2: str, commence: str) -> dict | None:
        a, b = (tennis_player(x, self.profiles, self.since) for x in (p1, p2))
        if not (a.ok and b.ok):
            return None
        day = pd.Timestamp(commence).tz_convert(None).normalize()
        df = self.atp
        m = df[(((df.Player_1 == a.name) & (df.Player_2 == b.name)) | ((df.Player_1 == b.name) & (df.Player_2 == a.name)))
               & df.date.between(day - pd.Timedelta(days=3), day + pd.Timedelta(days=1))]
        if m.empty:
            return None
        r = m.iloc[-1]
        winner = p1 if r.Winner == a.name else p2
        odds = {r.Player_1: r.Odd_1, r.Player_2: r.Odd_2}
        close = ({p1: odds[a.name], p2: odds[b.name]}
                 if all(pd.notna(v) and v > 1 for v in odds.values()) else None)
        return {"winner": winner, "close": close, "close_source": "kaggle_odds" if close else None}

    def lookup(self, sport: str, match: str, commence: str) -> dict | None:
        home, away = match.split(" v ", 1)
        return self.epl_event(home, away, commence) if sport == "epl" else self.atp_event(home, away, commence)


def record_closing(history: History, now: pd.Timestamp) -> int:
    """For forecast events that started 12h-21d ago and have no closing price yet, look one up.
    EPL: football-data closing odds (Pinnacle if present, else market average).
    ATP: our own last odds snapshot before the start (median across books; `minutes_before` says how
         close to the start it was), else Kaggle's odds column (one bookmaker, unclear timing: approximate)."""
    if not FORECASTS.exists():
        return 0
    f = pd.read_csv(FORECASTS, dtype=str)
    f["start"] = pd.to_datetime(f.commence_time, utc=True)
    done = set(pd.read_csv(CLOSING, dtype=str).event_id) if CLOSING.exists() else set()
    todo = (f[(f.start < now - timedelta(hours=12)) & (f.start > now - timedelta(days=21)) & ~f.event_id.isin(done)]
            .drop_duplicates("event_id"))
    snap = snapshots.closing_prices().set_index("event_id")
    rows = []
    for e in todo.itertuples():
        if e.sport == "atp" and e.event_id in snap.index:
            rows += [{"event_id": e.event_id, "outcome": r.outcome, "closing_odds": r.close_odds,
                      "source": "snapshot_median", "minutes_before": r.minutes_before,
                      "recorded_at": now.isoformat(timespec="seconds")}
                     for r in snap.loc[[e.event_id]].itertuples()]
            continue
        found = history.lookup(e.sport, e.match, e.commence_time)
        if found and found["close"]:
            rows += [{"event_id": e.event_id, "outcome": o, "closing_odds": round(float(p), 3),
                      "source": found["close_source"], "recorded_at": now.isoformat(timespec="seconds")}
                     for o, p in found["close"].items()]
    return _append(CLOSING, rows, key=["event_id", "outcome"])


def clv_summary(ledger: pd.DataFrame) -> str:
    """Closing line value: did we get a better price than the market's final one?
    clv = our odds / closing odds - 1. Positive on average = the market moved our way."""
    if not CLOSING.exists() or ledger.empty:
        return "CLV: no closing prices yet"
    c = pd.read_csv(CLOSING)
    m = ledger.merge(c, left_on=["event_id", "pick"], right_on=["event_id", "outcome"])
    if m.empty:
        return "CLV: no bets with closing prices yet"
    lines = []
    for wallet, g in m.groupby("wallet"):
        clv = g.odds / g.closing_odds - 1
        lines.append(f"  {wallet}: {len(g)} bets, mean CLV {clv.mean():+.1%}, beat close {np.mean(clv > 0):.0%}")
    return "CLV (our price vs closing):\n" + "\n".join(lines)
