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
import records  # noqa: E402

assert Path(daily.__file__).parent == TMP, "must run against the temp copy"
daily.fpl.refresh = lambda: "FPL refresh skipped in smoke test"  # no network in tests
daily.STRATEGIES["test_v1"] = {"prob": lambda r: r["elo_p"], "min_edge": 0.05, "start_bankroll": 5000}


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
        ev("t2", T, "Wang Imaginaryplayer", "Jannik Sinner", [book("bet365", {"Wang Imaginaryplayer": 9.0, "Jannik Sinner": 1.05})]),
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
check(not led.event_id.isin(["t2"]).any(), "no bet on the unknown-player match")
t1 = f[f.event_id == "t1"]
check(set(t1.resolved_as) == {"Bu Y. | Van Assche L."}, "Bu Yunchaokete resolves to 'Bu Y.'")
check(set(f[f.event_id == "t3"].resolved_as) == {"Zhang Zh. | Machac T."}, "Zhizhen Zhang resolves to 'Zhang Zh.'")
check(((f.odds <= f.median_odds + 1e-9) | f.median_odds.isna()).all(), "execution price is never above the median")
check(f.exec_book.notna().all(), "execution bookmaker recorded")
check(((dep.wallet == "atp:test_v1") & (dep.kind == "open") & (dep.amount == 5000)).any(), "new strategy opens its own $5,000 wallet")
new_bets = led[~led.bet_id.isin(real_open) & (led.status == "open") & led.placed_at.str.startswith("2026-10-07")]
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

shutil.rmtree(TMP)
print("\nall smoke checks passed")
