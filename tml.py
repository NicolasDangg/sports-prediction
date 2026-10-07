"""Tennis on TennisMyLife data (E009): ratings and pre-match features from every level of the game.

TennisMyLife (fetch_data.py tml) publishes the ATP main tour, challengers, qualifying and the
tournaments in progress, with stable player IDs and serve/return stats. Two things come out of
one walk through that history, in match order, always BEFORE updating with the match itself:

  replay()      -> for every match: both players' Elo (overall, surface), ranking, form, rest,
                   experience and decayed serve/return rates, as known before the match
  link_kaggle() -> which TML match each row of our odds data (Kaggle / live results) is, so the
                   models can be scored on exactly the matches we bet on

Elo differs from elo_v0 in two ways (both chosen on train years in E009):
  - results from lower levels (challengers, qualifying) can feed the ratings,
  - after a long break (> GAP_DAYS) a rating shrinks toward 1500 with a chosen half-life, so an
    injured or absent player isn't priced as if nothing happened.
"""

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from elo import expected_score
from strategies import logit

TML = Path(__file__).parent / "data" / "tml"
ROUND_ORDER = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3, "RR": 4, "R128": 5, "R64": 6, "R32": 7, "R16": 8,
               "QF": 9, "SF": 10, "BR": 11, "F": 12}
GAP_DAYS = 45  # a break longer than this counts as an absence
STAT_DECAY = 0.95  # serve/return totals: each older match counts 5% less
STAT_MIN = 3  # fewer prior matches with stats -> rates missing
STATS = ["serve_won", "return_won", "total_won", "ace_rate", "df_rate", "first_in", "bp_saved", "bp_conv"]
SURFACES = ("Hard", "Clay", "Grass")


# ------------------------------------------------------------------ loading


def load(root: Path = TML) -> pd.DataFrame:
    """Every TML match, in the order they were played. `level`: main / chall / qual."""
    frames = []
    for f in sorted(root.glob("*.csv")):
        name = f.name
        level = "qual" if "quali" in name else "chall" if "challenger" in name else "main"
        d = pd.read_csv(f, low_memory=False, dtype={"winner_id": str, "loser_id": str, "tourney_id": str})
        d["level"] = level
        frames.append(d)
    s = pd.concat(frames, ignore_index=True)
    s = s[s.winner_id.notna() & s.loser_id.notna()]
    s.loc[s["round"].isin(["Q1", "Q2", "Q3", "Q4"]), "level"] = "qual"  # (not QF!)
    s = s.drop_duplicates(["tourney_id", "round", "winner_id", "loser_id"], keep="first")
    stat_cols = [f"{p}_{c}" for p in ("w", "l") for c in ("ace", "df", "svpt", "1stIn", "1stWon", "2ndWon", "SvGms", "bpSaved", "bpFaced")]
    s[stat_cols] = s[stat_cols].apply(pd.to_numeric, errors="coerce")  # a few files store them as text
    s["tourney_date"] = pd.to_datetime(s.tourney_date.astype(int).astype(str), format="%Y%m%d")
    s["round_no"] = s["round"].map(ROUND_ORDER).fillna(6)
    s["surface"] = s.surface.where(s.surface.isin(SURFACES), "Hard")  # carpet / missing -> hard
    s["score"] = s.score.astype(str)
    s["completed"] = ~s.score.str.contains("W/O|DEF|unfinished", case=False, na=False)
    return s.sort_values(["tourney_date", "tourney_id", "round_no", "match_num"], kind="stable").reset_index(drop=True)


# -------------------------------------------------------------- the replay


@dataclass(frozen=True)
class EloConfig:
    levels: tuple[str, ...] = ("main", "chall", "qual")
    half_life: float | None = 365.0  # days; None = no shrink after a break
    k_scale: float = 200.0
    k_offset: float = 5.0
    k_shape: float = 0.4
    surface_weight: float = 0.5


class Replay:
    """Walks the history once. `pre` holds one dict per match with both players' pre-match state."""

    def __init__(self, cfg: EloConfig, with_features: bool = True):
        self.cfg, self.with_features = cfg, with_features
        self.overall: dict[str, float] = defaultdict(lambda: 1500.0)
        self.surf: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
        self.n: dict[str, int] = defaultdict(int)
        self.n_surf: dict[tuple[str, str], int] = defaultdict(int)
        self.last: dict[str, pd.Timestamp] = {}
        self.recent: dict[str, list[int]] = defaultdict(list)
        self.tot: dict[str, defaultdict] = defaultdict(lambda: defaultdict(float))
        self.rank: dict[str, tuple[float, float]] = {}  # latest (ranking, ranking points) seen per player

    def _k(self, n: int) -> float:
        c = self.cfg
        return c.k_scale / (n + c.k_offset) ** c.k_shape

    def _absence(self, pid: str, date: pd.Timestamp) -> int:
        """Shrink toward 1500 after a long break; returns the days since the last match."""
        if pid not in self.last:
            return -1
        gap = (date - self.last[pid]).days
        if self.cfg.half_life and gap > GAP_DAYS:
            f = 0.5 ** (gap / self.cfg.half_life)
            self.overall[pid] = 1500 + (self.overall[pid] - 1500) * f
            for s in SURFACES:
                if (pid, s) in self.surf:
                    self.surf[(pid, s)] = 1500 + (self.surf[(pid, s)] - 1500) * f
        return gap

    def prob(self, a: str, b: str, surface: str) -> float:
        w = self.cfg.surface_weight
        d = (1 - w) * (self.overall[a] - self.overall[b]) + w * (self.surf[(a, surface)] - self.surf[(b, surface)])
        return expected_score(d)

    def rates(self, pid: str) -> dict:
        t = self.tot[pid]
        if t["n"] < STAT_MIN or t["svpt"] <= 0 or t["ret_pts"] <= 0:
            return {k: np.nan for k in STATS}
        return {"serve_won": t["sv_won"] / t["svpt"], "return_won": t["ret_won"] / t["ret_pts"],
                "total_won": (t["sv_won"] + t["ret_won"]) / (t["svpt"] + t["ret_pts"]),
                "ace_rate": t["ace"] / t["svpt"], "df_rate": t["df"] / t["svpt"], "first_in": t["first_in"] / t["svpt"],
                "bp_saved": t["bp_saved"] / t["bp_faced"] if t["bp_faced"] > 0 else np.nan,
                "bp_conv": t["bp_won"] / t["bp_chances"] if t["bp_chances"] > 0 else np.nan}

    def _add_stats(self, pid: str, me: dict, opp: dict) -> None:
        t = self.tot[pid]
        for k in list(t):
            if k != "n":
                t[k] *= STAT_DECAY
        t["n"] += 1
        t["svpt"] += me["svpt"]
        t["sv_won"] += me["1stWon"] + me["2ndWon"]
        t["first_in"] += me["1stIn"]
        t["ace"] += me["ace"]
        t["df"] += me["df"]
        t["bp_saved"] += me["bpSaved"]
        t["bp_faced"] += me["bpFaced"]
        t["ret_pts"] += opp["svpt"]
        t["ret_won"] += opp["svpt"] - opp["1stWon"] - opp["2ndWon"]
        t["bp_chances"] += opp["bpFaced"]
        t["bp_won"] += opp["bpFaced"] - opp["bpSaved"]

    def player_state(self, pid: str, surface: str, gap: int) -> dict:
        r = self.recent[pid]
        st = {"elo": self.overall[pid], "surface_elo": self.surf[(pid, surface)], "matches": self.n[pid],
              "form10": np.mean(r) if r else 0.5, "rust": min(gap, 365) if gap >= 0 else np.nan}
        if self.with_features:
            st.update(self.rates(pid))
            st["stat_n"] = self.tot[pid]["n"]
        return st

    def run(self, s: pd.DataFrame) -> pd.DataFrame:
        cols = ["svpt", "1stIn", "1stWon", "2ndWon", "ace", "df", "bpSaved", "bpFaced"]
        has = (s[[f"{p}_{c}" for p in ("w", "l") for c in cols]].notna().all(axis=1) & (s.w_svpt > 0) & (s.l_svpt > 0)).to_numpy()
        out = []
        for i, r in enumerate(s.itertuples()):
            w, l, srf = r.winner_id, r.loser_id, r.surface
            gw, gl = self._absence(w, r.tourney_date), self._absence(l, r.tourney_date)
            rec = {"idx": r.Index, "p_w": self.prob(w, l, srf)}
            if self.with_features:
                rec.update({f"w_{k}": v for k, v in self.player_state(w, srf, gw).items()})
                rec.update({f"l_{k}": v for k, v in self.player_state(l, srf, gl).items()})
            out.append(rec)
            # ---- update after the match
            if r.level in self.cfg.levels and r.completed:
                e = expected_score(self.overall[w] - self.overall[l])
                kw, kl = self._k(self.n[w]), self._k(self.n[l])
                self.overall[w] += kw * (1 - e)
                self.overall[l] -= kl * (1 - e)
                e = expected_score(self.surf[(w, srf)] - self.surf[(l, srf)])
                kw, kl = self._k(self.n_surf[(w, srf)]), self._k(self.n_surf[(l, srf)])
                self.surf[(w, srf)] += kw * (1 - e)
                self.surf[(l, srf)] -= kl * (1 - e)
                self.n[w] += 1
                self.n[l] += 1
                self.n_surf[(w, srf)] += 1
                self.n_surf[(l, srf)] += 1
            if r.completed:
                self.recent[w] = (self.recent[w] + [1])[-10:]
                self.recent[l] = (self.recent[l] + [0])[-10:]
            self.last[w] = self.last[l] = r.tourney_date
            for pid, rk, pts in ((w, r.winner_rank, r.winner_rank_points), (l, r.loser_rank, r.loser_rank_points)):
                rk, pts = pd.to_numeric(rk, errors="coerce"), pd.to_numeric(pts, errors="coerce")
                if pd.notna(rk):
                    self.rank[pid] = (float(rk), float(pts) if pd.notna(pts) else 1.0)
            if self.with_features and has[i]:
                me = {c: getattr(r, f"w_{c}") for c in cols}
                op = {c: getattr(r, f"l_{c}") for c in cols}
                self._add_stats(w, me, op)
                self._add_stats(l, op, me)
        return pd.DataFrame(out).set_index("idx")


def replay(s: pd.DataFrame, cfg: EloConfig, with_features: bool = True) -> tuple[pd.DataFrame, Replay]:
    rp = Replay(cfg, with_features)
    return rp.run(s), rp


# ------------------------------------------------------------------ features

DIFFS = ["elo_diff", "surface_elo_diff", "rank_ratio", "points_ratio", "form10_diff", "experience_diff", "rust_diff",
         "elo_logit"] + [f"{s}_diff" for s in STATS] + ["serve_vs_return", "stat_n_diff"]
FEATURES = DIFFS + ["best_of_5", "surface_clay", "surface_grass"]


# ------------------------------------------------------------------ features


def features(s: pd.DataFrame, pre: pd.DataFrame) -> pd.DataFrame:
    """One row per TML match, P1 = winner, P2 = loser (mirrored later). All values known before the match."""
    w = lambda k: pre[f"w_{k}"].to_numpy(float)  # noqa: E731
    l = lambda k: pre[f"l_{k}"].to_numpy(float)  # noqa: E731,E741
    rank = lambda c: pd.to_numeric(s[c], errors="coerce").to_numpy(float)  # noqa: E731
    rw, rl = np.nan_to_num(rank("winner_rank"), nan=2000), np.nan_to_num(rank("loser_rank"), nan=2000)
    pw, pl = np.nan_to_num(rank("winner_rank_points"), nan=1), np.nan_to_num(rank("loser_rank_points"), nan=1)
    f = pd.DataFrame({
        "elo_diff": w("elo") - l("elo"), "surface_elo_diff": w("surface_elo") - l("surface_elo"),
        "rank_ratio": np.log(np.maximum(rl, 1)) - np.log(np.maximum(rw, 1)),
        "points_ratio": np.log(np.maximum(pw, 1)) - np.log(np.maximum(pl, 1)),
        "form10_diff": w("form10") - l("form10"), "experience_diff": np.log1p(w("matches")) - np.log1p(l("matches")),
        "rust_diff": np.nan_to_num(w("rust")) - np.nan_to_num(l("rust")),
        "elo_logit": logit(pre.p_w.to_numpy()),
        **{f"{k}_diff": w(k) - l(k) for k in STATS},
        "serve_vs_return": (w("serve_won") - l("return_won")) - (l("serve_won") - w("return_won")),
        "stat_n_diff": np.log1p(w("stat_n")) - np.log1p(l("stat_n")),
        "best_of_5": (pd.to_numeric(s.best_of, errors="coerce") == 5).astype(int).to_numpy(),
        "surface_clay": (s.surface == "Clay").astype(int).to_numpy(),
        "surface_grass": (s.surface == "Grass").astype(int).to_numpy(),
    }, index=s.index)
    return f


def flipped(x: pd.DataFrame) -> pd.DataFrame:
    f = x.copy()
    f[DIFFS] = -f[DIFFS]
    return f


def mirrored(x: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    return pd.concat([x, flipped(x)], ignore_index=True), np.r_[np.ones(len(x)), np.zeros(len(x))]


def sym_proba(model, x: pd.DataFrame) -> np.ndarray:
    """Average over both player orders, so swapping the players gives exactly 1 - p."""
    return (model.predict_proba(x)[:, 1] + 1 - model.predict_proba(flipped(x))[:, 1]) / 2

# ------------------------------------------------------------- the forecaster (E009 b)

# Chosen in E009 on 2018-19 (16 variants); refitted each morning on every completed main-tour match since 2010.
FORECASTER = dict(max_depth=2, learning_rate=0.1, min_samples_leaf=50, max_iter=258)
# Chosen in E009 (a) on 2010-2019 (18 variants): every level feeds the ratings, no shrink after absences.
CHOSEN_ELO = EloConfig(levels=("main", "chall", "qual"), half_life=None, k_scale=200.0)
TRAIN_FROM = "2010-01-01"


class LiveForecaster:
    """Everything the morning job needs, built once per run (~20 s): ratings, the refitted model, name -> ID."""

    def __init__(self, history: pd.DataFrame):
        self.s = load()
        pre, self.rp = replay(self.s, CHOSEN_ELO, with_features=True)
        self.model = fit_forecaster(self.s, pre)
        self.ids = player_ids(history, self.s, link_kaggle(history, self.s))

    def predict(self, a: str, b: str, surface: str, best_of: int, now: pd.Timestamp) -> tuple[float, float] | None:
        """(forecaster P(a wins), TML Elo P(a wins)) for history names a, b; None if either player is unknown."""
        ia, ib = self.ids.get(a), self.ids.get(b)
        if ia is None or ib is None or ia == ib:
            return None
        x = live_features(self.rp, ia, ib, surface, best_of, now)
        return float(sym_proba(self.model, x)[0]), float(self.rp.prob(ia, ib, surface if surface in SURFACES else "Hard"))


def fit_forecaster(s: pd.DataFrame, pre: pd.DataFrame):
    from sklearn.ensemble import HistGradientBoostingClassifier
    rows = (s.level == "main") & s.completed & (s.tourney_date >= TRAIN_FROM)
    x, y = mirrored(features(s, pre)[rows][FEATURES])
    return HistGradientBoostingClassifier(early_stopping=False, random_state=9, **FORECASTER).fit(x, y)


def live_features(rp: Replay, a: str, b: str, surface: str, best_of: int, now: pd.Timestamp) -> pd.DataFrame:
    """The same features as features(), for an upcoming match, P1 = a, from the replay's end state."""
    surface = surface if surface in SURFACES else "Hard"
    sa, sb = (rp.player_state(p, surface, (now.tz_localize(None) - rp.last[p]).days if p in rp.last else -1) for p in (a, b))
    (ra, pa), (rb, pb) = rp.rank.get(a, (2000.0, 1.0)), rp.rank.get(b, (2000.0, 1.0))
    v = lambda st, k: float(st.get(k, np.nan))  # noqa: E731
    row = {
        "elo_diff": v(sa, "elo") - v(sb, "elo"), "surface_elo_diff": v(sa, "surface_elo") - v(sb, "surface_elo"),
        "rank_ratio": np.log(max(rb, 1)) - np.log(max(ra, 1)), "points_ratio": np.log(max(pa, 1)) - np.log(max(pb, 1)),
        "form10_diff": v(sa, "form10") - v(sb, "form10"),
        "experience_diff": np.log1p(v(sa, "matches")) - np.log1p(v(sb, "matches")),
        "rust_diff": np.nan_to_num(v(sa, "rust")) - np.nan_to_num(v(sb, "rust")),
        "elo_logit": float(logit(rp.prob(a, b, surface))),
        **{f"{k}_diff": v(sa, k) - v(sb, k) for k in STATS},
        "serve_vs_return": (v(sa, "serve_won") - v(sb, "return_won")) - (v(sb, "serve_won") - v(sa, "return_won")),
        "stat_n_diff": np.log1p(v(sa, "stat_n")) - np.log1p(v(sb, "stat_n")),
        "best_of_5": int(best_of == 5), "surface_clay": int(surface == "Clay"), "surface_grass": int(surface == "Grass"),
    }
    return pd.DataFrame([row])[FEATURES]


# --------------------------------------------------- linking to the odds data


def norm(x) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", x)


def kaggle_keys(name: str) -> set[str]:
    """'Del Potro J.M.' -> {'delpotro|j'}; a hyphenated surname also tries its first part."""
    toks = str(name).split()
    i = len(toks)
    while i > 1 and re.fullmatch(r"[A-Z][a-z]?\.?([A-Z]\.?)*", toks[i - 1]):
        i -= 1
    ini = norm(toks[i] if i < len(toks) else "")[:1]
    surname = " ".join(toks[:i])
    return {f"{norm(surname)}|{ini}", f"{norm(surname.split('-')[0])}|{ini}"}


def full_name_keys(name: str) -> set[str]:
    """'Roberto Bautista Agut' -> {'bautista|r', 'bautistaagut|r', 'agut|r'}: any run of later words."""
    w = str(name).split()
    if len(w) < 2:
        return {f"{norm(name)}|"}
    ini = norm(w[0])[:1]
    return {f"{norm(' '.join(w[i:j]))}|{ini}" for i in range(1, len(w)) for j in range(i + 1, len(w) + 1)}


def link_kaggle(df: pd.DataFrame, s: pd.DataFrame) -> pd.Series:
    """Kaggle row index -> TML row index: same winner and loser (name keys), within the tournament's dates."""
    main = s[s.level == "main"]
    sk = pd.DataFrame([(i, wk, lk) for i, w, l in zip(main.index, main.winner_name, main.loser_name)
                       for wk in full_name_keys(w) for lk in full_name_keys(l)], columns=["s_idx", "wk", "lk"])
    sk["tourney_date"] = s.loc[sk.s_idx, "tourney_date"].to_numpy()
    loser = np.where(df.p1_won, df.Player_2, df.Player_1)
    kg = pd.DataFrame([(i, wk, lk, d) for i, w, l, d in zip(df.index, df.Winner, loser, df.date)
                       for wk in kaggle_keys(w) for lk in kaggle_keys(l)], columns=["k_idx", "wk", "lk", "date"])
    m = kg.merge(sk, on=["wk", "lk"])
    m["days"] = (m.date - m.tourney_date).dt.days
    m = m[m.days.between(-3, 20)].sort_values("days", key=abs)
    return m.drop_duplicates("k_idx").drop_duplicates("s_idx").set_index("k_idx").s_idx


def player_ids(df: pd.DataFrame, s: pd.DataFrame, link: pd.Series) -> dict[str, str]:
    """History name ('Sinner J.') -> TML player ID, learned from the linked matches (majority vote)."""
    k = df.loc[link.index]
    sm = s.loc[link.to_numpy()]
    loser = np.where(k.p1_won, k.Player_2, k.Player_1)
    pairs = pd.DataFrame({"name": np.concatenate([k.Winner.to_numpy(), loser]),
                          "pid": np.concatenate([sm.winner_id.to_numpy(), sm.loser_id.to_numpy()])})
    best = pairs.groupby(["name", "pid"]).size().reset_index(name="n").sort_values("n", ascending=False)
    return dict(best.drop_duplicates("name").set_index("name").pid)
