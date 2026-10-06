"""Elo over time + recent form, for the dashboard's Ratings page.

Replays the same Elo models the live job uses and records every rating after every match:

    state/epl_elo_history.csv   date, team, elo, kind     (current EPL teams, 2024/25 onward; kind = match | reset)
    state/atp_elo_history.csv   date, player, elo, surface_elo   (top active players, 2025 onward)
    state/epl_form.csv          team, pos, played, pts, last5, last10, pts10
    state/atp_form.csv          player, last10, wins10, matches_365

Ratings are stored at match granularity (one row per team/player per match), so the chart
shows every jump. Called from daily.py; can also be run on its own.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt
from elo import FootballElo, TennisElo

STATE = Path(__file__).parent / "state"
EPL_SINCE = "2024-07-01"
ATP_SINCE = "2025-01-01"
ATP_TOP = 40


def epl_history(df: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    elo = FootballElo(**params)
    rows = []
    for season, games in df.groupby("season", sort=True):
        elo.start_season(season, set(games.HomeTeam) | set(games.AwayTeam))
        first = games.date.min()
        if first >= pd.Timestamp(EPL_SINCE):  # season reset is a visible step on the chart
            rows += [{"date": first - pd.Timedelta(days=1), "team": t, "elo": elo.ratings[t], "kind": "reset"}
                     for t in elo.season_teams]
        for g in games.itertuples():
            elo.update(g.HomeTeam, g.AwayTeam, int(g.FTHG), int(g.FTAG))
            if g.date >= pd.Timestamp(EPL_SINCE):
                rows += [{"date": g.date, "team": t, "elo": elo.ratings[t], "kind": "match"} for t in (g.HomeTeam, g.AwayTeam)]
    hist = pd.DataFrame(rows)
    hist = hist[hist.team.isin(elo.season_teams)]

    cur = df[df.season == df.season.max()]
    table = []
    for t in sorted(elo.season_teams):
        def results(m):
            home = m.HomeTeam == t
            return np.where(home, m.result.map({"H": "W", "D": "D", "A": "L"}), m.result.map({"H": "L", "D": "D", "A": "W"}))
        mine = cur[(cur.HomeTeam == t) | (cur.AwayTeam == t)]
        r_season = results(mine)
        gd = int(np.where(mine.HomeTeam == t, mine.FTHG - mine.FTAG, mine.FTAG - mine.FTHG).sum())
        gf = int(np.where(mine.HomeTeam == t, mine.FTHG, mine.FTAG).sum())
        last = df[(df.HomeTeam == t) | (df.AwayTeam == t)].tail(10)
        r10 = results(last)
        pts = lambda r: int(3 * (r == "W").sum() + (r == "D").sum())
        table.append({"team": t, "played": len(mine), "pts": pts(r_season), "gd": gd, "gf": gf,
                      "last5": "".join(r10[-5:]), "last10": "".join(r10), "pts10": pts(r10)})
    form = pd.DataFrame(table).sort_values(["pts", "gd", "gf"], ascending=False).reset_index(drop=True)
    form.insert(1, "pos", form.index + 1)
    return hist, form


def atp_history(df: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    elo = TennisElo(**params)
    since = pd.Timestamp(ATP_SINCE)
    rows = []
    for d, a, b, srf, a_won in zip(df.date, df.Player_1, df.Player_2, df.Surface, df.p1_won):
        w, l = (a, b) if a_won else (b, a)
        elo.update(w, l, srf)
        if d >= since:
            rows += [{"date": d, "player": p, "elo": elo.overall[p], "surface": srf, "surface_elo": elo.surface[(p, srf)]}
                     for p in (a, b)]
    hist = pd.DataFrame(rows)
    recent = df[df.date >= df.date.max() - pd.Timedelta(days=365)]
    active = set(recent.Player_1) | set(recent.Player_2)
    top = sorted(active, key=lambda p: -elo.overall[p])[:ATP_TOP]
    hist = hist[hist.player.isin(top)]

    form = []
    for p in top:
        m = df[(df.Player_1 == p) | (df.Player_2 == p)].tail(10)
        r = np.where(m.Winner == p, "W", "L")
        form.append({"player": p, "elo": round(elo.overall[p], 1), "last10": "".join(r), "wins10": int((r == "W").sum()),
                     "matches_365": int(((recent.Player_1 == p) | (recent.Player_2 == p)).sum())})
    return hist, pd.DataFrame(form)


def write_all(epl_df: pd.DataFrame, epl_params: dict, atp_df: pd.DataFrame, atp_params: dict) -> None:
    STATE.mkdir(exist_ok=True)
    eh, ef = epl_history(epl_df, epl_params)
    ah, af = atp_history(atp_df, atp_params)
    eh.assign(date=eh.date.dt.date, elo=eh.elo.round(1)).to_csv(STATE / "epl_elo_history.csv", index=False)
    ef.to_csv(STATE / "epl_form.csv", index=False)
    ah.assign(date=ah.date.dt.date, elo=ah.elo.round(1), surface_elo=ah.surface_elo.round(1)).to_csv(
        STATE / "atp_elo_history.csv", index=False)
    af.to_csv(STATE / "atp_form.csv", index=False)


if __name__ == "__main__":
    import daily

    write_all(bt.load_epl(), daily.EPL_PARAMS, bt.load_atp(daily.ATP_RECENT), daily.ATP_PARAMS)
    for f in ["epl_elo_history", "epl_form", "atp_elo_history", "atp_form"]:
        print(f, len(pd.read_csv(STATE / f"{f}.csv")), "rows")
