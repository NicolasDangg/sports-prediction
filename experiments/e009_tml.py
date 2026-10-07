"""E009: tennis on TennisMyLife data. (a) a better Elo, (b) an E006-style forecaster that can run daily.

(a) Elo on TML player IDs. Variants, chosen on train years 2010-2019 only:
    levels feeding the ratings × shrink toward 1500 after a long break × k_scale.
(b) Gradient boosting (scikit-learn's HistGradientBoosting: same family as E005/E006's XGBoost,
    no extra runtime dependency for the morning job) on Elo + ranking + form + rest + format +
    decayed serve/return rates. Fit 2010-17, choose on 2018-19, refit 2010-19, score 2020-22 once.

Both are scored against elo_v0 on the same ATP main-tour rows of our odds data. Pass rules are
pre-registered in experiments/LOG.md. `--test` = the single sealed look at 2023+ for a variant
that passed (counts against the test-set budget).

    uv run python fetch_data.py tml                                   (once)
    uv run python -W ignore experiments/e009_tml.py [--test]          -> results/e009_tml.json
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]
import backtest as bt  # noqa: E402
import tml  # noqa: E402
from e004_format_calibration import cluster_ci, gap, match_ll, wallet_run  # noqa: E402

TRAIN, VALID, TEST_START = ("2010-01-01", "2019-12-31"), ("2020-01-01", "2022-12-31"), "2023-01-01"
FIT, TUNE = ("2010-01-01", "2017-12-31"), ("2018-01-01", "2019-12-31")
LEVELS = {"main": ("main",), "main+chall": ("main", "chall"), "all": ("main", "chall", "qual")}
HALF_LIVES = {"none": None, "180d": 180.0, "365d": 365.0}
K_SCALES = [200.0, 250.0]
GRID = {"max_depth": [2, 3, 4, 6], "learning_rate": [0.03, 0.1], "min_samples_leaf": [50, 200]}
OUT = ROOT / "results" / "e009_tml.json"

DIFFS, FEATURES = tml.DIFFS, tml.FEATURES
features, flipped, mirrored, sym_proba = tml.features, tml.flipped, tml.mirrored, tml.sym_proba


# ------------------------------------------------------------------ main


def main(test: bool) -> None:
    print("loading TML + odds data and linking them...")
    s = tml.load()
    df = bt.load_atp()
    link = tml.link_kaggle(df, s)
    df = df.loc[link.index].sort_index().copy()  # chronological: the wallet compounds bet by bet
    df["s_idx"] = link.loc[df.index]
    df["tourney"] = df.date.dt.year.astype(str) + " " + df.Tournament
    df["y"] = df.p1_won.astype(int).to_numpy()
    p_v0_all, _ = bt.tennis_probs(bt.load_atp(), k_scale=200, surface_weight=0.5)
    df["p_v0"] = p_v0_all[df.index]
    print(f"  {len(s):,} TML matches ({s.level.value_counts().to_dict()}); {len(df):,} odds-data rows linked "
          f"({len(df) / len(bt.load_atp()):.1%} of the odds data)")

    sel = lambda span: df.date.between(*span).to_numpy()  # noqa: E731
    tr, va = sel(TRAIN), sel(VALID)
    p1 = lambda p_w: np.where(df.p1_won, p_w.loc[df.s_idx].to_numpy(), 1 - p_w.loc[df.s_idx].to_numpy())  # noqa: E731

    # ---- (a) Elo variants, chosen on train years
    print("\n(a) Elo variants (log loss on 2010-2019 linked rows; elo_v0 "
          f"{match_ll(df.p_v0[tr].to_numpy(), df.y[tr].to_numpy()).mean():.4f}):")
    tried = []
    for (lv, levels), (hl, half), k in itertools.product(LEVELS.items(), HALF_LIVES.items(), K_SCALES):
        pre, _ = tml.replay(s, tml.EloConfig(levels=levels, half_life=half, k_scale=k), with_features=False)
        p = p1(pre.p_w)
        ll = float(match_ll(p[tr], df.y[tr].to_numpy()).mean())
        tried.append({"levels": lv, "half_life": hl, "k_scale": k, "train_log_loss": ll})
        print(f"  levels {lv:10s} shrink {hl:5s} k {k:.0f}: {ll:.4f}")
    best = min(tried, key=lambda r: r["train_log_loss"])
    cfg = tml.EloConfig(levels=LEVELS[best["levels"]], half_life=HALF_LIVES[best["half_life"]], k_scale=best["k_scale"])
    print(f"chosen ({len(tried)} variants): {best}")

    pre, _ = tml.replay(s, cfg, with_features=True)
    df["p_a"] = p1(pre.p_w)

    # ---- (b) forecaster: train on TML main-tour rows (not just linked ones), choose on 2018-19
    feats = features(s, pre)
    main_rows = (s.level == "main") & s.completed
    when = s.tourney_date
    xf, yf = mirrored(feats[main_rows & when.between(*FIT)][FEATURES])
    xt = feats[main_rows & when.between(*TUNE)][FEATURES]
    print(f"\n(b) forecaster: {int((main_rows & when.between(*FIT)).sum()):,} fit matches, "
          f"{len(xt):,} tuning matches (2018-19)")
    grid = []
    for depth, lr, leaf in itertools.product(*GRID.values()):
        m = HistGradientBoostingClassifier(max_depth=depth, learning_rate=lr, min_samples_leaf=leaf, max_iter=1500,
                                           early_stopping=False, random_state=9).fit(xf, yf)
        a, b = list(m.staged_predict_proba(xt)), list(m.staged_predict_proba(flipped(xt)))
        lls = [float(match_ll((pa[:, 1] + 1 - pb[:, 1]) / 2, np.ones(len(xt))).mean()) for pa, pb in zip(a, b)]
        it = int(np.argmin(lls)) + 1
        grid.append({"max_depth": depth, "learning_rate": lr, "min_samples_leaf": leaf, "trees": it, "tune_log_loss": lls[it - 1]})
        print(f"  depth {depth} lr {lr:<4} leaf {leaf:<3} -> {it:4d} trees, 2018-19 log loss {lls[it - 1]:.4f}")
    gb = min(grid, key=lambda r: r["tune_log_loss"])
    print(f"chosen ({len(grid)} variants): {gb}")
    xtr, ytr = mirrored(feats[main_rows & when.between(*TRAIN)][FEATURES])
    model = HistGradientBoostingClassifier(max_depth=gb["max_depth"], learning_rate=gb["learning_rate"],
                                           min_samples_leaf=gb["min_samples_leaf"], max_iter=gb["trees"],
                                           early_stopping=False, random_state=9).fit(xtr, ytr)
    xk = feats.loc[df.s_idx][FEATURES].set_axis(df.index)
    xk = pd.concat([xk[df.p1_won], flipped(xk[~df.p1_won])]).loc[df.index]  # orient to the odds data's P1
    df["p_b"] = sym_proba(model, xk)

    # ---- validation 2020-22, once
    v = df[va]
    yv, bo5 = v.y.to_numpy(), (v["Best of"] == 5).to_numpy()
    probs = {"elo_v0": v.p_v0.to_numpy(), "(a) TML Elo": v.p_a.to_numpy(), "(b) forecaster": v.p_b.to_numpy()}
    has = ((v.Odd_1 > 1) & (v.Odd_2 > 1)).to_numpy()
    book = np.full(len(v), np.nan)
    book[has] = bt.implied_probs(v.loc[has, ["Odd_1", "Odd_2"]].to_numpy(float))[:, 0]
    print(f"\nValidation 2020-2022: {len(v):,} linked matches")
    print(f"  {'model':16s} {'log loss':>9s} {'accuracy':>9s} {'gap Bo3':>8s} {'gap Bo5':>8s}")
    scores = {}
    for k, p in {**probs, "bookmaker": book}.items():
        o = has if k == "bookmaker" else np.ones(len(v), bool)
        scores[k] = {"log_loss": float(match_ll(p[o], yv[o]).mean()), "accuracy": float(((p[o] > .5) == (yv[o] == 1)).mean()),
                     "gap_bo3": gap(p[o & ~bo5], yv[o & ~bo5]), "gap_bo5": gap(p[o & bo5], yv[o & bo5])}
        sc = scores[k]
        print(f"  {k:16s} {sc['log_loss']:9.4f} {sc['accuracy']:9.1%} {sc['gap_bo3']:+7.1f}  {sc['gap_bo5']:+7.1f}")

    def compare(base: str, new: str) -> dict:
        d = match_ll(probs[base], yv) - match_ll(probs[new], yv)
        ci = cluster_ci(d, v.tourney.to_numpy())
        by = pd.Series(d).groupby(v.date.dt.year.to_numpy()).mean()
        print(f"  {new} vs {base}: {d.mean():+.5f}/match, 95% CI [{ci[0]:+.5f}, {ci[1]:+.5f}]; "
              f"by year {', '.join(f'{y} {x:+.4f}' for y, x in by.items())}")
        return {"improvement": float(d.mean()), "ci": ci, "by_year": {int(k): float(x) for k, x in by.items()},
                "years_better": int((by > 0).sum())}

    print("\nImprovements (positive = better):")
    a_vs_v0, b_vs_a, b_vs_v0 = compare("elo_v0", "(a) TML Elo"), compare("(a) TML Elo", "(b) forecaster"), compare("elo_v0", "(b) forecaster")

    odds = v[has].reset_index(drop=True)
    wallets = {k: wallet_run(odds, p[has]) for k, p in probs.items()}
    print("\nWallet on 2020-2022 ($1,000, live rules):")
    for k, w_ in wallets.items():
        print(f"  {k:16s} {w_['bets']:5d} bets  ROI {w_['roi']:+.1%}  final ${w_['final_bankroll']:,.0f}  "
              f"max drawdown {w_['max_drawdown']:.0%}")

    rules_a = {"ci": a_vs_v0["ci"][0] > 0, "years": a_vs_v0["years_better"] >= 2,
               "roi": wallets["(a) TML Elo"]["roi"] >= wallets["elo_v0"]["roi"]}
    show_b = b_vs_a["ci"][0] > 0
    rules_b = {"ci": b_vs_v0["ci"][0] > 0, "years": b_vs_v0["years_better"] >= 2,
               "roi": wallets["(b) forecaster"]["roi"] >= wallets["elo_v0"]["roi"]}
    print(f"\n(a) betting rules: {rules_a} -> {'PASS' if all(rules_a.values()) else 'FAIL'}")
    print(f"(b) dashboard forecast rule (beats (a), CI excludes 0): {'PASS' if show_b else 'FAIL'}; "
          f"betting rules: {rules_b} -> {'PASS' if all(rules_b.values()) else 'FAIL'}")

    result = {"linked_rows": len(df), "elo_variants": tried, "elo_chosen": best, "forecaster_grid": grid,
              "forecaster_chosen": gb, "validation": scores, "a_vs_v0": a_vs_v0, "b_vs_a": b_vs_a, "b_vs_v0": b_vs_v0,
              "wallets": wallets, "rules_a": rules_a, "show_b": show_b, "rules_b": rules_b,
              "features": FEATURES}

    if test:
        candidates = [k for k, r in (("(a) TML Elo", rules_a), ("(b) forecaster", rules_b)) if all(r.values())]
        if not candidates:
            print("\n--test: nothing passed its rules, so there is nothing to look at. Test years untouched.")
        else:
            # (b) on test years needs a model refitted on 2010-2022, frozen before looking.
            t = df[df.date >= TEST_START]
            tests = {"elo_v0": t.p_v0.to_numpy()}
            if "(a) TML Elo" in candidates:
                tests["(a) TML Elo"] = t.p_a.to_numpy()
            if "(b) forecaster" in candidates:
                xall, yall = mirrored(feats[main_rows & (when < TEST_START) & (when >= TRAIN[0])][FEATURES])
                final = HistGradientBoostingClassifier(max_depth=gb["max_depth"], learning_rate=gb["learning_rate"],
                                                       min_samples_leaf=gb["min_samples_leaf"], max_iter=gb["trees"],
                                                       early_stopping=False, random_state=9).fit(xall, yall)
                tests["(b) forecaster"] = sym_proba(final, xk.loc[t.index])
            yt = t.y.to_numpy()
            th = ((t.Odd_1 > 1) & (t.Odd_2 > 1)).to_numpy()
            print(f"\nTEST {TEST_START[:4]}+ (one look): {len(t):,} linked matches")
            out = {}
            for k, p in tests.items():
                out[k] = {"log_loss": float(match_ll(p, yt).mean()), "accuracy": float(((p > .5) == (yt == 1)).mean()),
                          "wallet": wallet_run(t[th].reset_index(drop=True), p[th])}
                print(f"  {k:16s} log loss {out[k]['log_loss']:.4f}  accuracy {out[k]['accuracy']:.1%}  "
                      f"ROI {out[k]['wallet']['roi']:+.1%} ({out[k]['wallet']['bets']} bets)")
            result["test"] = out

    OUT.write_text(json.dumps(result, indent=2, default=float))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(test="--test" in sys.argv)
