"""Squads, player stats, injuries, fixtures and coaches for the EPL team pages and FPL.

Sources (both free and public, no key):
  - Fantasy Premier League API: every player's season stats incl. expected goals/assists (xG/xA),
    injury status + news, price, ownership, FPL's expected points for the next gameweek, and fixtures
    with FPL difficulty ratings. Player photos come from the Premier League's public image server.
  - Wikidata: each club's current head coach and a Wikimedia Commons photo.

Writes:
  state/fpl_players.csv    one row per player (current squads)
  state/fpl_fixtures.csv   next 6 fixtures per team with difficulty (1 easy … 5 hard)
  state/coaches.csv        team, coach, since, image

    uv run python fpl.py
"""

import time
from pathlib import Path

import pandas as pd
import requests

STATE = Path(__file__).parent / "state"
FPL = "https://fantasy.premierleague.com/api"
PHOTO = "https://resources.premierleague.com/premierleague/photos/players/110x140/p{code}.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (personal research; sports-prediction)"}

# FPL short names -> the names our match history uses (football-data.co.uk)
FPL_TO_HISTORY = {"Man Utd": "Man United", "Spurs": "Tottenham", "Coventry City": "Coventry", "Hull City": "Hull",
                  "Ipswich Town": "Ipswich", "Leeds United": "Leeds", "Nottingham Forest": "Nott'm Forest",
                  "Newcastle United": "Newcastle", "Brighton & Hove Albion": "Brighton", "Wolves": "Wolves"}
# Wikidata IDs of the clubs (for the head coach). Add a line when a promoted club arrives.
CLUB_QIDS = {
    "Arsenal": "Q9617", "Aston Villa": "Q18711", "Bournemouth": "Q19568", "Brentford": "Q19571", "Brighton": "Q19453",
    "Chelsea": "Q9616", "Coventry": "Q19580", "Crystal Palace": "Q19467", "Everton": "Q5794", "Fulham": "Q18708",
    "Hull": "Q19477", "Ipswich": "Q9653", "Leeds": "Q1128631", "Liverpool": "Q1130849", "Man City": "Q50602",
    "Man United": "Q18656", "Newcastle": "Q18716", "Nott'm Forest": "Q19490", "Tottenham": "Q18741", "Sunderland": "Q18739",
}
POSITIONS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def _get(url: str, **kw) -> dict | list:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=45, **kw)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def players_and_fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    bs = _get(f"{FPL}/bootstrap-static/")
    teams = {t["id"]: FPL_TO_HISTORY.get(t["name"], t["name"]) for t in bs["teams"]}
    num = lambda v: float(v) if v not in (None, "") else None
    rows = []
    for e in bs["elements"]:
        if e.get("removed"):
            continue
        rows.append({
            "id": e["id"], "team": teams[e["team"]], "name": e["web_name"], "first_name": e["first_name"],
            "second_name": e["second_name"], "position": POSITIONS.get(e["element_type"], "?"),
            "number": e.get("squad_number"), "photo": PHOTO.format(code=str(e["photo"]).split(".")[0]),
            "status": e["status"], "chance_next": e.get("chance_of_playing_next_round"), "news": e.get("news") or "",
            "news_added": e.get("news_added") or "", "price": e["now_cost"] / 10, "selected_pct": num(e["selected_by_percent"]),
            "form": num(e["form"]), "total_points": e["total_points"], "ppg": num(e["points_per_game"]), "ep_next": num(e.get("ep_next")),
            "minutes": e["minutes"], "starts": e.get("starts", 0), "goals": e["goals_scored"], "assists": e["assists"],
            "xg": num(e.get("expected_goals")), "xa": num(e.get("expected_assists")),
            "xgi": num(e.get("expected_goal_involvements")), "xgc": num(e.get("expected_goals_conceded")),
            "xg90": e.get("expected_goals_per_90"), "xa90": e.get("expected_assists_per_90"),
            "xgi90": e.get("expected_goal_involvements_per_90"), "xgc90": e.get("expected_goals_conceded_per_90"),
            "clean_sheets": e["clean_sheets"], "goals_conceded": e["goals_conceded"], "saves": e["saves"],
            "pens_saved": e["penalties_saved"], "pens_missed": e["penalties_missed"], "yellow": e["yellow_cards"],
            "red": e["red_cards"], "bonus": e["bonus"], "bps": e["bps"], "ict": num(e["ict_index"]),
            "influence": num(e["influence"]), "creativity": num(e["creativity"]), "threat": num(e["threat"]),
            "def_contrib": e.get("defensive_contribution"), "tackles": e.get("tackles"), "recoveries": e.get("recoveries"),
            "cbi": e.get("clearances_blocks_interceptions"), "penalties_order": e.get("penalties_order"),
            "corners_order": e.get("corners_and_indirect_freekicks_order"), "freekicks_order": e.get("direct_freekicks_order"),
            "birth_date": e.get("birth_date") or "",
        })
    players = pd.DataFrame(rows)

    fx = _get(f"{FPL}/fixtures/", params={"future": 1})
    frows = []
    for f in fx:
        if f.get("event") is None:
            continue
        for team, opp, home, diff in ((f["team_h"], f["team_a"], True, f["team_h_difficulty"]),
                                      (f["team_a"], f["team_h"], False, f["team_a_difficulty"])):
            frows.append({"team": teams[team], "gw": f["event"], "opponent": teams[opp], "home": home,
                          "difficulty": diff, "kickoff": f.get("kickoff_time") or ""})
    fixtures = (pd.DataFrame(frows).sort_values(["team", "gw", "kickoff"]).groupby("team").head(6)
                if frows else pd.DataFrame(columns=["team", "gw", "opponent", "home", "difficulty", "kickoff"]))
    return players, fixtures


def coaches() -> pd.DataFrame:
    """Current head coach per club: the P286 statement with no end date (most recent start wins)."""
    values = " ".join(f"wd:{q}" for q in CLUB_QIDS.values())
    query = f"""SELECT ?club ?coachLabel ?image ?start WHERE {{
      VALUES ?club {{ {values} }}
      ?club p:P286 ?st . ?st ps:P286 ?coach . FILTER NOT EXISTS {{ ?st pq:P582 ?end }}
      OPTIONAL {{ ?st pq:P580 ?start }} OPTIONAL {{ ?coach wdt:P18 ?image }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""
    data = _get("https://query.wikidata.org/sparql", params={"query": query, "format": "json"})
    by_qid = {v: k for k, v in CLUB_QIDS.items()}
    rows = []
    for b in data["results"]["bindings"]:
        img = b.get("image", {}).get("value", "").replace("http://", "https://")
        rows.append({"team": by_qid[b["club"]["value"].rsplit("/", 1)[1]], "coach": b["coachLabel"]["value"],
                     "since": b.get("start", {}).get("value", "")[:10], "image": f"{img}?width=240" if img else ""})
    df = pd.DataFrame(rows)
    return df.sort_values("since").groupby("team").tail(1).sort_values("team") if len(df) else df


def refresh() -> str:
    """Update all three files; any source that fails keeps its previous file. Returns a summary line."""
    STATE.mkdir(exist_ok=True)
    notes = []
    try:
        players, fixtures = players_and_fixtures()
        players.to_csv(STATE / "fpl_players.csv", index=False)
        fixtures.to_csv(STATE / "fpl_fixtures.csv", index=False)
        injured = int(players.status.isin(["i", "s", "u"]).sum())
        notes.append(f"FPL: {len(players)} players ({injured} injured/suspended/unavailable), {fixtures.gw.nunique() if len(fixtures) else 0} gameweeks of fixtures")
    except Exception as e:  # noqa: BLE001 - never let this stop the betting job
        notes.append(f"FPL: FAILED ({type(e).__name__}: {e}); kept yesterday's files")
    try:
        c = coaches()
        if len(c):
            c.to_csv(STATE / "coaches.csv", index=False)
        notes.append(f"coaches: {len(c)} clubs")
    except Exception as e:  # noqa: BLE001
        notes.append(f"coaches: FAILED ({type(e).__name__}); kept previous file")
    return "; ".join(notes)


if __name__ == "__main__":
    print(refresh())
