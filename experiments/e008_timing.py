"""E008: timing and closing line value (CLV), from our own live odds snapshots.

Questions (pre-registered in experiments/LOG.md):
  1. Does the closing price beat the first price we saw? (It should: that's the market learning.)
  2. Do prices move toward Elo between our first sighting and the close? If yes, Elo knows
     something the early market hasn't priced yet, and betting early is where any edge lives.
  3. CLV per wallet: our bet price / closing price − 1. Positive on average = we beat the close.

ATP only: EPL closing comes from football-data and has no early snapshots.
Run any time; it says when there isn't enough data yet.

    uv run python -W ignore experiments/e008_timing.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import snapshots  # noqa: E402

STATE = ROOT / "state"
MAX_CLOSE_MINUTES = 180  # a "closing" price taken more than 3h before the start doesn't count
MIN_EVENTS, MIN_BETS = 150, 150  # pre-registered sample sizes before drawing conclusions
rng = np.random.default_rng(8)


def ci(x: np.ndarray, reps: int = 2000) -> tuple[float, float]:
    if len(x) < 2:
        return (np.nan, np.nan)
    m = [rng.choice(x, len(x)).mean() for _ in range(reps)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def fmt(x: np.ndarray, pct: bool = True) -> str:
    lo, hi = ci(x)
    f = (lambda v: f"{v:+.2%}") if pct else (lambda v: f"{v:+.4f}")
    return f"{f(x.mean())} [{f(lo)}, {f(hi)}] (n={len(x)})"


def main() -> None:
    cp = snapshots.closing_prices()
    f = pd.read_csv(STATE / "forecasts.csv")
    f = f[f.sport == "atp"].sort_values("run_at").drop_duplicates(["event_id", "outcome"])  # first forecast
    out = pd.read_csv(STATE / "outcomes.csv") if (STATE / "outcomes.csv").exists() else pd.DataFrame(columns=["event_id", "winner"])
    m = f.merge(cp, on=["event_id", "outcome"]).merge(out[["event_id", "winner"]], on="event_id", how="left")
    good = m[(m.minutes_before <= MAX_CLOSE_MINUTES) & (m.n_snapshots >= 2)]

    print(f"ATP outcomes with snapshots: {len(m)} ({m.event_id.nunique()} events); "
          f"usable (≥2 snapshots, close ≤ {MAX_CLOSE_MINUTES} min before start): {good.event_id.nunique()} events")
    if len(m):
        print(f"  closing snapshot taken a median {m.minutes_before.median():.0f} min before the start")

    # 1 + 2: one row per event (the first-listed player), with both players' prices to remove the vig
    pairs = good.groupby("event_id").filter(lambda g: len(g) == 2).sort_values(["event_id", "outcome"])
    a, b = pairs.groupby("event_id").first(), pairs.groupby("event_id").last()
    if len(a):
        novig = lambda x, y: (1 / x) / (1 / x + 1 / y)  # noqa: E731
        p_open, p_close = novig(a.open_odds, b.open_odds), novig(a.close_odds, b.close_odds)
        moved = p_close - p_open
        toward = (np.sign(a.elo_p - p_open) == np.sign(moved))[moved != 0]
        print(f"\nPrice movement first sighting → close ({len(a)} events): mean |Δp| {np.abs(moved).mean():.3f}; "
              f"moved toward Elo in {toward.mean():.0%} of {len(toward)} moves")
        done = a.winner.notna()
        if done.any():
            y = (a.winner[done] == a.outcome[done]).astype(int).to_numpy()
            ll = lambda p: -(y * np.log(p) + (1 - y) * np.log(1 - p))  # noqa: E731
            lo, lc, le = ll(p_open[done].to_numpy()), ll(p_close[done].to_numpy()), ll(a.elo_p[done].to_numpy())
            print(f"Log loss on {done.sum()} settled events: Elo {le.mean():.4f}  first price {lo.mean():.4f}  "
                  f"closing {lc.mean():.4f}")
            print(f"  closing beats first price by {fmt(lo - lc, pct=False)}")

    # 3: CLV of real bets
    led = pd.read_csv(STATE / "ledger.csv")
    flags = pd.read_csv(STATE / "bet_flags.csv") if (STATE / "bet_flags.csv").exists() else pd.DataFrame(columns=["bet_id"])
    bets = led[(led.sport == "atp") & ~led.bet_id.isin(flags.bet_id)].merge(
        cp, left_on=["event_id", "pick"], right_on=["event_id", "outcome"])
    bets = bets[bets.minutes_before <= MAX_CLOSE_MINUTES]
    print(f"\nCLV of ATP bets (our price / closing median − 1), closing ≤ {MAX_CLOSE_MINUTES} min before start:")
    for wallet, g in bets.groupby("wallet"):
        print(f"  {wallet:16s} {fmt((g.odds / g.close_odds - 1).to_numpy())}")
    if bets.empty:
        print("  no bets with a usable closing price yet")

    n_ev, n_bets = good.event_id.nunique(), len(bets)
    verdict = "enough data to judge" if n_ev >= MIN_EVENTS and n_bets >= MIN_BETS else \
        f"NOT enough data yet (need {MIN_EVENTS} events and {MIN_BETS} bets; have {n_ev} and {n_bets})"
    print(f"\n{verdict}")


if __name__ == "__main__":
    main()
