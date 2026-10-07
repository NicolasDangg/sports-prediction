"""E011: sharp vs soft. Use Pinnacle's price (margin removed) as the true probability and bet
wherever another bookmaker pays more than that. No model at all.

Example: Pinnacle has the home side at 1.80, draw 3.90, away 4.60 -> implied 55.6% + 25.6% + 21.7%
= 102.9%; scaled to 100% the home side is 54.0%, so its fair odds are 1/0.540 = 1.85. If Bet365
offers 1.95, then 0.540 x 1.95 - 1 = +5.3% expected value: a bet.

Data: football-data.co.uk EPL files. Their "opening" columns (B365H, PSH, MaxH...) were all
collected at the same moment (Friday afternoon for weekend games, Tuesday for midweek), so the
soft prices and the Pinnacle price are comparable. PSCH/PSCD/PSCA is Pinnacle's closing price.

Variants (tuned on 2012/13-2021/22 only):
  price  "soft": best price among named mainstream books (Bet365, Bet&Win, Interwetten, Ladbrokes,
                 William Hill, VC Bet, 1xBet, Betfair sportsbook...), i.e. books an ordinary
                 account can use. Realistic.
         "max":  market maximum across every book the site tracked. Optimistic (obscure books,
                 short-lived prices), shown for reference only.
  min_edge 0.01 / 0.02 / 0.03 / 0.05
Staking: quarter-Kelly, 5% cap, $1,000 start (wallet.py), plus flat $1 stakes for ROI.

Pre-registered rules (experiments/LOG.md, written before the first run):
  R1 train: mean CLV of the chosen variant > 0, 95% CI excludes 0
  R2 test:  mean CLV > 0, 95% CI excludes 0
  R3 test:  flat-stake ROI > 0 and the Kelly wallet ends above $1,000
  R4 test:  >= 100 bets
CLV (closing line value) = bet odds x Pinnacle's no-vig closing probability - 1. It measures
whether we got a better price than the sharpest closing price; far less noisy than profit.

    uv run python -W ignore experiments/e011_sharp_vs_soft.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import EPL_TEST, EPL_TRAIN, epl_elo_diffs, fit_outcome_model, load_epl, outcome_probs  # noqa: E402
from wallet import Wallet  # noqa: E402

SOFT_BOOKS = ["B365", "BW", "IW", "LB", "WH", "VC", "1XB", "BF", "GB", "SJ", "BS"]
MAX_COLS = [("MaxH", "MaxD", "MaxA"), ("BbMxH", "BbMxD", "BbMxA")]
OUT = ["H", "D", "A"]
EDGES = [0.01, 0.02, 0.03, 0.05]
rng = np.random.default_rng(11)


def no_vig(odds: np.ndarray) -> np.ndarray:
    imp = 1 / odds
    return imp / imp.sum(axis=1, keepdims=True)


def prepare() -> pd.DataFrame:
    df = load_epl()
    df = df[df.season.isin(EPL_TRAIN + EPL_TEST)].reset_index(drop=True)
    pin = df[["PSH", "PSD", "PSA"]].to_numpy(float)
    close = df[["PSCH", "PSCD", "PSCA"]].to_numpy(float)
    df[[f"fair_{o}" for o in OUT]] = no_vig(pin)
    df[[f"close_{o}" for o in OUT]] = no_vig(close)
    for i, o in enumerate(OUT):
        soft = [df[f"{b}{o}"] for b in SOFT_BOOKS if f"{b}{o}" in df]
        s = pd.concat(soft, axis=1).astype(float)
        df[f"soft_{o}"] = s.max(axis=1)
        df[f"soft_book_{o}"] = s.idxmax(axis=1).fillna("").str[:-1]
        mx = np.full(len(df), np.nan)
        for cols in MAX_COLS:
            if cols[i] in df:
                mx = np.where(np.isnan(mx), df[cols[i]].astype(float), mx)
        df[f"max_{o}"] = mx
    ok = np.isfinite(pin).all(axis=1) & np.isfinite(close).all(axis=1)
    return df[ok].reset_index(drop=True)


def run(df: pd.DataFrame, price: str, min_edge: float) -> dict:
    """One pass over the matches in date order; bet the best-edge outcome per match."""
    w, rows = Wallet(min_edge=min_edge), []
    for g in df.itertuples():
        opts = [(o, getattr(g, f"fair_{o}"), getattr(g, f"{price}_{o}")) for o in OUT]
        opts = [x for x in opts if np.isfinite(x[2])]
        bet = w.consider(opts)
        if not bet:
            continue
        o, p, odds, stake = bet
        won = g.result == o
        w.place_and_settle({"date": str(g.date.date()), "season": g.season, "match": f"{g.HomeTeam} v {g.AwayTeam}",
                            "book": getattr(g, f"soft_book_{o}") if price == "soft" else "max"}, o, p, odds, stake, won)
        rows.append({"clv": odds * getattr(g, f"close_{o}") - 1, "flat": odds - 1 if won else -1.0, "odds": odds})
    r = pd.DataFrame(rows, columns=["clv", "flat", "odds"])
    s = w.summary()
    return {"bets": len(r), "mean_odds": float(r.odds.mean()) if len(r) else None,
            "clv": float(r.clv.mean()) if len(r) else None, "clv_ci": ci(r.clv.to_numpy()),
            "flat_roi": float(r.flat.mean()) if len(r) else None, "flat_roi_ci": ci(r.flat.to_numpy()),
            "kelly_final": s["final_bankroll"], "kelly_roi": s["roi"], "max_drawdown": s["max_drawdown"],
            "by_book": pd.Series([b["book"] for b in w.bets]).value_counts().head(6).to_dict()}


def ci(x: np.ndarray, reps: int = 4000) -> list[float] | None:
    if len(x) < 2:
        return None
    m = rng.choice(x, (reps, len(x))).mean(axis=1)
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def elo_v0(df_all: pd.DataFrame, seasons: list[str]) -> dict:
    """The live control on the same matches, betting at the typical (average) opening price."""
    full = load_epl()
    params = json.loads((ROOT / "results" / "summary.json").read_text())["epl"]["params"]
    diffs, _ = epl_elo_diffs(full, **params)
    train = full.season.isin(EPL_TRAIN).to_numpy()
    model = fit_outcome_model(diffs[train], full.result[train].to_numpy())
    probs = outcome_probs(model, diffs)
    full[[f"elo_{o}" for o in OUT]] = probs[OUT].to_numpy()
    avg = [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA")]
    for i, o in enumerate(OUT):
        v = np.full(len(full), np.nan)
        for cols in avg:
            if cols[i] in full:
                v = np.where(np.isnan(v), full[cols[i]].astype(float), v)
        full[f"avg_{o}"] = v
    keys = ["date", "HomeTeam", "AwayTeam"]
    d = df_all[df_all.season.isin(seasons)][keys + [f"close_{o}" for o in OUT] + ["result", "season"]]
    d = d.merge(full[keys + [f"elo_{o}" for o in OUT] + [f"avg_{o}" for o in OUT]], on=keys, how="left")
    w, rows = Wallet(min_edge=0.05), []
    for g in d.itertuples():
        bet = w.consider([(o, getattr(g, f"elo_{o}"), getattr(g, f"avg_{o}")) for o in OUT])
        if bet:
            o, p, odds, stake = bet
            won = g.result == o
            w.place_and_settle({}, o, p, odds, stake, won)
            rows.append({"clv": odds * getattr(g, f"close_{o}") - 1, "flat": odds - 1 if won else -1.0})
    r = pd.DataFrame(rows)
    s = w.summary()
    return {"bets": len(r), "clv": float(r.clv.mean()), "clv_ci": ci(r.clv.to_numpy()),
            "flat_roi": float(r.flat.mean()), "flat_roi_ci": ci(r.flat.to_numpy()),
            "kelly_final": s["final_bankroll"], "max_drawdown": s["max_drawdown"]}


def show(name: str, r: dict) -> None:
    c, f = r["clv_ci"] or [np.nan] * 2, r["flat_roi_ci"] or [np.nan] * 2
    print(f"  {name:<22} bets {r['bets']:>5}  CLV {r['clv'] or 0:+.2%} [{c[0]:+.2%}, {c[1]:+.2%}]  "
          f"flat ROI {r['flat_roi'] or 0:+.2%} [{f[0]:+.2%}, {f[1]:+.2%}]  wallet ${r['kelly_final']:,.0f}  "
          f"maxDD {r['max_drawdown']:.0%}")


def main(look_at_test: bool) -> None:
    df = prepare()
    train, test = df[df.season.isin(EPL_TRAIN)], df[df.season.isin(EPL_TEST)]
    print(f"EPL matches with Pinnacle opening + closing: train {len(train)}, test {len(test)}")
    print(f"Pinnacle opening margin {(1 / df[['PSH', 'PSD', 'PSA']]).sum(axis=1).mean() - 1:.2%}, "
          f"best soft-book margin {(1 / df[['soft_H', 'soft_D', 'soft_A']]).sum(axis=1).mean() - 1:.2%}")

    print("\nTRAIN 2012/13-2021/22 (8 variants)")
    grid = {}
    for price in ("soft", "max"):
        for e in EDGES:
            grid[f"{price}@{e:.2f}"] = r = run(train, price, e)
            show(f"{price} min_edge {e:.2f}", r)
    base_train = elo_v0(df, EPL_TRAIN)
    show("elo_v0 (avg price)", base_train)

    # Choice rule fixed in advance: the realistic "soft" price, the min_edge with the highest
    # train CLV lower bound among variants with >= 100 bets.
    soft = {k: v for k, v in grid.items() if k.startswith("soft") and v["bets"] >= 100}
    chosen = max(soft, key=lambda k: soft[k]["clv_ci"][0])
    print(f"\nChosen: {chosen}  (R1 train CLV CI excludes 0: {grid[chosen]['clv_ci'][0] > 0})")
    out = {"train": grid, "elo_v0_train": base_train, "chosen": chosen, "soft_books": SOFT_BOOKS}

    if look_at_test:
        price, e = chosen.split("@")
        t = run(test, price, float(e))
        tm = run(test, "max", float(e))
        base = elo_v0(df, EPL_TEST)
        print(f"\nTEST 2022/23-now (one look)")
        show(chosen, t)
        show(f"max@{e} (reference)", tm)
        show("elo_v0 (avg price)", base)
        rules = {"R1": grid[chosen]["clv_ci"][0] > 0, "R2": t["clv_ci"][0] > 0,
                 "R3": t["flat_roi"] > 0 and t["kelly_final"] > 1000, "R4": t["bets"] >= 100}
        print("Rules:", rules, "->", "PASS" if all(rules.values()) else "FAIL")
        print("Bets by book:", t["by_book"])
        out.update(test=t, test_max=tm, elo_v0_test=base, rules=rules)
    (ROOT / "results" / "e011_sharp_vs_soft.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main(look_at_test="--test" in sys.argv)
