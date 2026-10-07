"""E004 (experiment A): is tennis Elo overconfident only in best-of-3, and does a per-format
calibration fix it?

Calibration = a small correction on top of Elo. Elo says 70%; history says players Elo rates
at 70% in best-of-3 actually win ~64%, so the corrected model says 64%. We fit it as
p' = sigmoid(slope × logit(p)) with one slope per format (strategies.format_calibrated).

Protocol (pre-registered in experiments/LOG.md before running):
  walk-forward: for each year Y in 2017-2022, fit on 2010..Y-1, score Y (train/validation years only).
  pass rules: (1) 95% CI of log-loss improvement vs raw Elo excludes 0 (tournament bootstrap),
              (2) better in >= 4 of 6 years, (3) best-of-3 gap < 2 pts, best-of-5 gap no worse.
  --test: the ONE sealed look at 2023+ with the curve fitted on 2010-2022 (counts against the budget).

    uv run python -W ignore experiments/e004_format_calibration.py          -> walk-forward only
    uv run python -W ignore experiments/e004_format_calibration.py --test   -> + the test-set look
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest as bt  # noqa: E402
from strategies import format_calibrated, logit  # noqa: E402
from wallet import Wallet  # noqa: E402

ATP_PARAMS = dict(k_scale=200, surface_weight=0.5)  # elo_v0's settings
FIT_FROM = "2010-01-01"
YEARS = range(2017, 2023)
TEST_START = "2023-01-01"
LIVE_MIN_EDGE = 0.05
OUT = ROOT / "results" / "e004_format_calibration.json"
rng = np.random.default_rng(4)


def fit_slopes(p: np.ndarray, bo5: np.ndarray, y: np.ndarray, per_format: bool) -> tuple[float, float]:
    """Logistic regression on logit(p) with no intercept; one slope, or one per format."""
    z = logit(p)
    x = np.column_stack([z * ~bo5, z * bo5]) if per_format else z.reshape(-1, 1)
    c = LogisticRegression(fit_intercept=False, C=1e6).fit(x, y).coef_[0]
    return (float(c[0]), float(c[1])) if per_format else (float(c[0]), float(c[0]))


def match_ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(np.where(y == 1, p, 1 - p))


def gap(p: np.ndarray, y: np.ndarray) -> float:
    """Favourite's average predicted chance minus how often favourites actually won (pts)."""
    fav_p = np.maximum(p, 1 - p)
    fav_won = np.where(p >= 0.5, y, 1 - y)
    return 100 * (fav_p.mean() - fav_won.mean())


def cluster_ci(diff: np.ndarray, groups: np.ndarray, reps: int = 2000) -> tuple[float, float]:
    """95% interval for the mean improvement, resampling whole tournaments (not single matches)."""
    codes, idx = np.unique(groups, return_inverse=True)
    sums, counts = np.bincount(idx, diff), np.bincount(idx)
    means = []
    for _ in range(reps):
        pick = rng.integers(0, len(codes), len(codes))
        means.append(sums[pick].sum() / counts[pick].sum())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wallet_run(t: pd.DataFrame, p: np.ndarray) -> dict:
    """Live betting rules (quarter-Kelly, 5% cap, +5% min edge) on matches with odds."""
    w = Wallet(min_edge=LIVE_MIN_EDGE)
    for i, g in enumerate(t.itertuples()):
        bet = w.consider([(g.Player_1, p[i], g.Odd_1), (g.Player_2, 1 - p[i], g.Odd_2)])
        if bet:
            label, prob, odds, stake = bet
            w.place_and_settle({}, label, prob, odds, stake, won=(g.Winner == label))
    s = w.summary()
    return {k: s[k] for k in ("bets", "win_rate", "roi", "final_bankroll", "max_drawdown")}


def score(name: str, t: pd.DataFrame, probs: dict[str, np.ndarray], y: np.ndarray, bo5: np.ndarray) -> dict:
    out = {}
    print(f"\n{name}: {len(t):,} matches ({bo5.sum():,} best-of-5)")
    print(f"  {'model':16s} {'log loss':>9s} {'gap Bo3':>8s} {'gap Bo5':>8s}")
    for k, p in probs.items():
        out[k] = {"log_loss": float(match_ll(p, y).mean()),
                  "gap_bo3": gap(p[~bo5], y[~bo5]), "gap_bo5": gap(p[bo5], y[bo5])}
        print(f"  {k:16s} {out[k]['log_loss']:9.4f} {out[k]['gap_bo3']:+7.1f}  {out[k]['gap_bo5']:+7.1f}")
    return out


def main(test: bool) -> None:
    df = bt.load_atp()
    p_raw, _ = bt.tennis_probs(df, **ATP_PARAMS)
    df["p_raw"], df["bo5"], df["y"] = p_raw, (df["Best of"] == 5).to_numpy(), df.p1_won.astype(int)
    df["tourney"] = df.date.dt.year.astype(str) + " " + df.Tournament

    # ---- walk-forward on train/validation years
    rows, oos = [], []
    for year in YEARS:
        fit = df[(df.date >= FIT_FROM) & (df.date.dt.year < year)]
        sc = df[df.date.dt.year == year].copy()
        single = fit_slopes(fit.p_raw.to_numpy(), fit.bo5.to_numpy(), fit.y.to_numpy(), per_format=False)
        fmt = fit_slopes(fit.p_raw.to_numpy(), fit.bo5.to_numpy(), fit.y.to_numpy(), per_format=True)
        sc["p_single"] = format_calibrated(sc.p_raw, np.where(sc.bo5, 5, 3), *single)
        sc["p_fmt"] = format_calibrated(sc.p_raw, np.where(sc.bo5, 5, 3), *fmt)
        ll = {k: match_ll(sc[k].to_numpy(), sc.y.to_numpy()).mean() for k in ("p_raw", "p_single", "p_fmt")}
        rows.append({"year": year, "matches": len(sc), "slope_bo3": fmt[0], "slope_bo5": fmt[1],
                     "slope_single": single[0], **{f"ll_{k[2:]}": v for k, v in ll.items()},
                     "fmt_beats_raw": bool(ll["p_fmt"] < ll["p_raw"])})
        oos.append(sc)
    years = pd.DataFrame(rows)
    print("Walk-forward (fit 2010..Y-1, score Y):")
    print(years.round(4).to_string(index=False))

    v = pd.concat(oos, ignore_index=True)
    y, bo5 = v.y.to_numpy(), v.bo5.to_numpy()
    probs = {"raw Elo": v.p_raw.to_numpy(), "single curve": v.p_single.to_numpy(), "per-format": v.p_fmt.to_numpy()}
    wf = score("Walk-forward 2017-2022 pooled", v, probs, y, bo5)

    d_raw = match_ll(v.p_raw.to_numpy(), y) - match_ll(v.p_fmt.to_numpy(), y)
    d_single = match_ll(v.p_single.to_numpy(), y) - match_ll(v.p_fmt.to_numpy(), y)
    ci_raw, ci_single = cluster_ci(d_raw, v.tourney.to_numpy()), cluster_ci(d_single, v.tourney.to_numpy())
    print(f"\nImprovement per match vs raw Elo     : {d_raw.mean():+.5f}  95% CI [{ci_raw[0]:+.5f}, {ci_raw[1]:+.5f}]")
    print(f"Improvement per match vs single curve: {d_single.mean():+.5f}  95% CI [{ci_single[0]:+.5f}, {ci_single[1]:+.5f}]")

    rule1 = ci_raw[0] > 0
    rule2 = int(years.fmt_beats_raw.sum()) >= 4
    rule3 = abs(wf["per-format"]["gap_bo3"]) < 2 and abs(wf["per-format"]["gap_bo5"]) <= abs(wf["raw Elo"]["gap_bo5"])
    passed = rule1 and rule2 and rule3
    print(f"\nPass rules: (1) CI excludes 0: {rule1}  (2) {int(years.fmt_beats_raw.sum())}/6 years: {rule2}  "
          f"(3) gaps: {rule3}  ->  {'PASS' if passed else 'FAIL'}")

    odds = v[(v.Odd_1 > 1) & (v.Odd_2 > 1)].reset_index(drop=True)
    wallets = {k: wallet_run(odds, odds[c].to_numpy()) for k, c in
               (("raw Elo (elo_v0)", "p_raw"), ("per-format", "p_fmt"))}
    print("\nWallet on walk-forward years ($1,000, live rules):")
    for k, s in wallets.items():
        print(f"  {k:18s} {s['bets']:5d} bets  ROI {s['roi']:+.1%}  final ${s['final_bankroll']:,.0f}  "
              f"max drawdown {s['max_drawdown']:.0%}")

    final = fit_slopes(*(df[(df.date >= FIT_FROM) & (df.date < TEST_START)][c].to_numpy() for c in ("p_raw", "bo5", "y")),
                       per_format=True)
    print(f"\nFinal curve (fit 2010-2022): slope Bo3 {final[0]:.4f}, slope Bo5 {final[1]:.4f}")
    result = {"walk_forward": {"years": rows, "pooled": wf, "improvement_vs_raw": float(d_raw.mean()),
                               "ci_vs_raw": ci_raw, "improvement_vs_single": float(d_single.mean()),
                               "ci_vs_single": ci_single, "wallets": wallets,
                               "rules": {"ci": rule1, "years": rule2, "gaps": rule3}, "passed": passed},
              "variants_tried": 1, "final_slopes": {"bo3": final[0], "bo5": final[1]}}

    if test:
        t = df[(df.date >= TEST_START) & (df.Odd_1 > 1) & (df.Odd_2 > 1)].reset_index(drop=True)
        ty, tbo5 = t.y.to_numpy(), t.bo5.to_numpy()
        p_fmt = format_calibrated(t.p_raw, np.where(tbo5, 5, 3), *final)
        book = bt.implied_probs(t[["Odd_1", "Odd_2"]].to_numpy())[:, 0]
        ts = score(f"TEST {TEST_START[:4]}+ (one look)", t, {"raw Elo": t.p_raw.to_numpy(), "per-format": p_fmt,
                                                            "bookmaker": book}, ty, tbo5)
        d = match_ll(t.p_raw.to_numpy(), ty) - match_ll(p_fmt, ty)
        ci = cluster_ci(d, t.tourney.to_numpy())
        print(f"Improvement per match vs raw Elo: {d.mean():+.5f}  95% CI [{ci[0]:+.5f}, {ci[1]:+.5f}]")
        tw = {"raw Elo (elo_v0)": wallet_run(t, t.p_raw.to_numpy()), "per-format": wallet_run(t, p_fmt)}
        print("Wallet on test years ($1,000, live rules):")
        for k, s in tw.items():
            print(f"  {k:18s} {s['bets']:5d} bets  ROI {s['roi']:+.1%}  final ${s['final_bankroll']:,.0f}  "
                  f"max drawdown {s['max_drawdown']:.0%}")
        result["test"] = {"scores": ts, "improvement_vs_raw": float(d.mean()), "ci": ci, "wallets": tw}

    OUT.write_text(json.dumps(result, indent=2, default=float))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(test="--test" in sys.argv)
