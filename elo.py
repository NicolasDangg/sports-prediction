"""Elo rating models for EPL and tennis.

Elo in one sentence: every team/player has a number; the gap between two numbers
predicts who wins; after the match, the winner takes points from the loser, and
an upset moves more points than an expected result.

    expected = 1 / (1 + 10 ** (-(rating_a - rating_b) / 400))
    rating_a += K * (actual - expected)      # actual: 1 win, 0.5 draw, 0 loss

A 400-point gap means the stronger side is expected to score ~91% of the points.
K controls how fast ratings react: high K = jumpy, low K = slow and stable.
"""

import math
from collections import defaultdict


def expected_score(diff: float) -> float:
    """Chance-like score for the side that is `diff` Elo points stronger."""
    return 1.0 / (1.0 + 10 ** (-diff / 400))


# --------------------------------------------------------------------------- EPL


class FootballElo:
    """Team Elo with home advantage, goal-difference weighting and season resets."""

    def __init__(self, k: float = 20, home_adv: float = 60, carryover: float = 0.8):
        self.k = k
        self.home_adv = home_adv  # home teams play as if they were this many points better
        self.carryover = carryover  # keep 80% of last season's distance from average
        self.ratings: dict[str, float] = {}
        self.season = None
        self.season_teams: set[str] = set()

    def start_season(self, season: str, teams: set[str]) -> None:
        """Between seasons: pull ratings back toward the mean (squads change) and
        give promoted teams the average rating of the relegated teams they replace."""
        if self.ratings:
            mean = sum(self.ratings[t] for t in self.season_teams) / len(self.season_teams)
            for t in self.season_teams:
                self.ratings[t] = mean + self.carryover * (self.ratings[t] - mean)
            relegated = self.season_teams - teams
            promoted_rating = (
                sum(self.ratings[t] for t in relegated) / len(relegated) if relegated else mean - 100
            )
            for t in teams - self.season_teams:
                self.ratings[t] = promoted_rating
        else:
            for t in teams:
                self.ratings[t] = 1500.0
        self.season = season
        self.season_teams = set(teams)

    def diff(self, home: str, away: str) -> float:
        """Rating gap from the home side's point of view, home advantage included."""
        return self.ratings[home] + self.home_adv - self.ratings[away]

    def update(self, home: str, away: str, home_goals: int, away_goals: int) -> None:
        actual = 1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
        expected = expected_score(self.diff(home, away))
        # Winning 4-0 says more than winning 1-0 (World Football Elo multiplier).
        gd = abs(home_goals - away_goals)
        mult = 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8
        delta = self.k * mult * (actual - expected)
        self.ratings[home] += delta
        self.ratings[away] -= delta


# ------------------------------------------------------------------------ Tennis


class TennisElo:
    """Player Elo with a separate rating per surface (clay/grass/hard specialists exist).

    New players' ratings move fast and veterans' move slowly: K shrinks as a player's
    match count grows (the FiveThirtyEight tennis formula).
    """

    def __init__(self, k_scale: float = 250, k_offset: float = 5, k_shape: float = 0.4,
                 surface_weight: float = 0.5):
        self.k_scale, self.k_offset, self.k_shape = k_scale, k_offset, k_shape
        self.surface_weight = surface_weight  # 0 = ignore surface, 1 = surface only
        self.overall: dict[str, float] = defaultdict(lambda: 1500.0)
        self.surface: dict[tuple[str, str], float] = defaultdict(lambda: 1500.0)
        self.n_overall: dict[str, int] = defaultdict(int)
        self.n_surface: dict[tuple[str, str], int] = defaultdict(int)

    def _k(self, n_matches: int) -> float:
        return self.k_scale / (n_matches + self.k_offset) ** self.k_shape

    def diff(self, a: str, b: str, surface: str) -> float:
        d_all = self.overall[a] - self.overall[b]
        d_srf = self.surface[(a, surface)] - self.surface[(b, surface)]
        return (1 - self.surface_weight) * d_all + self.surface_weight * d_srf

    def prob(self, a: str, b: str, surface: str) -> float:
        return expected_score(self.diff(a, b, surface))

    def update(self, winner: str, loser: str, surface: str) -> None:
        e = expected_score(self.overall[winner] - self.overall[loser])
        kw, kl = self._k(self.n_overall[winner]), self._k(self.n_overall[loser])
        self.overall[winner] += kw * (1 - e)
        self.overall[loser] -= kl * (1 - e)

        w, l = (winner, surface), (loser, surface)
        e = expected_score(self.surface[w] - self.surface[l])
        kw, kl = self._k(self.n_surface[w]), self._k(self.n_surface[l])
        self.surface[w] += kw * (1 - e)
        self.surface[l] -= kl * (1 - e)

        self.n_overall[winner] += 1
        self.n_overall[loser] += 1
        self.n_surface[w] += 1
        self.n_surface[l] += 1


def log_loss(probs_of_actual: list[float]) -> float:
    """Average of -ln(probability you gave to what actually happened). Lower is better.
    Saying 90% and being right costs 0.11; saying 90% and being wrong costs 2.30."""
    eps = 1e-12
    return -sum(math.log(max(p, eps)) for p in probs_of_actual) / len(probs_of_actual)
