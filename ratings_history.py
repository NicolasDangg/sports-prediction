"""Elo over time + recent form, for the dashboard's Ratings page.

Replays the same Elo models the live job uses and records every rating after every match:

    state/epl_elo_history.csv   date, team, elo, kind     (current EPL teams, 2024/25 onward; kind = match | reset)
    state/atp_elo_history.csv   date, player, elo, surface_elo   (top active players, 2025 onward)
    state/epl_form.csv          team, pos, played, pts, last5, last10, pts10
    state/atp_form.csv          player, last10, wins10, matches_365
    state/epl_matches.csv       every EPL match since 2024/25: ratings before/after, model H/D/A probabilities
    state/atp_matches.csv       every 2025+ match of a top player: ratings before/after, model win probability, odds

Ratings are stored at match granularity (one row per team/player per match), so the chart
shows every jump. Called from daily.py; can also be run on its own.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt
from elo import FootballElo, TennisElo, expected_score

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


def epl_matches(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Every match since EPL_SINCE with both teams' ratings before/after and the model's
    pre-match H/D/A probabilities (same outcome model the live job fits on the train seasons)."""
    elo = FootballElo(**params)
    rows, diffs = [], np.empty(len(df))
    for season, games in df.groupby("season", sort=True):
        elo.start_season(season, set(games.HomeTeam) | set(games.AwayTeam))
        for i, g in games.iterrows():
            h, a = g.HomeTeam, g.AwayTeam
            diffs[i] = elo.diff(h, a)
            before = (elo.ratings[h], elo.ratings[a])
            elo.update(h, a, int(g.FTHG), int(g.FTAG))
            rows.append({"i": i, "season": season, "date": g.date.date(), "home": h, "away": a,
                         "hg": int(g.FTHG), "ag": int(g.FTAG), "result": g.result,
                         "home_before": round(before[0], 1), "away_before": round(before[1], 1),
                         "home_after": round(elo.ratings[h], 1), "away_after": round(elo.ratings[a], 1)})
    train = df.season.isin(bt.EPL_TRAIN).to_numpy()
    model = bt.fit_outcome_model(diffs[train], df.result[train].to_numpy())
    out = pd.DataFrame(rows)
    out = out[pd.to_datetime(out.date) >= pd.Timestamp(EPL_SINCE)]
    probs = bt.outcome_probs(model, diffs[out.i.to_numpy()]).round(4)
    return out.drop(columns="i").assign(p_home=probs.H.to_numpy(), p_draw=probs.D.to_numpy(), p_away=probs.A.to_numpy())


def atp_matches(df: pd.DataFrame, params: dict, players: set[str]) -> pd.DataFrame:
    """Every match since ATP_SINCE involving one of `players`, with ratings before/after,
    the model's pre-match probability for Player 1 (overall/surface blend) and the odds."""
    elo = TennisElo(**params)
    since = pd.Timestamp(ATP_SINCE)
    rows = []
    for r in df.itertuples():
        a, b, srf = r.Player_1, r.Player_2, r.Surface
        keep = r.date >= since and (a in players or b in players)
        if keep:
            before = (elo.overall[a], elo.overall[b])
            p1 = elo.prob(a, b, srf)
        w, l = (a, b) if r.p1_won else (b, a)
        elo.update(w, l, srf)
        if keep:
            rows.append({"date": r.date.date(), "tournament": r.Tournament, "series": r.Series, "round": r.Round,
                         "surface": srf, "p1": a, "p2": b, "winner": r.Winner,
                         "score": r.Score, "p1_before": round(before[0], 1), "p2_before": round(before[1], 1),
                         "p1_after": round(elo.overall[a], 1), "p2_after": round(elo.overall[b], 1),
                         "p1_prob": round(p1, 4), "odd_1": r.Odd_1, "odd_2": r.Odd_2})
    return pd.DataFrame(rows)


def write_all(epl_df: pd.DataFrame, epl_params: dict, atp_df: pd.DataFrame, atp_params: dict) -> None:
    STATE.mkdir(exist_ok=True)
    eh, ef = epl_history(epl_df, epl_params)
    ah, af = atp_history(atp_df, atp_params)
    eh.assign(date=eh.date.dt.date, elo=eh.elo.round(1)).to_csv(STATE / "epl_elo_history.csv", index=False)
    ef.to_csv(STATE / "epl_form.csv", index=False)
    ah.assign(date=ah.date.dt.date, elo=ah.elo.round(1), surface_elo=ah.surface_elo.round(1)).to_csv(
        STATE / "atp_elo_history.csv", index=False)
    af.to_csv(STATE / "atp_form.csv", index=False)
    epl_matches(epl_df, epl_params).to_csv(STATE / "epl_matches.csv", index=False)
    atp_matches(atp_df, atp_params, set(af.player)).to_csv(STATE / "atp_matches.csv", index=False)
    name_map(epl_df, atp_df).to_csv(STATE / "name_map.csv", index=False)


def name_map(epl_df: pd.DataFrame, atp_df: pd.DataFrame) -> pd.DataFrame:
    """Bookmaker spelling -> history name for every team/player in the ledger and today's
    forecasts, so the dashboard can attach bets and upcoming matches to a team/player page."""
    from names import epl_team, player_profiles, tennis_player

    teams = set(epl_df.HomeTeam) | set(epl_df.AwayTeam)
    profiles, since = player_profiles(atp_df), atp_df.date.max() - pd.Timedelta(days=365)
    seen: set[tuple[str, str]] = set()
    for f in ("ledger.csv", "predictions.csv"):
        if (STATE / f).exists():
            d = pd.read_csv(STATE / f, usecols=["sport", "match"])
            seen |= {(sp, n) for sp, m in zip(d.sport, d.match) for n in str(m).split(" v ")}
    rows = []
    for sport, api in sorted(seen):
        name = epl_team(api, teams) if sport == "epl" else tennis_player(api, profiles, since).name
        if name:
            rows.append({"sport": sport, "api_name": api, "name": name})
    return pd.DataFrame(rows, columns=["sport", "api_name", "name"])


if __name__ == "__main__":
    import daily

    write_all(bt.load_epl(), daily.EPL_PARAMS, bt.load_atp(daily.ATP_RECENT), daily.ATP_PARAMS)
    for f in ["epl_elo_history", "epl_form", "atp_elo_history", "atp_form", "epl_matches", "atp_matches", "name_map"]:
        print(f, len(pd.read_csv(STATE / f"{f}.csv")), "rows")
