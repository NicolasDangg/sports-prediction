"""Different data sources spell the same team/player differently.
The Odds API says "Manchester City" / "Jannik Sinner"; our history says "Man City" / "Sinner J.".

Getting this wrong is dangerous, not just noisy: a mismatched player gets a fresh 1500
rating, which manufactures fake betting edges and then corrupts ratings with real results.
So the tennis resolver refuses to guess. Anything it can't pin to exactly one recently
active history player comes back as "unknown", "ambiguous" or "stale", and is not bet on.
Manual fixes go in aliases.csv (sport, api_name, history_name).
"""

import csv
import difflib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ALIASES_FILE = Path(__file__).parent / "aliases.csv"

EPL_ALIASES = {
    "Manchester City": "Man City",
    "Manchester United": "Man United",
    "Newcastle United": "Newcastle",
    "Tottenham Hotspur": "Tottenham",
    "Wolverhampton Wanderers": "Wolves",
    "Brighton and Hove Albion": "Brighton",
    "West Ham United": "West Ham",
    "Nottingham Forest": "Nott'm Forest",
    "Leeds United": "Leeds",
    "Leicester City": "Leicester",
    "Ipswich Town": "Ipswich",
    "Luton Town": "Luton",
    "AFC Bournemouth": "Bournemouth",
    "Sheffield Utd": "Sheffield United",
    "Hull City": "Hull",
    "Coventry City": "Coventry",
    "Norwich City": "Norwich",
    "Cardiff City": "Cardiff",
    "Stoke City": "Stoke",
    "Swansea City": "Swansea",
    "West Bromwich Albion": "West Brom",
    "Huddersfield Town": "Huddersfield",
}


def load_aliases(sport: str) -> dict[str, str]:
    if not ALIASES_FILE.exists():
        return {}
    with ALIASES_FILE.open() as f:
        return {r["api_name"]: r["history_name"] for r in csv.DictReader(f) if r["sport"] == sport}


def epl_team(name: str, known: set[str]) -> str | None:
    if name in known:
        return name
    alias = load_aliases("epl").get(name) or EPL_ALIASES.get(name)
    if alias in known:
        return alias
    close = difflib.get_close_matches(name, known, n=1, cutoff=0.75)
    return close[0] if close else None


# ---------------------------------------------------------------------- tennis


@dataclass(frozen=True)
class Profile:
    matches: int
    last: pd.Timestamp


@dataclass(frozen=True)
class Resolved:
    api_name: str
    name: str | None  # history name we trust, or None
    status: str  # alias | matched | unknown | ambiguous | stale
    candidates: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return self.name is not None


def player_profiles(df: pd.DataFrame) -> dict[str, Profile]:
    """Match count and last appearance for every player in the history."""
    both = pd.concat([df[["Player_1", "date"]].set_axis(["p", "date"], axis=1),
                      df[["Player_2", "date"]].set_axis(["p", "date"], axis=1)])
    g = both.groupby("p").date.agg(["count", "max"])
    return {p: Profile(int(c), m) for p, c, m in zip(g.index, g["count"], g["max"])}


def _initials(given: list[str]) -> list[str]:
    """Ways the history abbreviates given names: 'J.L.', 'J-L.', 'J.', 'Zh.', 'D.' (middle name)."""
    parts = [p for w in given for p in w.split("-") if p]
    if not parts:
        return []
    styles = [".".join(p[0] for p in parts) + ".", "-".join(p[0] for p in parts) + "."]
    for p in parts:  # each given name alone, plus 2-3 letter prefixes used to split namesakes
        styles += [f"{p[0]}.", f"{p[:2]}.", f"{p[:3]}."]
    return list(dict.fromkeys(styles))


def tennis_candidates(full_name: str) -> list[tuple[int, str]]:
    """(tier, history-style name) guesses. Tier 0: given names first (most names).
    Tier 1: surname first, as the API writes many Chinese names ('Bu Yunchaokete' -> 'Bu Y.')."""
    words = full_name.replace(".", "").split()
    out: list[tuple[int, str]] = []
    for k in range(1, len(words)):
        for tier, given, surname in ((0, words[:k], words[k:]), (1, words[k:], words[:k])):
            for sur in dict.fromkeys((" ".join(surname), " ".join(w.capitalize() for w in surname))):
                out += [(tier, f"{sur} {ini}") for ini in _initials(given)]
    return list(dict.fromkeys(out))


def tennis_player(full_name: str, profiles: dict[str, Profile], active_since: pd.Timestamp,
                  aliases: dict[str, str] | None = None) -> Resolved:
    aliases = load_aliases("atp") if aliases is None else aliases
    if full_name in aliases:
        return Resolved(full_name, aliases[full_name], "alias")

    hits = [(tier, n) for tier, n in tennis_candidates(full_name) if n in profiles]
    names = tuple(dict.fromkeys(n for _, n in hits))
    if not hits:
        return Resolved(full_name, None, "unknown")

    recent = [(t, n) for t, n in hits if profiles[n].last >= active_since]
    if not recent:
        return Resolved(full_name, None, "stale", names)  # only long-inactive namesakes: don't trust
    best_tier = min(t for t, _ in recent)
    top = list(dict.fromkeys(n for t, n in recent if t == best_tier))
    if len(top) == 1:
        return Resolved(full_name, top[0], "matched", names)
    return Resolved(full_name, None, "ambiguous", tuple(top))


STALE_DAYS = 180  # a gap this long (injury, suspension) freezes a rating: we don't know how the player has changed
RETURN_MATCHES = 5  # matches back before the rating is trusted again


def stale_ratings(df: pd.DataFrame, gap_days: int = STALE_DAYS, min_back: int = RETURN_MATCHES) -> dict[str, str]:
    """Players whose Elo is too old to bet on, with the reason. Separate from identity: an alias
    can say who someone is, but not that their rating still describes them. Stale = no match in
    the last gap_days, or back from such a gap with fewer than min_back matches since."""
    today = df.date.max()
    both = pd.concat([df[["Player_1", "date"]].set_axis(["p", "date"], axis=1),
                      df[["Player_2", "date"]].set_axis(["p", "date"], axis=1)])
    out = {}
    for p, dates in both.groupby("p").date:
        d = dates.sort_values().reset_index(drop=True)
        if (today - d.iloc[-1]).days > gap_days:
            out[p] = f"last match {d.iloc[-1].date()}"
            continue
        gaps = d.diff().dt.days
        returns = gaps[gaps > gap_days].index
        if len(returns) and len(d) - returns[-1] < min_back:
            out[p] = f"back from a {int(gaps[returns[-1]])}-day break, {len(d) - returns[-1]} match(es) since"
    return out
