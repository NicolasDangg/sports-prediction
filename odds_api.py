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
# Betting exchanges quote prices before their commission (~2-5%), so a "best price" there isn't
# what you'd actually be paid. Excluded from the best bookmaker price (E012).
EXCHANGES = {"betfair_ex_eu", "betfair_ex_uk", "betfair_ex_au", "matchbook", "smarkets"}


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


def quotes(event: dict) -> dict[str, list[dict]]:
    """Every bookmaker's head-to-head price for one event: {outcome: [{book, price, at}, ...]}."""
    out: dict[str, list[dict]] = {}
    for book in event.get("bookmakers", []):
        for market in book.get("markets", []):
            if market["key"] != "h2h":
                continue
            at = market.get("last_update") or book.get("last_update", "")
            for o in market["outcomes"]:
                out.setdefault(o["name"], []).append({"book": book.get("key", "?"), "price": float(o["price"]), "at": at})
    return out


def price_summary(event: dict) -> tuple[dict[str, dict], int]:
    """Per outcome:
      median   consensus price across books: the benchmark for "what the market thinks"
      exec     a REAL quote to paper-bet at: the highest actual price that is <= the median,
               i.e. a typical, conservative price someone was really offering (never the best)
      pinnacle Pinnacle's price if it was quoted (the sharpest book), for reference
      best     the highest real bookmaker price (exchanges excluded), with its book and time (E012)
    Returns ({outcome: summary}, number of books)."""
    q = quotes(event)
    n_books = max((len(v) for v in q.values()), default=0)
    summary = {}
    for name, qs in q.items():
        med = statistics.median(x["price"] for x in qs)
        below = [x for x in qs if x["price"] <= med] or qs
        ex = max(below, key=lambda x: x["price"])
        pin = next((x["price"] for x in qs if x["book"] == "pinnacle"), None)
        books = [x for x in qs if x["book"] not in EXCHANGES] or qs
        top = max(books, key=lambda x: x["price"])
        summary[name] = {"median": round(med, 3), "exec": ex["price"], "exec_book": ex["book"],
                         "exec_at": ex["at"], "pinnacle": pin,
                         "best": top["price"], "best_book": top["book"], "best_at": top["at"]}
    return summary, n_books


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
