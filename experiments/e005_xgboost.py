"""E005: XGBoost on pre-match ATP features. Does boosting beat Elo calibrated per format?

Gradient boosting builds trees one after another. Each new tree is fitted to what the trees
before it still get wrong, and adds a small nudge (on the log-odds scale) to their combined
prediction. Hundreds of small nudges add up to a flexible model.

Protocol (pre-registered in experiments/LOG.md before running):
  fit 2010-2017, pick hyperparameters on 2018-2019, refit 2010-2019, score 2020-2022 once.
  Features are E003's (all known before the match) plus the Elo log-odds and best-of-5.
  The test years (2023+) are NOT touched.

    uv run --group experiments python -W ignore experiments/e005_xgboost.py   -> results/e005_xgboost.json
    (macOS needs the OpenMP runtime once: brew install libomp)
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
import backtest as bt  # noqa: E402
from e003_decision_tree import LABELS, SYMMETRIC, build_features  # noqa: E402
from e004_format_calibration import cluster_ci, fit_slopes, gap, match_ll, wallet_run  # noqa: E402
from strategies import format_calibrated, logit  # noqa: E402

FIT = ("2010-01-01", "2017-12-31")
TUNE = ("2018-01-01", "2019-12-31")
TRAIN = ("2010-01-01", "2019-12-31")
VALID = ("2020-01-01", "2022-12-31")
FEATURES = list(LABELS) + ["elo_logit"]
SYM = SYMMETRIC + ["elo_logit"]
GRID = {"max_depth": [2, 3, 4, 6], "learning_rate": [0.03, 0.1], "min_child_weight": [50, 200]}
OUT = ROOT / "results" / "e005_xgboost.json"


def flipped(x: pd.DataFrame) -> pd.DataFrame:
    f = x.copy()
    f[SYM] = -f[SYM]
    return f


def mirrored(x: pd.DataFrame, y: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    """Every match twice, players swapped, so listing order can't be learned."""
    return pd.concat([x, flipped(x)], ignore_index=True), np.concatenate([y, 1 - y])


def sym_predict(model: XGBClassifier, x: pd.DataFrame) -> np.ndarray:
    """Average P1's chance with (1 - P2's chance) from the swapped row: exactly symmetric."""
    return (model.predict_proba(x)[:, 1] + 1 - model.predict_proba(flipped(x))[:, 1]) / 2


def make(params: dict, n: int = 3000, early: bool = True) -> XGBClassifier:
    return XGBClassifier(n_estimators=n, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                         eval_metric="logloss", early_stopping_rounds=100 if early else None,
                         tree_method="hist", n_jobs=-1, random_state=5, **params)


def main() -> None:
    df = bt.load_atp()
    df["best_of"] = df["Best of"]
    print("building pre-match features (one replay of the full history)...")
    feats = build_features(df)
    feats["elo_logit"] = logit(feats.elo_p.to_numpy())
    feats["tourney"] = df.date.dt.year.astype(str).to_numpy() + " " + df.Tournament.to_numpy()
    for c in ("Player_1", "Player_2", "Winner"):
        feats[c] = df[c].to_numpy()
    y = feats.p1_won.astype(int).to_numpy()
    sel = lambda span: feats.date.between(*span).to_numpy()  # noqa: E731
    fit, tune, train, valid = sel(FIT), sel(TUNE), sel(TRAIN), sel(VALID)

    # ---- 1. hyperparameters: fit 2010-17, early-stop and score on 2018-19
    xf, yf = mirrored(feats.loc[fit, FEATURES], y[fit])
    xt, yt = mirrored(feats.loc[tune, FEATURES], y[tune])
    tried = []
    for depth, lr, mcw in itertools.product(*GRID.values()):
        params = {"max_depth": depth, "learning_rate": lr, "min_child_weight": mcw}
        m = make(params).fit(xf, yf, eval_set=[(xt, yt)], verbose=False)
        ll = match_ll(sym_predict(m, feats.loc[tune, FEATURES]), y[tune]).mean()
        tried.append({**params, "trees": int(m.best_iteration) + 1, "tune_log_loss": float(ll)})
        print(f"  depth {depth} lr {lr:<4} min_child {mcw:<3} -> {m.best_iteration + 1:4d} trees, 2018-19 log loss {ll:.4f}")
    best = min(tried, key=lambda r: r["tune_log_loss"])
    params = {k: best[k] for k in GRID}
    print(f"chosen ({len(tried)} variants tried): {params}, {best['trees']} trees")

    # ---- 2. refit on all train years, score validation once
    xtr, ytr = mirrored(feats.loc[train, FEATURES], y[train])
    model = make(params, n=best["trees"], early=False).fit(xtr, ytr, verbose=False)
    v = feats[valid].reset_index(drop=True)
    yv, bo5 = y[valid], v.best_of_5.to_numpy().astype(bool)
    slopes = fit_slopes(feats.elo_p[train].to_numpy(), feats.best_of_5[train].to_numpy().astype(bool), y[train],
                        per_format=True)
    probs = {"raw Elo (elo_v0)": v.elo_p.to_numpy(),
             "calibrated Elo": format_calibrated(v.elo_p.to_numpy(), np.where(bo5, 5, 3), *slopes),
             "XGBoost": sym_predict(model, v[FEATURES])}
    has_odds = ((v.odd_1 > 1) & (v.odd_2 > 1)).to_numpy()
    book = np.full(len(v), np.nan)
    book[has_odds] = bt.implied_probs(v.loc[has_odds, ["odd_1", "odd_2"]].to_numpy(float))[:, 0]

    print(f"\nValidation 2020-2022: {len(v):,} matches ({has_odds.sum():,} with odds)")
    print(f"  {'model':18s} {'log loss':>9s} {'w/ odds':>8s} {'accuracy':>9s} {'gap Bo3':>8s} {'gap Bo5':>8s}")
    scores = {}
    for k, p in {**probs, "bookmaker": book}.items():
        o = has_odds if k == "bookmaker" else np.ones(len(v), bool)
        scores[k] = {"log_loss": float(match_ll(p[o], yv[o]).mean()),
                     "log_loss_with_odds": float(match_ll(p[has_odds], yv[has_odds]).mean()),
                     "accuracy": float(((p[o] > 0.5) == (yv[o] == 1)).mean()),
                     "gap_bo3": gap(p[o & ~bo5], yv[o & ~bo5]), "gap_bo5": gap(p[o & bo5], yv[o & bo5])}
        s = scores[k]
        print(f"  {k:18s} {s['log_loss']:9.4f} {s['log_loss_with_odds']:8.4f} {s['accuracy']:9.1%} "
              f"{s['gap_bo3']:+7.1f}  {s['gap_bo5']:+7.1f}")

    d = match_ll(probs["calibrated Elo"], yv) - match_ll(probs["XGBoost"], yv)
    ci = cluster_ci(d, v.tourney.to_numpy())
    yearly = pd.DataFrame({"year": v.date.dt.year, "d": d}).groupby("year").d.mean()
    print(f"\nXGBoost improvement per match vs calibrated Elo: {d.mean():+.5f}  95% CI [{ci[0]:+.5f}, {ci[1]:+.5f}]")
    print("  by year: " + ", ".join(f"{yr} {x:+.5f}" for yr, x in yearly.items()))

    odds = v[has_odds].rename(columns={"odd_1": "Odd_1", "odd_2": "Odd_2"}).reset_index(drop=True)
    wallets = {k: wallet_run(odds, p[has_odds]) for k, p in probs.items()}
    print("\nWallet on 2020-2022 ($1,000, live rules: quarter-Kelly, 5% cap, +5% edge):")
    for k, s in wallets.items():
        print(f"  {k:18s} {s['bets']:5d} bets  ROI {s['roi']:+.1%}  final ${s['final_bankroll']:,.0f}  "
              f"max drawdown {s['max_drawdown']:.0%}")

    rule1 = ci[0] > 0
    rule2 = int((yearly > 0).sum()) >= 2
    rule3 = wallets["XGBoost"]["roi"] >= wallets["raw Elo (elo_v0)"]["roi"]
    passed = rule1 and rule2 and rule3
    print(f"\nPass rules: (1) CI excludes 0: {rule1}  (2) {int((yearly > 0).sum())}/3 years: {rule2}  "
          f"(3) ROI >= elo_v0: {rule3}  ->  {'PASS' if passed else 'FAIL'}")

    gain = model.get_booster().get_score(importance_type="gain")
    total = sum(gain.values())
    importance = {f: round(gain.get(f, 0) / total, 4) for f in FEATURES}
    print("\nFeature importance (share of total gain):")
    for f, g in sorted(importance.items(), key=lambda kv: -kv[1]):
        print(f"  {f:18s} {g:6.1%}")

    OUT.write_text(json.dumps({"variants_tried": len(tried), "grid": tried, "chosen": {**params, "trees": best["trees"]},
                               "calibration_slopes": slopes, "validation": scores, "improvement_vs_calibrated": float(d.mean()),
                               "ci": ci, "by_year": yearly.to_dict(), "wallets": wallets, "importance": importance,
                               "rules": {"ci": rule1, "years": rule2, "roi": rule3}, "passed": passed},
                              indent=2, default=float))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
