"""E003: a decision tree on ATP matches. Which variable splits winners from losers best?

A decision tree asks one yes/no question at a time ("is the Elo gap > 120?"), picking at every
step the question that makes the two resulting groups as *pure* as possible: ideally one
group where Player 1 almost always wins and one where he almost always loses.
Purity is measured with Gini impurity: 1 - p^2 - (1-p)^2 (0 = pure, 0.5 = coin flip).
Then it repeats inside each group: split, split, split.

Protocol (docs/REFERENCE.md §7): fit on TRAIN 2010-2019, choose depth on VALIDATION 2020-2022.
The test years (2023+) are NOT touched.

    uv run python -W ignore experiments/e003_decision_tree.py      -> results/e003_decision_tree.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest as bt  # noqa: E402
from elo import TennisElo, expected_score, log_loss  # noqa: E402

TRAIN = ("2010-01-01", "2019-12-31")
VALID = ("2020-01-01", "2022-12-31")

# Every feature is "Player 1 minus Player 2" (or a match property), known BEFORE the match.
LABELS = {
    "elo_diff": "Elo gap (P1 − P2)",
    "surface_elo_diff": "Surface Elo gap",
    "rank_ratio": "Ranking ratio, log(rank P2 / rank P1)",
    "points_ratio": "Ranking points ratio, log",
    "form10_diff": "Win rate, last 10 (P1 − P2)",
    "experience_diff": "Career matches, log (P1 − P2)",
    "rust_diff": "Days since last match (P1 − P2)",
    "best_of_5": "Best of 5 sets",
    "surface_clay": "Surface is clay",
    "surface_grass": "Surface is grass",
}
SYMMETRIC = ["elo_diff", "surface_elo_diff", "rank_ratio", "points_ratio", "form10_diff", "experience_diff", "rust_diff"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Replay history once, recording pre-match features (predict-before-update, no leakage)."""
    elo = TennisElo(k_scale=200, surface_weight=0.5)
    last_played: dict[str, pd.Timestamp] = {}
    recent: dict[str, list[int]] = {}
    count: dict[str, int] = {}
    rows = []
    for r in df.itertuples():
        a, b, srf = r.Player_1, r.Player_2, r.Surface
        fa, fb = recent.get(a, []), recent.get(b, [])
        ra = r.Rank_1 if r.Rank_1 and r.Rank_1 > 0 else 2000
        rb = r.Rank_2 if r.Rank_2 and r.Rank_2 > 0 else 2000
        pa = r.Pts_1 if r.Pts_1 and r.Pts_1 > 0 else 1
        pb = r.Pts_2 if r.Pts_2 and r.Pts_2 > 0 else 1
        rows.append({
            "date": r.date, "p1_won": r.p1_won, "odd_1": r.Odd_1, "odd_2": r.Odd_2,
            "elo_p": expected_score(elo.diff(a, b, srf)),
            "elo_diff": elo.overall[a] - elo.overall[b],
            "surface_elo_diff": elo.surface[(a, srf)] - elo.surface[(b, srf)],
            "rank_ratio": np.log(rb) - np.log(ra),
            "points_ratio": np.log(pa) - np.log(pb),
            "form10_diff": (np.mean(fa) if fa else 0.5) - (np.mean(fb) if fb else 0.5),
            "experience_diff": np.log1p(count.get(a, 0)) - np.log1p(count.get(b, 0)),
            "rust_diff": min((r.date - last_played[a]).days, 365) - min((r.date - last_played[b]).days, 365)
            if a in last_played and b in last_played else 0,
            "best_of_5": int(r.best_of == 5),
            "surface_clay": int(srf == "Clay"),
            "surface_grass": int(srf == "Grass"),
        })
        w, l = (a, b) if r.p1_won else (b, a)
        elo.update(w, l, srf)
        for p, won in ((a, r.p1_won), (b, not r.p1_won)):
            recent[p] = (recent.get(p, []) + [int(won)])[-10:]
            count[p] = count.get(p, 0) + 1
            last_played[p] = r.date
    return pd.DataFrame(rows)


def mirrored(x: pd.DataFrame, y: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    """Add every match a second time with the players swapped, so the tree can't learn
    anything from which player happens to be listed first."""
    flip = x.copy()
    flip[SYMMETRIC] = -flip[SYMMETRIC]
    return pd.concat([x, flip], ignore_index=True), np.concatenate([y, 1 - y])


def gini(p: float) -> float:
    return 1 - p ** 2 - (1 - p) ** 2


def best_single_split(x: pd.Series, y: np.ndarray) -> dict:
    """Try one question on one variable: which threshold leaves the purest two groups?"""
    stump = DecisionTreeClassifier(max_depth=1, min_samples_leaf=500).fit(x.to_frame(), y)
    t = stump.tree_
    if t.node_count < 3:
        return {"threshold": None, "gain": 0.0}
    n = t.n_node_samples
    parent = gini(y.mean())
    left = t.value[1][0][1] / t.value[1][0].sum() if t.value[1][0].sum() else 0
    right = t.value[2][0][1] / t.value[2][0].sum() if t.value[2][0].sum() else 0
    child = (n[1] * gini(left) + n[2] * gini(right)) / n[0]
    return {"threshold": float(t.threshold[0]), "gain": float(parent - child),
            "left_p1_win": float(left), "right_p1_win": float(right)}


def export_tree(tree: DecisionTreeClassifier, features: list[str]) -> dict:
    t = tree.tree_

    def node(i: int) -> dict:
        counts = t.value[i][0]
        p = float(counts[1] / counts.sum())
        out = {"samples": int(t.n_node_samples[i]), "p1_win": round(p, 4), "gini": round(float(t.impurity[i]), 4)}
        if t.children_left[i] == -1:
            return {**out, "leaf": True}
        f = features[t.feature[i]]
        return {**out, "leaf": False, "feature": f, "label": LABELS[f], "threshold": round(float(t.threshold[i]), 3),
                "left": node(t.children_left[i]), "right": node(t.children_right[i])}

    return node(0)


def main() -> None:
    df = bt.load_atp()
    df["best_of"] = df["Best of"]
    print("building pre-match features (one replay of 69k matches)...")
    feats = build_features(df)

    tr = feats.date.between(*TRAIN).to_numpy()
    va = feats.date.between(*VALID).to_numpy()
    cols = list(LABELS)
    y = feats.p1_won.astype(int).to_numpy()
    print(f"train {tr.sum():,} matches, validation {va.sum():,}; P1 win rate {y.mean():.3f} "
          f"({'listing order looks random' if abs(y.mean() - 0.5) < 0.01 else 'listing order is NOT random'})")

    xtr, ytr = mirrored(feats.loc[tr, cols], y[tr])
    xva, yva = feats.loc[va, cols], y[va]
    ll = lambda p: log_loss(list(np.where(yva == 1, p, 1 - p)))

    # 1. Which single variable best splits the data? (the root question)
    ranking = sorted(({"feature": f, "label": LABELS[f], **best_single_split(xtr[f], ytr)} for f in cols),
                     key=lambda r: -r["gain"])
    print("\nBest single split per variable (Gini gain on train; higher = purer groups):")
    for r in ranking:
        thr = "" if r["threshold"] is None else f" at {r['threshold']:+.2f}"
        print(f"  {r['label']:42}{thr:>12}  gain {r['gain']:.4f}")

    # 2. Grow trees of different depths; choose depth on VALIDATION only.
    depth_rows = []
    for depth in range(1, 11):
        m = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=300, random_state=0).fit(xtr, ytr)
        depth_rows.append({"depth": depth, "leaves": int(m.get_n_leaves()), "val_log_loss": ll(m.predict_proba(xva)[:, 1])})
    best = min(depth_rows, key=lambda r: r["val_log_loss"])
    print("\nValidation log loss by depth:", ", ".join(f"d{r['depth']}={r['val_log_loss']:.4f}" for r in depth_rows))

    best_tree = DecisionTreeClassifier(max_depth=best["depth"], min_samples_leaf=300, random_state=0).fit(xtr, ytr)
    show_tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=300, random_state=0).fit(xtr, ytr)
    importance = sorted(({"feature": f, "label": LABELS[f], "importance": float(v)}
                         for f, v in zip(cols, best_tree.feature_importances_)), key=lambda r: -r["importance"])

    # 3. Compare with the baselines on the same validation matches.
    elo_raw = feats.loc[va, "elo_p"].to_numpy()
    logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    cal = LogisticRegression().fit(logit(feats.loc[tr, "elo_p"].to_numpy()), y[tr])
    has_odds = (feats.loc[va, "odd_1"] > 1).to_numpy() & (feats.loc[va, "odd_2"] > 1).to_numpy()
    odds = feats.loc[va, ["odd_1", "odd_2"]].to_numpy()[has_odds]
    market = bt.implied_probs(odds)[:, 0]
    sub = lambda p: log_loss(list(np.where(yva[has_odds] == 1, p[has_odds], 1 - p[has_odds])))
    tree_p = best_tree.predict_proba(xva)[:, 1]
    elo_cal = cal.predict_proba(logit(elo_raw))[:, 1]
    compare = [
        {"model": "Coin flip", "val_log_loss": log_loss([0.5] * int(has_odds.sum()))},
        {"model": f"Decision tree (depth {best['depth']})", "val_log_loss": sub(tree_p)},
        {"model": "Elo (elo_v0)", "val_log_loss": sub(elo_raw)},
        {"model": "Elo, calibrated", "val_log_loss": sub(elo_cal)},
        {"model": "Bookmaker", "val_log_loss": log_loss(list(np.where(yva[has_odds] == 1, market, 1 - market)))},
    ]
    print(f"\nValidation 2020-22, {has_odds.sum():,} matches with odds:")
    for c in compare:
        print(f"  {c['model']:28} {c['val_log_loss']:.4f}")
    print("\nFeature importance (share of all Gini reduction in the chosen tree):")
    for r in importance:
        print(f"  {r['label']:42} {r['importance']:.1%}")

    out = {
        "experiment": "E003", "sport": "atp", "train": TRAIN, "validation": VALID, "test_years_touched": False,
        "n_train": int(tr.sum()), "n_validation": int(va.sum()), "min_samples_leaf": 300,
        "split_ranking": ranking, "depth_search": depth_rows, "chosen_depth": best["depth"],
        "importance": importance, "comparison": compare, "tree": export_tree(show_tree, cols),
    }
    (ROOT / "results" / "e003_decision_tree.json").write_text(json.dumps(out, indent=2))
    print("\nwrote results/e003_decision_tree.json")


if __name__ == "__main__":
    main()
