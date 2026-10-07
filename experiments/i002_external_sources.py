"""I002: what do the hand-downloaded tennisdata.app CSVs and the tennisabstract Elo page add?

Files (downloaded by the owner into data/retrieved_tennis_data/, not committed):
  <year>-atp-season.csv                 tennisdata.app, 2021-2026: ATP Tour + Challenger + qualifying,
                                        one match-winner price per side, first-set odds, % serve stats
  Tennis Abstract_ ATP Elo Ratings.html tennisabstract weekly Elo report (overall + per surface)

Checks (market-only or rating-vs-rating: none of them touches our model's test years):
  1. Are tennisdata.app odds a different moment than Kaggle's (useful for timing)? Join + compare.
  2. Are challenger / qualifying markets softer than ATP main? Bookmaker log loss, margin, favourite bias.
  3. How do our Elo ratings compare with tennisabstract's?

    uv run --group experiments python -W ignore experiments/i002_external_sources.py
"""

import glob
import io
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest as bt  # noqa: E402

SRC = ROOT / "data" / "retrieved_tennis_data"


def norm(x) -> str:
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower())


def short_key(name: str) -> str:
    """'Carreno-Busta P.' / 'Zhang Zh.' -> surname only (initials vary between sources)."""
    return norm(str(name).rsplit(" ", 1)[0]) if " " in str(name) else norm(name)


def load_tennisdata() -> pd.DataFrame:
    td = pd.concat([pd.read_csv(f, low_memory=False) for f in sorted(glob.glob(str(SRC / "*-atp-season.csv")))],
                   ignore_index=True)
    td = td[(td.status == "FINISHED") & td.winner_code.isin([1, 2])].copy()
    td["date"] = pd.to_datetime(td.date_timestamp, unit="s")
    td["has_odds"] = td.home_odds_match_winner.gt(1) & td.away_odds_match_winner.gt(1)
    h, a = 1 / td.home_odds_match_winner, 1 / td.away_odds_match_winner
    td["p_home"], td["margin"], td["y"] = h / (h + a), h + a - 1, (td.winner_code == 1).astype(int)
    return td


def check_odds_vs_kaggle(td: pd.DataFrame) -> None:
    t = td[(td.tour_type_human == "ATP Tour") & td.has_odds].copy()
    k = bt.load_atp()
    k = k[(k.date >= t.date.min() - pd.Timedelta(days=5)) & (k.Odd_1 > 1) & (k.Odd_2 > 1)].copy()
    t["pair"] = [tuple(sorted(x)) for x in zip(t.home_name.map(short_key), t.away_name.map(short_key))]
    k["pair"] = [tuple(sorted(x)) for x in zip(k.Player_1.map(short_key), k.Player_2.map(short_key))]
    m = t.merge(k, on="pair", suffixes=("", "_k"))
    m = m[(m.date - m.date_k).dt.days.abs() <= 3].drop_duplicates("match_id")
    same = m.home_name.map(short_key) == m.Player_1.map(short_key)
    oh, oa = np.where(same, m.Odd_1, m.Odd_2), np.where(same, m.Odd_2, m.Odd_1)
    pk = (1 / oh) / (1 / oh + 1 / oa)
    ll = lambda p: -np.mean(m.y * np.log(p) + (1 - m.y) * np.log(1 - p))  # noqa: E731
    print(f"1. tennisdata.app vs Kaggle odds on {len(m):,} joined ATP matches: log loss {ll(m.p_home):.4f} vs {ll(pk):.4f}, "
          f"mean |Δp| {np.abs(m.p_home - pk).mean():.4f}, corr {np.corrcoef(m.p_home, pk)[0, 1]:.4f}, "
          f"margin {m.margin.mean():.2%} vs {(1 / oh + 1 / oa - 1).mean():.2%}")
    print("   -> the same price (same source/time). No timing information; E008 still needs our own snapshots.")


def check_markets(td: pd.DataFrame) -> None:
    t = td[td.has_odds].copy()
    qual = t.tournament.str.contains("Qualif")
    t["market"] = np.where(t.tour_type_human == "ATP Chall", np.where(qual, "Challenger qualifying", "Challenger main"),
                           np.where(qual, "ATP qualifying", "ATP main"))
    t = t[t.tour_type_human != "ATP Exhib"]
    t["ll"] = -(t.y * np.log(t.p_home) + (1 - t.y) * np.log(1 - t.p_home))
    t["fav_p"], t["fav_won"] = np.maximum(t.p_home, 1 - t.p_home), (t.p_home > 0.5) == (t.y == 1)
    g = t.groupby("market").agg(matches=("ll", "size"), log_loss=("ll", "mean"), margin=("margin", "mean"),
                                fav_implied=("fav_p", "mean"), fav_won=("fav_won", "mean"))
    g["fav_bias_pts"] = 100 * (g.fav_won - g.fav_implied)
    print("\n2. Bookmaker by market (2021-2026):")
    print(g.round(4).to_string())
    print("   -> higher margins below the main tour; prices stay calibrated; favourites win slightly more than implied.")


def check_elo() -> None:
    html = (SRC / "Tennis Abstract_ ATP Elo Ratings.html").read_text(encoding="utf-8", errors="ignore")
    asof = re.search(r"Last update: ([\d-]+)", html)
    t = max(pd.read_html(io.StringIO(html)), key=len)
    t.columns = [c.replace("\xa0", " ") for c in t.columns]
    t = t[pd.to_numeric(t.Elo, errors="coerce").notna()].assign(Elo=lambda d: d.Elo.astype(float))
    ours = pd.read_csv(ROOT / "state" / "atp_ratings.csv")
    ours["k"] = [f"{norm(s)}|{norm(i)[:1]}" for s, _, i in (p.rpartition(" ") for p in ours.player)]
    rows = []
    for name, elo in zip(t.Player.astype(str).str.replace("\xa0", " "), t.Elo):
        w = name.split()
        keys = {f"{norm(' '.join(w[i:]))}|{norm(w[0])[:1]}" for i in range(1, len(w))}
        hit = ours[ours.k.isin(keys)]
        if len(hit) == 1:
            rows.append({"player": name, "ta_elo": elo, "our_elo": hit.elo.iloc[0]})
    m = pd.DataFrame(rows)
    top = m.nlargest(100, "ta_elo")
    slope, icpt = np.polyfit(m.ta_elo, m.our_elo, 1)
    m["diff"] = m.our_elo - (icpt + slope * m.ta_elo)
    print(f"\n3. Our Elo vs tennisabstract (theirs as of {asof.group(1) if asof else '?'}; {len(m)} players matched):")
    print(f"   rank correlation on their top 100: {top[['ta_elo', 'our_elo']].corr(method='spearman').iloc[0, 1]:.3f}; "
          f"our scale = {slope:.2f} × theirs (> 1 = ours more spread out)")
    print("   biggest disagreements (ours minus what theirs implies):")
    print(m.reindex(m["diff"].abs().sort_values(ascending=False).index).head(10).round(0).to_string(index=False))


if __name__ == "__main__":
    td = load_tennisdata()
    print(f"tennisdata.app: {len(td):,} finished matches {td.date.min().date()} → {td.date.max().date()}; "
          f"{td.tour_type_human.value_counts().to_dict()}\n")
    check_odds_vs_kaggle(td)
    check_markets(td)
    check_elo()
