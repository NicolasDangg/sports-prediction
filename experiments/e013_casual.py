"""E013: the casual "safe bets" bettor, replayed on ATP history (Kaggle odds, 2010-now).

Question from the owner: what if someone only bets now and then, on outcomes very likely to win,
either one big bet or many small ones, to "make some money"?
Not a strategy we expect to profit: a realistic comparison wallet. This script shows what history says.

  1. Backing the favourite at the listed price, by how likely it was (margin removed): win rate and ROI.
  2. Replay of the live rule: once a week (first match day of the week), 25% of the wallet on
     favourites with an 80%+ chance: one big bet (the likeliest) or split over up to 20.

    uv run python -W ignore experiments/e013_casual.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
POT, MIN_P, START = 0.25, 0.80, 5000.0


def load() -> pd.DataFrame:
    d = pd.read_csv(ROOT / "data/tennis/atp_tennis.csv")
    d["date"] = pd.to_datetime(d.Date)
    d = d[(d.Odd_1 > 1) & (d.Odd_2 > 1) & (d.date >= "2010-01-01")].copy()
    fav1 = d.Odd_1 < d.Odd_2
    d["fo"], d["uo"] = np.where(fav1, d.Odd_1, d.Odd_2), np.where(fav1, d.Odd_2, d.Odd_1)
    d["fwin"] = np.where(fav1, d.Winner == d.Player_1, d.Winner == d.Player_2)
    d["p"] = (1 / d.fo) / (1 / d.fo + 1 / d.uo)
    d["week"] = d.date.dt.to_period("W")
    return d


def replay(d: pd.DataFrame, max_picks: int) -> dict:
    bank, path, bets, lost = START, [], 0, 0
    for _, g in d[d.p >= MIN_P].groupby("week"):
        day = g[g.date == g.date.min()].nlargest(max_picks, "p")
        stake = bank * POT / len(day)
        bank += float(np.where(day.fwin, stake * (day.fo - 1), -stake).sum())
        bets, lost, path = bets + len(day), lost + int((~day.fwin).sum()), path + [bank]
    p = np.array(path)
    return {"sessions": len(p), "bets": bets, "lost": lost, "won_pct": 1 - lost / bets, "final": round(bank, 2),
            "worst_drop": float(1 - (p / np.maximum.accumulate(p)).min()),
            "peak": round(float(p.max()), 2)}


def main() -> None:
    d = load()
    bands = []
    print("Backing the favourite, flat $1 at the listed price (ATP 2010-now)")
    for lo, hi in [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.85), (0.85, 0.9), (0.9, 1.0)]:
        g = d[(d.p >= lo) & (d.p < hi)]
        roi = float(np.where(g.fwin, g.fo - 1, -1).mean())
        bands.append({"band": f"{lo:.0%}-{hi:.0%}", "bets": len(g), "won": float(g.fwin.mean()),
                      "avg_odds": float(g.fo.mean()), "roi": roi})
        print(f"  {lo:.0%}-{hi:.0%}: {len(g):6d} bets  won {g.fwin.mean():.1%}  avg odds {g.fo.mean():.2f}  ROI {roi:+.2%}")
    out = {"bands": bands}
    for name, k in (("casual_big_v1", 1), ("casual_many_v1", 20)):
        out[name] = r = replay(d, k)
        print(f"{name}: {r['sessions']} weekly sessions, {r['bets']} bets, won {r['won_pct']:.1%}, "
              f"${START:,.0f} -> ${r['final']:,.0f} (peak ${r['peak']:,.0f}, worst drop {r['worst_drop']:.0%})")
    (ROOT / "results/e013_casual.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()


# ---- E014: smart casual vs casual on EPL (football-data has Pinnacle AND the other books' prices)
def epl_replay() -> dict:
    """Same weekly session on EPL 2012/13-now: casual = typical price (market average), any 80%+
    outcome; smart = only outcomes whose best mainstream price beats Pinnacle's fair price."""
    import sys
    sys.path.insert(0, str(ROOT / "experiments"))
    sys.path.insert(0, str(ROOT))
    from e011_sharp_vs_soft import OUT, prepare  # noqa: E402

    df = prepare()
    avg = {"H": ("AvgH", "BbAvH"), "D": ("AvgD", "BbAvD"), "A": ("AvgA", "BbAvA")}
    rows = []
    for o in OUT:
        typ = df[avg[o][0]].astype(float) if avg[o][0] in df else np.nan
        if avg[o][1] in df:
            typ = typ.fillna(df[avg[o][1]].astype(float)) if isinstance(typ, pd.Series) else df[avg[o][1]].astype(float)
        rows.append(pd.DataFrame({"date": df.date, "event": df.index, "p": df[f"fair_{o}"], "typical": typ,
                                  "best": df[f"soft_{o}"], "won": df.result == o}))
    x = pd.concat(rows)
    x = x[x.p >= MIN_P]
    x["week"] = x.date.dt.to_period("W")
    out = {}
    for name, pick, price in (("casual_big_v1", 1, "typical"), ("casual_many_v1", 20, "typical"),
                              ("smart_casual_v1", 20, "best")):
        y = x[x.best * x.p > 1] if name.startswith("smart") else x
        bank, n, won, peak = START, 0, 0, START
        for _, g in y.groupby("week"):
            g = g.nlargest(pick, "p")
            stake = bank * POT / len(g)
            bank += float(np.where(g.won, stake * (g[price] - 1), -stake).sum())
            n, won, peak = n + len(g), won + int(g.won.sum()), max(peak, bank)
        out[name] = {"sessions": int(y.week.nunique()), "bets": n, "won_pct": won / n if n else None,
                     "final": round(bank, 2), "peak": round(peak, 2)}
        print(f"EPL {name}: {out[name]['sessions']} sessions, {n} bets, won {won / max(n, 1):.1%}, "
              f"${START:,.0f} -> ${bank:,.0f} (peak ${peak:,.0f})")
    return out


if __name__ == "__main__" and "--epl" in __import__("sys").argv:
    r = json.loads((ROOT / "results/e013_casual.json").read_text())
    r["epl"] = epl_replay()
    (ROOT / "results/e013_casual.json").write_text(json.dumps(r, indent=2))
