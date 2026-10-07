"""E006: does adding serve/return stats (Jeff Sackmann's data) make E005's XGBoost better?

Elo only knows who won. Sackmann's files also say *how*: serve points won, return points
won, aces, double faults, break points. If a player wins his matches narrowly while losing
lots of return points, Elo may rate him too high; point-level stats can see that.

For every player we keep running totals of these counts over all earlier matches
(including challengers and qualifying), with older matches fading out (×0.95 per match).
The model sees the P1 − P2 difference of each rate, as it was BEFORE the match.

Protocol (pre-registered in experiments/LOG.md): identical to E005, and E005's feature set is
retrained in this script on the same rows as the baseline. Test years (2023+) are NOT touched.

    uv run python fetch_data.py sackmann                                       (once)
    uv run --group experiments python -W ignore experiments/e006_serve_stats.py   -> results/e006_serve_stats.json
"""

import itertools
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
import backtest as bt  # noqa: E402
from e003_decision_tree import LABELS, SYMMETRIC, build_features  # noqa: E402
from e004_format_calibration import cluster_ci, gap, match_ll, wallet_run  # noqa: E402
from e005_xgboost import FIT, GRID, TRAIN, TUNE, VALID, make  # noqa: E402
from strategies import logit  # noqa: E402

SACKMANN = ROOT / "data" / "sackmann"
DECAY = 0.95  # each older match counts 5% less (half-life ≈ 14 matches)
MIN_MATCHES = 3  # fewer prior matches with stats -> rates are missing (XGBoost handles gaps)
ROUND_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "RR": 4, "R128": 5, "R64": 6, "R32": 7, "R16": 8,
               "QF": 9, "SF": 10, "BR": 11, "F": 12}
BASE = list(LABELS) + ["elo_logit"]
STATS = ["serve_won", "return_won", "total_won", "ace_rate", "df_rate", "first_in", "bp_saved", "bp_conv"]
NEW = [f"{s}_diff" for s in STATS] + ["serve_vs_return", "stat_matches_diff"]
SYM = SYMMETRIC + ["elo_logit"] + NEW
OUT = ROOT / "results" / "e006_serve_stats.json"


# --------------------------------------------------------------- Sackmann stats


def load_sackmann() -> pd.DataFrame:
    frames = []
    for f in sorted(SACKMANN.glob("atp_matches_*.csv")):
        d = pd.read_csv(f, low_memory=False)
        d["main_tour"] = "qual_chall" not in f.name
        frames.append(d)
    s = pd.concat(frames, ignore_index=True)
    s["tourney_date"] = pd.to_datetime(s.tourney_date.astype(int).astype(str), format="%Y%m%d")
    s["round_no"] = s["round"].map(ROUND_ORDER).fillna(6)
    return s.sort_values(["tourney_date", "tourney_id", "round_no", "match_num"], kind="stable").reset_index(drop=True)


def stat_snapshots(s: pd.DataFrame) -> pd.DataFrame:
    """Walk through every match in order; record both players' rates BEFORE it, then update."""
    tot: dict[int, defaultdict] = defaultdict(lambda: defaultdict(float))

    def rates(pid: int) -> dict:
        t = tot[pid]
        if t["n"] < MIN_MATCHES or t["svpt"] <= 0 or t["ret_pts"] <= 0:
            return {k: np.nan for k in STATS} | {"n": t["n"]}
        return {"serve_won": t["sv_won"] / t["svpt"], "return_won": t["ret_won"] / t["ret_pts"],
                "total_won": (t["sv_won"] + t["ret_won"]) / (t["svpt"] + t["ret_pts"]),
                "ace_rate": t["ace"] / t["svpt"], "df_rate": t["df"] / t["svpt"], "first_in": t["first_in"] / t["svpt"],
                "bp_saved": t["bp_saved"] / t["bp_faced"] if t["bp_faced"] > 0 else np.nan,
                "bp_conv": t["bp_won"] / t["bp_chances"] if t["bp_chances"] > 0 else np.nan, "n": t["n"]}

    def add(pid: int, me: str, opp: str, r) -> None:
        sv = lambda side, c: getattr(r, f"{side}_{c}")  # noqa: E731
        t = tot[pid]
        for k in list(t):
            t[k] *= DECAY if k != "n" else 1
        t["n"] += 1
        t["svpt"] += sv(me, "svpt")
        t["sv_won"] += sv(me, "1stWon") + sv(me, "2ndWon")
        t["first_in"] += sv(me, "1stIn")
        t["ace"] += sv(me, "ace")
        t["df"] += sv(me, "df")
        t["bp_saved"] += sv(me, "bpSaved")
        t["bp_faced"] += sv(me, "bpFaced")
        t["ret_pts"] += sv(opp, "svpt")
        t["ret_won"] += sv(opp, "svpt") - sv(opp, "1stWon") - sv(opp, "2ndWon")
        t["bp_chances"] += sv(opp, "bpFaced")
        t["bp_won"] += sv(opp, "bpFaced") - sv(opp, "bpSaved")

    cols = ["svpt", "1stIn", "1stWon", "2ndWon", "ace", "df", "bpSaved", "bpFaced"]
    has = s[[f"{p}_{c}" for p in ("w", "l") for c in cols]].notna().all(axis=1) & (s.w_svpt > 0) & (s.l_svpt > 0)
    out = []
    for r, ok in zip(s.itertuples(), has):
        if r.main_tour:
            out.append({"idx": r.Index, **{f"w_{k}": v for k, v in rates(r.winner_id).items()},
                        **{f"l_{k}": v for k, v in rates(r.loser_id).items()}})
        if ok:
            add(r.winner_id, "w", "l", r)
            add(r.loser_id, "l", "w", r)
    return pd.DataFrame(out).set_index("idx")


# ------------------------------------------------------------ joining the sources


def norm(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", x)


def kaggle_keys(name: str) -> set[str]:
    """'Del Potro J.M.' -> {'delpotro|j'}. Trailing initials are the first name.
    A hyphenated surname also tries its first part: 'Ramos-Vinolas A.' is 'Albert Ramos' in Sackmann."""
    toks = name.split()
    i = len(toks)
    while i > 1 and re.fullmatch(r"[A-Z][a-z]?\.?([A-Z]\.?)*", toks[i - 1]):
        i -= 1
    ini = norm(toks[i] if i < len(toks) else "")[:1]
    surname = " ".join(toks[:i])
    return {f"{norm(surname)}|{ini}", f"{norm(surname.split('-')[0])}|{ini}"}


def sackmann_keys(name: str) -> set[str]:
    """'Roberto Bautista Agut' -> {'bautista|r', 'bautistaagut|r', 'agut|r'}: any run of later words."""
    w = str(name).split()
    if len(w) < 2:
        return {f"{norm(name)}|"}
    ini = norm(w[0])[:1]
    return {f"{norm(' '.join(w[i:j]))}|{ini}" for i in range(1, len(w)) for j in range(i + 1, len(w) + 1)}


def join(df: pd.DataFrame, s: pd.DataFrame) -> pd.Series:
    """Kaggle row index -> Sackmann row index, via (winner key, loser key) within the tournament's dates."""
    main = s[s.main_tour]
    sk = pd.DataFrame([(i, wk, lk) for i, w, l in zip(main.index, main.winner_name, main.loser_name)
                       for wk in sackmann_keys(w) for lk in sackmann_keys(l)], columns=["s_idx", "wk", "lk"])
    sk["tourney_date"] = s.loc[sk.s_idx, "tourney_date"].to_numpy()
    loser = np.where(df.p1_won, df.Player_2, df.Player_1)
    kg = pd.DataFrame([(i, wk, lk, d) for i, w, l, d in zip(df.index, df.Winner, loser, df.date)
                       for wk in kaggle_keys(w) for lk in kaggle_keys(l)], columns=["k_idx", "wk", "lk", "date"])
    m = kg.merge(sk, on=["wk", "lk"])
    m["days"] = (m.date - m.tourney_date).dt.days
    m = m[m.days.between(-3, 20)].sort_values("days", key=abs)
    m = m.drop_duplicates("k_idx").drop_duplicates("s_idx")
    return m.set_index("k_idx").s_idx


def stat_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    s = load_sackmann()
    snaps = stat_snapshots(s)
    link = join(df, s)
    feats = pd.DataFrame(index=df.index, columns=NEW, dtype=float)
    snap = snaps.loc[link.to_numpy()]
    p1w = df.loc[link.index, "p1_won"].to_numpy()
    side = lambda a, b: np.where(p1w, snap[f"w_{a}"], snap[f"l_{a}"]) if b == 1 else \
        np.where(p1w, snap[f"l_{a}"], snap[f"w_{a}"])  # noqa: E731
    for k in STATS:
        feats.loc[link.index, f"{k}_diff"] = side(k, 1) - side(k, 2)
    feats.loc[link.index, "serve_vs_return"] = ((side("serve_won", 1) - side("return_won", 2))
                                                - (side("serve_won", 2) - side("return_won", 1)))
    feats.loc[link.index, "stat_matches_diff"] = np.log1p(side("n", 1)) - np.log1p(side("n", 2))
    return feats, pd.Series(df.index.isin(link.index), index=df.index)


# ------------------------------------------------------------------ the model


def flipped(x: pd.DataFrame) -> pd.DataFrame:
    f = x.copy()
    cols = [c for c in SYM if c in f.columns]
    f[cols] = -f[cols]
    return f


def mirrored(x: pd.DataFrame, y: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    return pd.concat([x, flipped(x)], ignore_index=True), np.concatenate([y, 1 - y])


def sym_predict(model, x: pd.DataFrame) -> np.ndarray:
    return (model.predict_proba(x)[:, 1] + 1 - model.predict_proba(flipped(x))[:, 1]) / 2


def fit_and_score(name: str, feats: pd.DataFrame, cols: list[str], y: np.ndarray) -> tuple[np.ndarray, dict, object]:
    """E005's protocol: grid on 2018-19, refit 2010-19, predict 2020-22."""
    sel = lambda span: feats.date.between(*span).to_numpy()  # noqa: E731
    fit, tune, train, valid = sel(FIT), sel(TUNE), sel(TRAIN), sel(VALID)
    xf, yf = mirrored(feats.loc[fit, cols], y[fit])
    xt, yt = mirrored(feats.loc[tune, cols], y[tune])
    tried = []
    for depth, lr, mcw in itertools.product(*GRID.values()):
        params = {"max_depth": depth, "learning_rate": lr, "min_child_weight": mcw}
        m = make(params).fit(xf, yf, eval_set=[(xt, yt)], verbose=False)
        ll = match_ll(sym_predict(m, feats.loc[tune, cols]), y[tune]).mean()
        tried.append({**params, "trees": int(m.best_iteration) + 1, "tune_log_loss": float(ll)})
    best = min(tried, key=lambda r: r["tune_log_loss"])
    params = {k: best[k] for k in GRID}
    print(f"  {name}: {len(tried)} variants, chosen {params}, {best['trees']} trees, "
          f"2018-19 log loss {best['tune_log_loss']:.4f}")
    xtr, ytr = mirrored(feats.loc[train, cols], y[train])
    model = make(params, n=best["trees"], early=False).fit(xtr, ytr, verbose=False)
    return sym_predict(model, feats.loc[valid, cols]), {"grid": tried, "chosen": {**params, "trees": best["trees"]}}, model


def main() -> None:
    df = bt.load_atp()
    df["best_of"] = df["Best of"]
    print("building pre-match features (Elo, ranking, form...)")
    feats = build_features(df)
    feats["elo_logit"] = logit(feats.elo_p.to_numpy())
    feats["tourney"] = df.date.dt.year.astype(str).to_numpy() + " " + df.Tournament.to_numpy()
    for c in ("Player_1", "Player_2", "Winner"):
        feats[c] = df[c].to_numpy()
    print("replaying Sackmann stats and joining them to the odds data...")
    stats, linked = stat_features(df)
    feats = pd.concat([feats, stats], axis=1)
    y = feats.p1_won.astype(int).to_numpy()

    yr = feats.date.dt.year
    cover = pd.DataFrame({"linked": linked.groupby(yr).mean(),
                          "has_stats": feats.serve_won_diff.notna().groupby(yr).mean()})
    print("Share of odds-data matches linked to Sackmann / with both players' stats:")
    print(cover.loc[2010:2022].round(3).T.to_string())

    print("\nFitting (same protocol and grid as E005):")
    p_base, info_base, _ = fit_and_score("E005 features", feats, BASE, y)
    p_new, info_new, model = fit_and_score("E005 + serve stats", feats, BASE + NEW, y)

    valid = feats.date.between(*VALID).to_numpy()
    v = feats[valid].reset_index(drop=True)
    yv, bo5 = y[valid], v.best_of_5.to_numpy().astype(bool)
    has_odds = ((v.odd_1 > 1) & (v.odd_2 > 1)).to_numpy()
    book = np.full(len(v), np.nan)
    book[has_odds] = bt.implied_probs(v.loc[has_odds, ["odd_1", "odd_2"]].to_numpy(float))[:, 0]
    probs = {"raw Elo (elo_v0)": v.elo_p.to_numpy(), "E005 XGBoost": p_base, "E006 + serve stats": p_new}

    print(f"\nValidation 2020-2022: {len(v):,} matches")
    print(f"  {'model':20s} {'log loss':>9s} {'accuracy':>9s} {'gap Bo3':>8s} {'gap Bo5':>8s}")
    scores = {}
    for k, p in {**probs, "bookmaker": book}.items():
        o = has_odds if k == "bookmaker" else np.ones(len(v), bool)
        scores[k] = {"log_loss": float(match_ll(p[o], yv[o]).mean()), "accuracy": float(((p[o] > .5) == (yv[o] == 1)).mean()),
                     "gap_bo3": gap(p[o & ~bo5], yv[o & ~bo5]), "gap_bo5": gap(p[o & bo5], yv[o & bo5])}
        s = scores[k]
        print(f"  {k:20s} {s['log_loss']:9.4f} {s['accuracy']:9.1%} {s['gap_bo3']:+7.1f}  {s['gap_bo5']:+7.1f}")

    d = match_ll(p_base, yv) - match_ll(p_new, yv)
    ci = cluster_ci(d, v.tourney.to_numpy())
    yearly = pd.DataFrame({"year": v.date.dt.year, "d": d}).groupby("year").d.mean()
    with_stats = v.serve_won_diff.notna().to_numpy()
    print(f"\nImprovement per match vs E005: {d.mean():+.5f}  95% CI [{ci[0]:+.5f}, {ci[1]:+.5f}]")
    print("  by year: " + ", ".join(f"{yr} {x:+.5f}" for yr, x in yearly.items()))
    print(f"  on matches with stats for both players ({with_stats.sum():,}): {d[with_stats].mean():+.5f}")

    odds = v[has_odds].rename(columns={"odd_1": "Odd_1", "odd_2": "Odd_2"}).reset_index(drop=True)
    wallets = {k: wallet_run(odds, p[has_odds]) for k, p in probs.items()}
    print("\nWallet on 2020-2022 ($1,000, live rules):")
    for k, s in wallets.items():
        print(f"  {k:20s} {s['bets']:5d} bets  ROI {s['roi']:+.1%}  final ${s['final_bankroll']:,.0f}  "
              f"max drawdown {s['max_drawdown']:.0%}")

    rule1, rule2 = ci[0] > 0, int((yearly > 0).sum()) >= 2
    rule3 = wallets["E006 + serve stats"]["roi"] >= wallets["raw Elo (elo_v0)"]["roi"]
    passed = rule1 and rule2 and rule3
    print(f"\nPass rules: (1) CI excludes 0: {rule1}  (2) {int((yearly > 0).sum())}/3 years: {rule2}  "
          f"(3) ROI >= elo_v0: {rule3}  ->  {'PASS' if passed else 'FAIL'}")

    gain = model.get_booster().get_score(importance_type="gain")
    total = sum(gain.values())
    importance = {f: round(gain.get(f, 0) / total, 4) for f in BASE + NEW}
    print("\nFeature importance (share of total gain):")
    for f, g in sorted(importance.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {f:20s} {g:6.1%}")

    OUT.write_text(json.dumps({"coverage": cover.loc[2010:2022].to_dict(), "baseline": info_base, "new": info_new,
                               "validation": scores, "improvement_vs_e005": float(d.mean()), "ci": ci,
                               "by_year": yearly.to_dict(), "improvement_with_stats": float(d[with_stats].mean()),
                               "wallets": wallets, "importance": importance,
                               "rules": {"ci": rule1, "years": rule2, "roi": rule3}, "passed": passed},
                              indent=2, default=float))
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
