"""Replay history match by match and ask: does Elo beat the bookmaker?

The golden rule: when predicting a match, the model may only use matches that
happened BEFORE it. We walk forward through time: predict -> record -> update.

Split:
  - TRAIN period: used to choose settings (K, home advantage...) and to learn how an
    Elo gap maps to win/draw/loss chances.
  - TEST period: never touched while tuning. This is the honest score.

Outputs go to results/: bet logs for each sport plus current ratings.
"""

from pathlib import Path

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from elo import FootballElo, TennisElo, log_loss
from wallet import Wallet

ROOT = Path(__file__).parent
DATA, RESULTS = ROOT / "data", ROOT / "results"


def implied_probs(odds: np.ndarray) -> np.ndarray:
    """Decimal odds -> probabilities with the bookmaker's cut (vig) removed.
    1/odds sums to more than 1 (e.g. 1.05); dividing by that sum strips the margin."""
    raw = 1.0 / odds
    return raw / raw.sum(axis=1, keepdims=True)


# =========================================================================== EPL

EPL_TRAIN = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2012, 2022)]  # 2012/13-2021/22
EPL_TEST = [f"{y % 100:02d}{(y + 1) % 100:02d}" for y in range(2022, 2027)]  # 2022/23-now
# Preferred odds first: Pinnacle closing (the sharpest bookmaker), then market-average closing,
# then opening averages for old seasons.
ODDS_SETS = [("PSCH", "PSCD", "PSCA"), ("AvgCH", "AvgCD", "AvgCA"),
             ("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA"), ("B365H", "B365D", "B365A")]


def load_epl() -> pd.DataFrame:
    frames = []
    for f in sorted((DATA / "epl").glob("E0_*.csv")):
        d = pd.read_csv(f, encoding="latin-1").dropna(subset=["HomeTeam", "FTHG"])
        d["season"] = f.stem.split("_")[1]
        odds = np.full((len(d), 3), np.nan)
        for cols in ODDS_SETS:  # fill each match from the best odds source available
            if all(c in d.columns for c in cols):
                missing = np.isnan(odds).any(axis=1)
                odds[missing] = d.loc[missing, list(cols)].to_numpy(float)
        d[["odds_h", "odds_d", "odds_a"]] = odds
        frames.append(d)
    df = pd.concat(frames, ignore_index=True).copy()
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    df["result"] = np.select([df.FTHG > df.FTAG, df.FTHG == df.FTAG], ["H", "D"], "A")
    return df.sort_values(["date"], kind="stable").reset_index(drop=True)


def epl_elo_diffs(df: pd.DataFrame, **params) -> tuple[np.ndarray, FootballElo]:
    """Walk forward through every match, recording the pre-match Elo gap."""
    elo = FootballElo(**params)
    diffs = np.empty(len(df))
    for season, games in df.groupby("season", sort=True):
        elo.start_season(season, set(games.HomeTeam) | set(games.AwayTeam))
        for i, g in games.iterrows():
            diffs[i] = elo.diff(g.HomeTeam, g.AwayTeam)  # predict BEFORE updating
            elo.update(g.HomeTeam, g.AwayTeam, int(g.FTHG), int(g.FTAG))
    return diffs, elo


def fit_outcome_model(diff: np.ndarray, result: np.ndarray) -> LogisticRegression:
    """Elo gives one number; football has three outcomes. This small model learns,
    from the training years, how a given Elo gap translates into P(home), P(draw), P(away).
    (Draws are most likely when teams are close, so P(draw) peaks near a gap of zero.)"""
    return LogisticRegression().fit(diff.reshape(-1, 1) / 100, result)


def outcome_probs(model: LogisticRegression, diff: np.ndarray) -> pd.DataFrame:
    p = model.predict_proba(diff.reshape(-1, 1) / 100)
    return pd.DataFrame(p, columns=model.classes_)[["H", "D", "A"]]


def prob_of_actual(probs: pd.DataFrame | np.ndarray, result: pd.Series) -> list[float]:
    idx = result.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    arr = np.asarray(probs)
    return list(arr[np.arange(len(arr)), idx])


def run_epl() -> dict:
    print("=" * 70, "\nEPL\n" + "=" * 70)
    df = load_epl()
    train = df.season.isin(EPL_TRAIN).to_numpy()
    test = df.season.isin(EPL_TEST).to_numpy()

    # 1. Tune: try a small grid of settings, keep whichever predicts the TRAIN years best.
    best = None
    for k in [15, 20, 25, 30]:
        for home_adv in [40, 60, 80]:
            for carryover in [0.7, 0.8, 0.9]:
                diffs, _ = epl_elo_diffs(df, k=k, home_adv=home_adv, carryover=carryover)
                m = fit_outcome_model(diffs[train], df.result[train].to_numpy())
                ll = log_loss(prob_of_actual(outcome_probs(m, diffs[train]), df.result[train]))
                if best is None or ll < best[0]:
                    best = (ll, dict(k=k, home_adv=home_adv, carryover=carryover))
    params = best[1]
    print(f"Best settings on train years: {params}")

    # 2. Rebuild with the chosen settings and score the untouched TEST years.
    diffs, elo = epl_elo_diffs(df, **params)
    model = fit_outcome_model(diffs[train], df.result[train].to_numpy())
    t = df[test].reset_index(drop=True)
    elo_p = outcome_probs(model, diffs[test])
    book_p = implied_probs(t[["odds_h", "odds_d", "odds_a"]].to_numpy())
    base = df.result[train].value_counts(normalize=True)[["H", "D", "A"]].to_numpy()

    print(f"\nTest period: {EPL_TEST[0]}-{EPL_TEST[-1]}, {len(t)} matches. Log loss (lower = better):")
    scores = {"baseline": log_loss(prob_of_actual(np.tile(base, (len(t), 1)), t.result)),
              "elo": log_loss(prob_of_actual(elo_p, t.result)),
              "bookmaker": log_loss(prob_of_actual(book_p, t.result))}
    print(f"  Know-nothing (always predict the average H/D/A rates): {scores['baseline']:.4f}")
    print(f"  Elo                                                   : {scores['elo']:.4f}")
    print(f"  Bookmaker closing odds                                : {scores['bookmaker']:.4f}")

    # 3. Virtual wallet: bet wherever Elo disagrees enough with the odds.
    w = Wallet()
    for i, g in t.iterrows():
        opts = [("H", elo_p.H[i], g.odds_h), ("D", elo_p.D[i], g.odds_d), ("A", elo_p.A[i], g.odds_a)]
        bet = w.consider(opts)
        if bet:
            label, p, odds, stake = bet
            info = {"date": g.date.date(), "season": g.season, "match": f"{g.HomeTeam} v {g.AwayTeam}",
                    "score": f"{int(g.FTHG)}-{int(g.FTAG)}"}
            w.place_and_settle(info, label, p, odds, stake, won=(g.result == label))
    wallet = report_wallet(w, "epl")

    ratings = pd.Series({t_: elo.ratings[t_] for t_ in elo.season_teams}).sort_values(ascending=False)
    ratings.rename("elo").rename_axis("team").round(1).to_csv(RESULTS / "epl_ratings.csv")
    print("\nCurrent top 5 EPL Elo:\n" + ratings.head().round(0).to_string())
    return {"params": params, "test_period": f"{EPL_TEST[0]}-{EPL_TEST[-1]}", "matches": len(t),
            "log_loss": scores, "baseline_label": "Average H/D/A rates", "wallet": wallet}


# ======================================================================== Tennis

TENNIS_TUNE = ("2010-01-01", "2019-12-31")
TENNIS_TEST_START = "2023-01-01"


def load_atp(recent: Path | None = None) -> pd.DataFrame:
    """ATP history. `recent` = extra results collected live by daily.py; a live result is added
    unless the main dataset already has that match, so nothing is counted twice."""
    df = pd.read_csv(DATA / "tennis" / "atp_tennis.csv", low_memory=False)
    if recent is not None and recent.exists():
        extra = pd.read_csv(recent)
        extra = extra[~already_listed(df, extra)].drop(columns="event_id")
        df = pd.concat([df, extra], ignore_index=True)
    df[["Odd_1", "Odd_2"]] = df[["Odd_1", "Odd_2"]].apply(pd.to_numeric, errors="coerce")
    for col in ["Player_1", "Player_2", "Winner"]:
        df[col] = df[col].str.strip()  # some names have stray trailing spaces
    df["date"] = pd.to_datetime(df.Date)
    df["p1_won"] = df.Winner == df.Player_1
    return df.sort_values("date", kind="stable").reset_index(drop=True)


MATCH_SLACK_DAYS = 3  # the main dataset dates matches by local day, the live feed by UTC start


def already_listed(main: pd.DataFrame, extra: pd.DataFrame) -> pd.Series:
    """For each live result, whether `main` has the same two players within a few days.
    Matching by match, not by date: the main dataset often has only part of its latest days
    (e.g. one tournament's final but not another's), so a date cut-off would drop real results."""
    pair = lambda d: [frozenset(x) for x in zip(d.Player_1.str.strip(), d.Player_2.str.strip())]
    lo = pd.to_datetime(extra.Date).min() - pd.Timedelta(days=MATCH_SLACK_DAYS) if len(extra) else None
    m = main[pd.to_datetime(main.Date) >= lo] if lo is not None else main.iloc[:0]
    seen: dict[frozenset, list[pd.Timestamp]] = {}
    for k, d in zip(pair(m), pd.to_datetime(m.Date)):
        seen.setdefault(k, []).append(d)
    slack = pd.Timedelta(days=MATCH_SLACK_DAYS)
    return pd.Series([any(abs(d - t) <= slack for t in seen.get(k, [])) for k, d in zip(pair(extra), pd.to_datetime(extra.Date))],
                     index=extra.index, dtype=bool)


def tennis_probs(df: pd.DataFrame, **params) -> tuple[np.ndarray, TennisElo]:
    elo = TennisElo(**params)
    probs = np.empty(len(df))
    for i, (a, b, srf, a_won) in enumerate(zip(df.Player_1, df.Player_2, df.Surface, df.p1_won)):
        probs[i] = elo.prob(a, b, srf)  # predict BEFORE updating
        if a_won:
            elo.update(a, b, srf)
        else:
            elo.update(b, a, srf)
    return probs, elo


def run_tennis() -> dict:
    print("\n" + "=" * 70, "\nATP TENNIS\n" + "=" * 70)
    df = load_atp()
    tune = df.date.between(*TENNIS_TUNE).to_numpy()
    actual = lambda p, won: np.where(won, p, 1 - p)

    best = None
    for k_scale in [200, 250, 300]:
        for surface_weight in [0.0, 0.25, 0.5, 0.75]:
            p, _ = tennis_probs(df, k_scale=k_scale, surface_weight=surface_weight)
            ll = log_loss(list(actual(p[tune], df.p1_won[tune])))
            if best is None or ll < best[0]:
                best = (ll, dict(k_scale=k_scale, surface_weight=surface_weight))
    params = best[1]
    print(f"Best settings on {TENNIS_TUNE[0][:4]}-{TENNIS_TUNE[1][:4]}: {params}")

    p, elo = tennis_probs(df, **params)
    test = ((df.date >= TENNIS_TEST_START) & (df.Odd_1 > 1) & (df.Odd_2 > 1)).to_numpy()
    t = df[test].reset_index(drop=True)
    elo_p = p[test]
    book_p = implied_probs(t[["Odd_1", "Odd_2"]].to_numpy())[:, 0]

    print(f"\nTest period: {TENNIS_TEST_START[:4]}-{t.date.max().date()}, {len(t)} matches. Log loss (lower = better):")
    scores = {"baseline": log_loss([0.5] * len(t)),
              "elo": log_loss(list(actual(elo_p, t.p1_won))),
              "bookmaker": log_loss(list(actual(book_p, t.p1_won)))}
    print(f"  Coin flip (50/50)      : {scores['baseline']:.4f}")
    print(f"  Elo                    : {scores['elo']:.4f}")
    print(f"  Bookmaker odds         : {scores['bookmaker']:.4f}")

    w = Wallet()
    for i, g in t.iterrows():
        bet = w.consider([(g.Player_1, elo_p[i], g.Odd_1), (g.Player_2, 1 - elo_p[i], g.Odd_2)])
        if bet:
            label, prob, odds, stake = bet
            info = {"date": g.date.date(), "tournament": g.Tournament, "surface": g.Surface,
                    "match": f"{g.Player_1} v {g.Player_2}", "score": g.Score}
            w.place_and_settle(info, label, prob, odds, stake, won=(g.Winner == label))
    wallet = report_wallet(w, "tennis")

    active = df[df.date >= df.date.max() - pd.Timedelta(days=365)]
    players = set(active.Player_1) | set(active.Player_2)
    ratings = pd.DataFrame({
        "player": sorted(players),
        "elo": [elo.overall[x] for x in sorted(players)],
        **{f"elo_{s.lower()}": [elo.surface[(x, s)] for x in sorted(players)] for s in ["Hard", "Clay", "Grass"]},
    }).sort_values("elo", ascending=False).round(1)
    ratings.to_csv(RESULTS / "tennis_ratings.csv", index=False)
    print("\nCurrent top 5 ATP Elo:\n" + ratings.head().to_string(index=False))
    return {"params": params, "test_period": f"{TENNIS_TEST_START[:4]}-{t.date.max().date()}",
            "matches": len(t), "log_loss": scores, "baseline_label": "Coin flip", "wallet": wallet}


def report_wallet(w: Wallet, name: str) -> dict:
    s = w.summary()
    print(f"\nVirtual wallet ($1,000 start, quarter-Kelly, bet only if edge >= {w.min_edge:.0%}):")
    print(f"  {s['bets']} bets, won {s['win_rate']:.1%}, staked ${s['staked']:,.0f}, "
          f"profit ${s['profit']:,.0f}, ROI {s['roi']:+.1%}")
    print(f"  Final bankroll ${s['final_bankroll']:,.0f}, worst drawdown {s['max_drawdown']:.0%}")
    pd.DataFrame(w.bets).to_csv(RESULTS / f"{name}_bets.csv", index=False)
    return {**s, "min_edge": w.min_edge}


if __name__ == "__main__":
    RESULTS.mkdir(exist_ok=True)
    summary = {"epl": run_epl(), "atp": run_tennis()}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
