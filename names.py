"""Different data sources spell the same team/player differently.
The Odds API says "Manchester City" / "Jannik Sinner"; our history says "Man City" / "Sinner J.".
If we got this wrong, Elo would treat them as brand-new 1500-rated unknowns."""

import difflib

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


def epl_team(name: str, known: set[str]) -> str | None:
    if name in known:
        return name
    if EPL_ALIASES.get(name) in known:
        return EPL_ALIASES[name]
    close = difflib.get_close_matches(name, known, n=1, cutoff=0.75)
    return close[0] if close else None


def tennis_player(full_name: str, known: set[str]) -> str:
    """'Alex de Minaur' -> 'De Minaur A.'; 'Felix Auger-Aliassime' -> 'Auger-Aliassime F.'.
    Try every first/last split and keep the one that exists in our history."""
    words = full_name.replace(".", "").split()
    candidates = []
    for k in range(1, len(words)):
        first, last = words[:k], words[k:]
        parts = [p for w in first for p in w.split("-")]  # Jan-Lennard -> Jan, Lennard
        initial_styles = [".".join(p[0] for p in parts) + ".", "-".join(p[0] for p in parts) + ".",
                          f"{first[0][0]}."]
        for surname in (" ".join(last), " ".join(w.capitalize() if w.islower() else w for w in last)):
            candidates += [f"{surname} {ini}" for ini in initial_styles]
    for c in candidates:
        if c in known:
            return c
    return candidates[0] if candidates else full_name  # unseen player: new 1500 rating
