"""End-to-end smoke test of daily.py against a fake Odds API, on a throwaway copy of the repo.
Real state/ is never touched; no API credits are spent.

    uv run python tests/smoke_daily.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="sp-smoke-"))
for f in REPO.glob("*.py"):
    shutil.copy(f, TMP)
shutil.copy(REPO / "aliases.csv", TMP)
shutil.copytree(REPO / "state", TMP / "state")
(TMP / "data").symlink_to(REPO / "data")
sys.path.insert(0, str(TMP))

import accounts  # noqa: E402  (imported from the temp copy)
import daily  # noqa: E402
import news  # noqa: E402
import records  # noqa: E402
import snapshots  # noqa: E402
import strategies  # noqa: E402

assert Path(daily.__file__).parent == TMP, "must run against the temp copy"
daily.fpl.refresh = lambda: "FPL refresh skipped in smoke test"  # no network in tests
daily.STRATEGIES["test_v1"] = {"prob": lambda r: r["elo_p"], "min_edge": 0.05, "start_bankroll": 5000}
# News without network or LLM: Tomas Machac is "injured", everyone else fine.
import os  # noqa: E402
os.environ["OPENROUTER_API_KEY"] = "smoke-test"
INJURED = "Tomas Machac"
news.fetch_headlines = lambda player, now: [{"title": f"{player} news", "source": "test", "published": now}]
news.assess = lambda player, *a: {"status": "injured" if player == INJURED else "none", "confidence": 0.9,
                                  "summary": "smoke test", "evidence": ""}
# Make the injured player the one Elo would back: news_v1 must refuse while elo_v0 still bets.
daily.STRATEGIES["veto_probe"] = {"prob": lambda r: 0.0 if strategies.news_veto(r) else (0.9 if r["outcome"] == INJURED else 0.1),
                                  "min_edge": 0.05, "sports": ("atp",)}
daily.STRATEGIES["back_probe"] = {"prob": lambda r: 0.9 if r["outcome"] == INJURED else 0.1, "min_edge": 0.05,
                                  "sports": ("atp",)}


def book(key, prices, at="2026-10-07T00:00:00Z"):
    return {"key": key, "last_update": at,
            "markets": [{"key": "h2h", "last_update": at, "outcomes": [{"name": n, "price": p} for n, p in prices.items()]}]}


def ev(eid, start, home, away, books):
    return {"id": eid, "commence_time": start, "home_team": home, "away_team": away, "bookmakers": books}


def done(eid, start, home, away, sh, sa):
    return {"id": eid, "completed": True, "commence_time": start, "home_team": home, "away_team": away,
            "scores": [{"name": home, "score": str(sh)}, {"name": away, "score": str(sa)}]}


T = "2026-10-07T10:00:00Z"
ODDS = {
    "soccer_epl": [ev("e1", "2026-10-07T19:00:00Z", "Manchester City", "Hull City",
                      [book("pinnacle", {"Manchester City": 1.25, "Draw": 6.5, "Hull City": 13}),
                       book("bet365", {"Manchester City": 1.22, "Draw": 6.0, "Hull City": 12}),
                       book("unibet", {"Manchester City": 1.20, "Draw": 6.2, "Hull City": 14})])],
    "tennis_atp_shanghai_masters": [
        ev("t1", T, "Bu Yunchaokete", "Luca Van Assche", [book("pinnacle", {"Bu Yunchaokete": 1.9, "Luca Van Assche": 1.95}),
                                                           book("bet365", {"Bu Yunchaokete": 1.85, "Luca Van Assche": 2.0})]),
        ev("t2", T, "Wang Imaginaryplayer", "Jannik Sinner", [book("bet365", {"Wang Imaginaryplayer": 9.0, "Jannik Sinner": 1.05}),
                                                               book("pinnacle", {"Wang Imaginaryplayer": 12.0, "Jannik Sinner": 1.06}),
                                                               book("unibet", {"Wang Imaginaryplayer": 13.5, "Jannik Sinner": 1.04}),
                                                               book("betfair_ex_eu", {"Wang Imaginaryplayer": 30.0, "Jannik Sinner": 1.10})]),
        ev("t3", T, "Zhizhen Zhang", "Tomas Machac", [book("bet365", {"Zhizhen Zhang": 2.4, "Tomas Machac": 1.6}),
                                                       book("unibet", {"Zhizhen Zhang": 2.5, "Tomas Machac": 1.55})]),
    ],
}
SCORES_DAY2 = {
    "soccer_epl": [done("e1", "2026-10-07T19:00:00Z", "Manchester City", "Hull City", 1, 1)],
    "tennis_atp_shanghai_masters": [done("t1", T, "Bu Yunchaokete", "Luca Van Assche", 2, 1),
                                    done("t2", T, "Wang Imaginaryplayer", "Jannik Sinner", 0, 2),
                                    done("t3", T, "Zhizhen Zhang", "Tomas Machac", 0, 2)],
}


class FakeAPI:
    remaining = "999"

    def __init__(self, day):
        self.day = day

    def active_atp_keys(self):
        return [{"key": "tennis_atp_shanghai_masters", "title": "ATP Shanghai Masters", "active": True}]

    def odds(self, key):
        return ODDS.get(key, []) if self.day == 1 else []

    def scores(self, key):
        return SCORES_DAY2.get(key, []) if self.day >= 2 else []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        raise SystemExit(1)


print(f"temp repo: {TMP}")
real_open = set(pd.read_csv(TMP / "state/ledger.csv").query("status == 'open'").bet_id)

# ---- day 1: forecast + bet
daily.main(FakeAPI(1), pd.Timestamp("2026-10-07T01:00:00Z"), download=False)
f = pd.read_csv(TMP / "state/forecasts.csv")
led = pd.read_csv(TMP / "state/ledger.csv")
dep = pd.read_csv(TMP / "state/deposits.csv")
print("\nDAY 1 checks")
check(set(f.event_id) >= {"e1", "t1", "t2", "t3"}, "every priced event logged in forecasts.csv (passes included)")
t2 = f[f.event_id == "t2"]
check((t2.eligible.astype(str) == "False").all() and t2.elo_p.isna().all(), "unknown player -> forecast logged, not bettable")
check(not led[led.strategy != "sharp_v1"].event_id.isin(["t2"]).any(), "no model bet on the unknown-player match")
sh = led[(led.strategy == "sharp_v1") & led.event_id.isin(["e1", "t1", "t2", "t3"])].set_index("event_id")
check(sh.loc["e1", "pick"] == "Hull City" and sh.loc["e1", "odds"] == 14 and sh.loc["e1", "exec_book"] == "unibet",
      "sharp_v1 bets the soft price above Pinnacle's fair price (Hull 14 at unibet vs fair 13.4)")
check(abs(sh.loc["e1", "model_p"] - 0.0746) < 1e-3, "sharp_v1 probability = Pinnacle with the margin removed")
check("t1" not in sh.index, "sharp_v1 passes when no book beats Pinnacle's fair price")
check("t3" not in sh.index, "sharp_v1 never bets without a Pinnacle price")
check(sh.loc["t2", "odds"] == 13.5 and sh.loc["t2", "exec_book"] == "unibet",
      "sharp_v1 needs no model (bets an unknown player) and ignores exchange prices (30.0 on betfair_ex)")
e1 = f[f.event_id == "e1"].set_index("outcome")
check(e1.loc["Hull City", "best_odds"] == 14 and abs(e1.pin_fair_p.sum() - 1) < 1e-3, "forecast rows carry best price and Pinnacle fair p")
check(((dep.wallet == "epl:sharp_v1") & (dep.kind == "open")).any() and ((dep.wallet == "atp:sharp_v1") & (dep.kind == "open")).any(),
      "sharp_v1 opens a wallet per sport")
t1 = f[f.event_id == "t1"]
check(set(t1.resolved_as) == {"Bu Y. | Van Assche L."}, "Bu Yunchaokete resolves to 'Bu Y.'")
check(set(f[f.event_id == "t3"].resolved_as) == {"Zhang Zh. | Machac T."}, "Zhizhen Zhang resolves to 'Zhang Zh.'")
check(((f.odds <= f.median_odds + 1e-9) | f.median_odds.isna()).all(), "execution price is never above the median")
check(f.exec_book.notna().all(), "execution bookmaker recorded")
atp1 = f[(f.sport == "atp") & (f.eligible.astype(str) == "True") & f.run_at.astype(str).str.startswith("2026-10-07T01")]
check(atp1.forecast_p.notna().any() and ((atp1.forecast_p > 0) & (atp1.forecast_p < 1)).all(), "E009 forecaster fills forecast_p for known players")
pair = atp1.groupby("event_id").forecast_p.sum()
check(((pair - 1).abs() < 1e-3).all(), "forecast_p of the two players sums to 1")
check(((dep.wallet == "atp:test_v1") & (dep.kind == "open") & (dep.amount == 5000)).any(), "new strategy opens its own $5,000 wallet")
new_bets = led[~led.bet_id.isin(real_open) & (led.status == "open") & led.placed_at.str.startswith("2026-10-07")]
check("epl:news_v1" not in dep.wallet.values and "atp:news_v1" in dep.wallet.values, "'sports' key: news_v1 gets an ATP wallet only")
nw = pd.read_csv(TMP / "state/news.csv")
check({"Zhizhen Zhang", "Tomas Machac"} <= set(nw.player), "news verdicts logged for players in the betting window")
check(set(f.loc[f.outcome == INJURED, "news_status"].dropna()) == {"injured"}, "news status attached to the forecast rows")
check(((new_bets.strategy == "back_probe") & (new_bets.pick == INJURED)).any(), "probe without the veto backs the injured player")
check(not ((new_bets.strategy == "veto_probe") & (new_bets.pick == INJURED)).any(), "veto: never back a player with injury news")
check(not new_bets.strategy.str.startswith("news_v1").any() or not (new_bets[new_bets.strategy == "news_v1"].pick == INJURED).any(),
      "news_v1 never backs the injured player")
snap = pd.read_csv(TMP / "state/odds_snapshots.csv")
check(set(snap[snap["at"].str.startswith("2026-10-07T01")].event_id) >= {"e1", "t1", "t3"}, "daily run's prices saved as snapshots (no extra credit)")
check(len(new_bets) > 0 and new_bets.exec_book.notna().all(), f"{len(new_bets)} new bets placed at real recorded quotes")

# ---- day 2: settle from API, record outcomes + results
daily.main(FakeAPI(2), pd.Timestamp("2026-10-08T01:00:00Z"), download=False)
led = pd.read_csv(TMP / "state/ledger.csv")
out = pd.read_csv(TMP / "state/outcomes.csv")
rec = pd.read_csv(TMP / "state/atp_recent.csv")
print("\nDAY 2 checks")
check(led[led.event_id.isin(["e1", "t1", "t3"])].status.isin(["won", "lost"]).all(), "fake-API bets settled")
check((led[led.event_id.isin(["e1", "t1", "t3"])].result_source == "odds_api").all(), "result source recorded")
check({"e1", "t1", "t2", "t3"} <= set(out.event_id), "outcomes recorded for every finished event")
check(not rec.event_id.isin(["t2"]).any(), "unknown-player result NOT stored (no phantom players)")
check(rec[rec.event_id == "t1"][["Player_1", "Player_2"]].values.tolist() == [["Bu Y.", "Van Assche L."]], "t1 result stored under real identities")

# ---- day 3 (16 days later): old real bets with no result anywhere -> unresolved, refunded
cash_before = {w: v["cash"] for w, v in __import__("json").loads((TMP / "state/wallets.json").read_text()).items()}
daily.main(FakeAPI(3), pd.Timestamp("2026-10-23T01:00:00Z"), download=False)
led = pd.read_csv(TMP / "state/ledger.csv")
hist = pd.read_csv(TMP / "state/bankroll_history.csv")
print("\nDAY 3 checks")
check((led[led.bet_id.isin(real_open)].status == "unresolved").all(), "missing results become 'unresolved', not 'void'")
check({"deposits", "net"} <= set(hist.columns), "bankroll history tracks deposits and net profit")
last = hist[hist.date == "2026-10-23"].set_index("wallet")
check((abs(last.bankroll - last.deposits - last.net) < 0.01).all(), "net = bankroll - deposits")

# ---- history fallback lookup (a real Kaggle match: Sinner v Zverev)
h = records.History()
pair = {"Sinner J.", "Zverev A."}
m = h.atp[h.atp.Player_1.isin(pair) & h.atp.Player_2.isin(pair)].iloc[-1]
start = pd.Timestamp(m.date).tz_localize("UTC").isoformat()
found = h.atp_event("Jannik Sinner", "Alexander Zverev", start)
expect = "Jannik Sinner" if m.Winner == "Sinner J." else "Alexander Zverev"
check(found is not None and found["winner"] == expect, f"history fallback finds {m.date.date()} Sinner v Zverev, winner {expect}")
check(h.atp_event("Jannik Sinner", "Wang Imaginaryplayer", start) is None, "history lookup refuses an unresolvable player")

# ---- refill: top a wallet up to a target above its current bankroll
w, deps = __import__("json").loads((TMP / "state/wallets.json").read_text()), accounts.load_deposits()
target = accounts.bankroll(w, led, "atp:elo_v0") + 750
deps = accounts.record(deps, w, "atp:elo_v0", target - accounts.bankroll(w, led, "atp:elo_v0"), "refill", "smoke test", "2026-10-23T02:00:00Z")
check(abs(accounts.bankroll(w, led, "atp:elo_v0") - target) < 0.01, "refill tops the bankroll up to the target")
check(deps.iloc[-1].kind == "refill" and abs(deps.iloc[-1].amount - 750) < 0.01, "refill recorded in deposits.csv")

print("\nSTALE rating checks")
from names import stale_ratings  # noqa: E402

day = pd.Timestamp("2026-10-01")
games = ([("Active A.", day - pd.Timedelta(days=d)) for d in (1, 30, 60)]
         + [("Gone G.", day - pd.Timedelta(days=400))]
         + [("Back B.", day - pd.Timedelta(days=d)) for d in (500, 10, 5)]
         + [("Back C.", day - pd.Timedelta(days=d)) for d in (500, 50, 40, 30, 20, 10)])
st = stale_ratings(pd.DataFrame({"Player_1": [p for p, _ in games], "Player_2": "Opp O.", "date": [d for _, d in games]}))
check("Active A." not in st and "Opp O." not in st, "regular players are fresh")
check(st.get("Gone G.", "").startswith("last match"), "no match for over 180 days -> stale")
check("2 match(es) since" in st.get("Back B.", ""), "back from a long break with < 5 matches -> stale")
check("Back C." not in st, "back with 5 matches -> trusted again")

print("\nSNAPSHOT / CLOSING checks")


class SnapAPI(FakeAPI):
    def __init__(self, remaining):
        super().__init__(1)
        self.remaining, self.calls = str(remaining), 0

    def odds(self, key):
        self.calls += 1
        self.remaining = str(int(self.remaining) - 1)
        return [ev("t3", T, "Zhizhen Zhang", "Tomas Machac", [book("bet365", {"Zhizhen Zhang": 2.2, "Tomas Machac": 1.7}),
                                                               book("unibet", {"Zhizhen Zhang": 2.3, "Tomas Machac": 1.65})])]


at = pd.Timestamp("2026-10-07T06:00:00Z")
poor = SnapAPI(snapshots.credits_reserved(at))  # exactly the reserve: must not spend
snapshots.run(poor, at)
check(poor.calls == 0, "snapshot run never spends credits reserved for the daily runs")
rich = SnapAPI(400)
snapshots.run(rich, at)
check(rich.calls == 1, "snapshot run fetches the tournament with a match starting soon")
cp = snapshots.closing_prices().set_index(["event_id", "outcome"])
row = cp.loc[("t3", "Tomas Machac")]
check(row.close_odds == 1.675 and row.minutes_before == 240 and row.open_odds != row.close_odds,
      "closing = last pre-start snapshot (4h before), opening = first seen")
cl = pd.read_csv(TMP / "state/closing.csv")  # recorded by the day-2 run, from the daily run's own snapshot
t3c = cl[cl.event_id == "t3"]
check(len(t3c) == 2 and (t3c.source == "snapshot_median").all() and (t3c.minutes_before == 540).all(),
      "ATP closing comes from our snapshots, with minutes before the start")

# ---- E013 casual weekly session (pure place_bets, in memory)
def prow(eid, outcome, p, odds, sport="atp"):
    return {"sport": sport, "event_id": eid, "outcome": outcome, "commence_time": "2026-10-10T08:00:00Z",
            "sport_key": "k", "competition": "c", "match": f"{eid} match", "elo_p": float("nan"), "market_p": p,
            "pin_fair_p": p, "odds": odds, "exec_book": "bet365", "quote_at": "", "median_odds": odds, "n_books": 5,
            "best_odds": odds, "best_book": "bet365", "best_at": "", "eligible": False}
cp = pd.DataFrame([prow("c1", "A", 0.92, 1.06), prow("c1", "B", 0.08, 9.0), prow("c2", "C", 0.85, 1.12),
                   prow("c2", "D", 0.15, 5.5), prow("c3", "E", 0.60, 1.6), prow("c3", "F", 0.40, 2.4)])
cw = {f"atp:{n}": {"cash": 1000.0} for n in daily.STRATEGIES} | {f"epl:{n}": {"cash": 1000.0} for n in daily.STRATEGIES}
empty = led.iloc[0:0].copy()
sat, wed = pd.Timestamp("2026-10-09T23:00:00Z"), pd.Timestamp("2026-10-06T23:00:00Z")  # Sat / Wed 06:00 Saigon
cl, _ = daily.place_bets(cp, empty, {k: dict(v) for k, v in cw.items()}, wed)
check(not cl.strategy.str.startswith("casual").any(), "casual wallets don't bet outside the weekly session")
cl, _ = daily.place_bets(cp, empty, cw, sat)
big, many = cl[cl.strategy == "casual_big_v1"], cl[cl.strategy == "casual_many_v1"]
check(list(big.pick) == ["A"] and big.stake.iloc[0] == 250, "casual_big_v1: 25% of the wallet on the single likeliest winner")
check(sorted(many.pick) == ["A", "C"] and (many.stake == 125).all(), "casual_many_v1: 25% split over every 80%+ favourite")
cl2, _ = daily.place_bets(cp, cl, cw, sat + pd.Timedelta(hours=1))
check(len(cl2[cl2.strategy.str.startswith("casual")]) == len(cl[cl.strategy.str.startswith("casual")]), "one session per day, even if re-run")

shutil.rmtree(TMP)
print("\nall smoke checks passed")
