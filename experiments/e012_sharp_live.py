"""E012: live paper test of sharp_v1 (E011's idea on the bookmakers we log every morning).

sharp_v1 bets the best real bookmaker price whenever it beats Pinnacle's price with the margin
removed by >= 2%. Judged on closing line value against Pinnacle's no-vig CLOSING price:

    clv_fair = our odds x Pinnacle's closing fair probability - 1

Example: we took 3.14; at the close Pinnacle was 2.90 / 1.42 -> fair p 0.329 -> 3.14 x 0.329 - 1 = +3.3%.
Closing prices: ATP from our odds snapshots (last one <= 3h before the start, Pinnacle quoted on
both sides); EPL from football-data's Pinnacle closing columns once the file has the match.

Pre-registered decision (experiments/LOG.md): judge after 150 settled sharp_v1 bets with a fair CLV.
  keep running (and consider staking it seriously on paper) if mean clv_fair > 0 with a 95% CI excluding 0;
  stop if the CI is entirely below 0; otherwise extend to 300 bets once, then decide on the point estimate.
Profit is reported but not the judge: at ~1-3 bets a day it is noise for many months.

    uv run python -W ignore experiments/e012_sharp_live.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import records  # noqa: E402

STATE = ROOT / "state"
STRATEGY, TARGET, EXTENDED = "sharp_v1", 150, 300
MAX_CLOSE_MINUTES = 180
rng = np.random.default_rng(12)


def ci(x: np.ndarray, reps: int = 4000) -> tuple[float, float]:
    if len(x) < 2:
        return (np.nan, np.nan)
    m = rng.choice(x, (reps, len(x))).mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def atp_pinnacle_close() -> dict[tuple[str, str], float]:
    """(event_id, outcome) -> Pinnacle's no-vig closing probability, from our snapshots."""
    path = STATE / "odds_snapshots.csv"
    if not path.exists():
        return {}
    s = pd.read_csv(path)
    s = s[(s.sport == "atp") & s.pinnacle_odds.notna()]
    s["mins"] = (pd.to_datetime(s.commence_time, utc=True) - pd.to_datetime(s["at"], utc=True)).dt.total_seconds() / 60
    s = s[(s.mins >= 0) & (s.mins <= MAX_CLOSE_MINUTES)]
    out = {}
    for eid, g in s.groupby("event_id"):
        last = g[g["at"] == g["at"].max()]
        if len(last) != 2:
            continue
        imp = 1 / last.pinnacle_odds.to_numpy(float)
        for o, p in zip(last.outcome, imp / imp.sum()):
            out[(eid, o)] = float(p)
    return out


def epl_pinnacle_close(bets: pd.DataFrame) -> dict[tuple[str, str], float]:
    h, out = records.History(), {}
    for b in bets[bets.sport == "epl"].itertuples():
        found = h.lookup("epl", b.match, b.commence_time)
        if not found or found.get("close_source") != "pinnacle_close":
            continue
        close = found["close"]  # {home, Draw, away}: Pinnacle closing odds
        tot = sum(1 / v for v in close.values())
        if b.pick in close:
            out[(b.event_id, b.pick)] = (1 / close[b.pick]) / tot
    return out


def main() -> None:
    led = pd.read_csv(STATE / "ledger.csv")
    flags = pd.read_csv(STATE / "bet_flags.csv") if (STATE / "bet_flags.csv").exists() else pd.DataFrame(columns=["bet_id"])
    bets = led[(led.strategy == STRATEGY) & ~led.bet_id.isin(flags.bet_id)].copy()
    if bets.empty:
        print(f"No {STRATEGY} bets yet (first bets from the next morning run).")
        return
    close = {**atp_pinnacle_close(), **epl_pinnacle_close(bets)}
    bets["close_p"] = [close.get((e, p)) for e, p in zip(bets.event_id, bets.pick)]
    bets["clv_fair"] = bets.odds * bets.close_p - 1
    settled = bets[bets.status.isin(["won", "lost"])]
    judged = settled.dropna(subset=["clv_fair"])

    print(f"{STRATEGY}: {len(bets)} bets placed, {len(settled)} settled, {len(judged)} with a Pinnacle close")
    if len(judged):
        lo, hi = ci(judged.clv_fair.to_numpy())
        print(f"  CLV vs Pinnacle fair close: {judged.clv_fair.mean():+.2%}  95% CI [{lo:+.2%}, {hi:+.2%}]  "
              f"beat it {np.mean(judged.clv_fair > 0):.0%}")
        print(f"  claimed edge at bet time:   {(bets.model_p * bets.odds - 1).mean():+.2%}")
        print("  by sport:", judged.groupby("sport").clv_fair.agg(["size", "mean"]).round(4).to_dict("index"))
        print("  by book: ", judged.groupby("exec_book").clv_fair.agg(["size", "mean"]).round(4)
              .sort_values("size", ascending=False).head(8).to_dict("index"))
    if len(settled):
        print(f"  profit: {settled.pnl.sum():+.2f} on {settled.stake.sum():.2f} staked "
              f"(ROI {settled.pnl.sum() / settled.stake.sum():+.1%}); wins {(settled.status == 'won').sum()} "
              f"vs {settled.model_p.sum():.1f} expected")

    n = len(judged)
    if n < TARGET:
        print(f"\nNot enough data: {n}/{TARGET} settled bets with a fair close. No conclusion yet.")
        return
    lo, hi = ci(judged.clv_fair.to_numpy())
    if lo > 0:
        verdict = "KEEP: beats Pinnacle's close (CI above 0)"
    elif hi < 0:
        verdict = "STOP: worse than Pinnacle's close (CI below 0)"
    elif n < EXTENDED:
        verdict = f"UNDECIDED: extend to {EXTENDED} bets"
    else:
        verdict = "KEEP (weak)" if judged.clv_fair.mean() > 0 else "STOP"
    print(f"\nVerdict at {n} bets: {verdict}")


if __name__ == "__main__":
    main()
