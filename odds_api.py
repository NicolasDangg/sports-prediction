"""Thin client for The Odds API (https://the-odds-api.com), v4.

Costs on the free plan (500 credits/month):
  /sports            free
  /odds              1 credit per market per region  (we use 1 market x 1 region = 1)
  /scores?daysFrom   2 credits
Every response says how many credits are left; we print it so the agent can report it.
"""

import os
import statistics

import requests

BASE = "https://api.the-odds-api.com/v4"
REGION = "eu"  # European bookmakers, incl. Pinnacle (the sharpest book)


class OddsAPI:
    def __init__(self, api_key: str | None = None):
        self.key = api_key or os.environ.get("ODDS_API_KEY")
        if not self.key:
            raise RuntimeError("ODDS_API_KEY is not set (see .env.example)")
        self.remaining: str | None = None

    def _get(self, path: str, **params) -> list[dict]:
        resp = requests.get(f"{BASE}{path}", params={"apiKey": self.key, **params}, timeout=30)
        resp.raise_for_status()
        self.remaining = resp.headers.get("x-requests-remaining", self.remaining)
        return resp.json()

    def active_sports(self) -> list[dict]:
        return self._get("/sports")

    def active_atp_keys(self) -> list[dict]:
        """Tennis has one sport key per tournament (e.g. tennis_atp_shanghai_masters)."""
        return [s for s in self.active_sports()
                if s["key"].startswith("tennis_atp_") and s.get("active") and not s.get("has_outrights")]

    def odds(self, sport_key: str) -> list[dict]:
        return self._get(f"/sports/{sport_key}/odds", regions=REGION, markets="h2h", oddsFormat="decimal")

    def scores(self, sport_key: str, days_from: int = 3) -> list[dict]:
        return self._get(f"/sports/{sport_key}/scores", daysFrom=days_from)


def consensus_prices(event: dict) -> tuple[dict[str, float], int]:
    """Collapse all bookmakers' head-to-head prices for one event into one price per
    outcome: the median, i.e. a typical price you could actually get (not the best one,
    which would flatter our results). Returns ({outcome name: price}, number of books)."""
    prices: dict[str, list[float]] = {}
    n_books = 0
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            if market["key"] != "h2h":
                continue
            n_books += 1
            for o in market["outcomes"]:
                prices.setdefault(o["name"], []).append(float(o["price"]))
    return {name: statistics.median(p) for name, p in prices.items()}, n_books


def winner_from_scores(event: dict) -> str | None:
    """For a completed event, return the winner's name, 'Draw', or None if unknown."""
    if not event.get("completed") or not event.get("scores"):
        return None
    try:
        s = {x["name"]: float(x["score"]) for x in event["scores"]}
    except (TypeError, ValueError):
        return None
    (a, sa), (b, sb) = list(s.items())[:2]
    return a if sa > sb else b if sb > sa else "Draw"
