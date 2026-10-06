"""The morning job: settle yesterday's paper bets, rebuild ratings, bet on today.

    uv run python daily.py

Steps
  1. Download the latest results (football-data.co.uk, Kaggle ATP).
  2. Settle open bets using The Odds API scores; record finished tennis matches.
  3. Rebuild Elo from all history (takes seconds; nothing is cached between runs).
  4. Fetch today's odds, predict every match, and let each strategy's wallet bet.
  5. Write everything to state/ (committed to git = permanent record):
       ledger.csv             every paper bet ever placed, open and settled
       wallets.json           cash per wallet
       bankroll_history.csv   one snapshot per wallet per day (for the chart)
       predictions.csv        today's predictions vs the market, bet or not
       atp_recent.csv         tennis results collected from The Odds API

The LLM agent that runs this each morning only orchestrates and reports. All maths
happens here, so every number can be reproduced.
"""

import difflib
import json
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import backtest as bt
import fetch_data
from names import epl_team, tennis_player
from odds_api import OddsAPI, consensus_prices, winner_from_scores
from wallet import Wallet

ROOT = Path(__file__).parent
STATE = ROOT / "state"
LEDGER, WALLETS = STATE / "ledger.csv", STATE / "wallets.json"
HISTORY, PREDICTIONS = STATE / "bankroll_history.csv", STATE / "predictions.csv"
ATP_RECENT = STATE / "atp_recent.csv"

START_BANKROLL = 1000.0
LOOKAHEAD_HOURS = 30  # bet on matches starting within the next 30 hours
VOID_AFTER_DAYS = 7  # no result after a week (postponed, data gap) -> refund the stake
EPL_PARAMS = dict(k=15, home_adv=40, carryover=0.9)  # chosen by backtest.py tuning
ATP_PARAMS = dict(k_scale=200, surface_weight=0.5)

# Each strategy gets its own wallet per sport, so versions can be compared side by side.
# A strategy turns a prediction row into the probability it believes for that outcome.
# Add new versions here; never edit an old one, or its history stops meaning anything.
STRATEGIES = {
    "elo_v0": {"prob": lambda row: row["elo_p"], "min_edge": 0.05},
}

LEDGER_COLS = ["bet_id", "wallet", "sport", "strategy", "placed_at", "commence_time", "sport_key",
               "event_id", "competition", "match", "pick", "model_p", "market_p", "odds", "n_books",
               "stake", "status", "result", "pnl", "settled_at"]


# ------------------------------------------------------------------- state I/O


def load_state() -> tuple[pd.DataFrame, dict]:
    text_cols = {c: "object" for c in ["result", "settled_at", "pick", "match", "event_id"]}
    ledger = (pd.read_csv(LEDGER, dtype=text_cols) if LEDGER.exists()
              else pd.DataFrame(columns=LEDGER_COLS).astype(text_cols))
    wallets = json.loads(WALLETS.read_text()) if WALLETS.exists() else {}
    for sport in ["epl", "atp"]:
        for name in STRATEGIES:
            wallets.setdefault(f"{sport}:{name}", {"cash": START_BANKROLL})
    return ledger, wallets


def save_state(ledger: pd.DataFrame, wallets: dict, predictions: pd.DataFrame, now: pd.Timestamp) -> None:
    STATE.mkdir(exist_ok=True)
    ledger.to_csv(LEDGER, index=False)
    WALLETS.write_text(json.dumps(wallets, indent=2))
    predictions.to_csv(PREDICTIONS, index=False)

    rows = []
    for name, w in wallets.items():
        mine = ledger[ledger.wallet == name]
        open_stakes = mine.loc[mine.status == "open", "stake"].sum()
        settled = mine[mine.status.isin(["won", "lost"])]
        rows.append({"date": now.date().isoformat(), "wallet": name, "cash": round(w["cash"], 2),
                     "open_stakes": round(open_stakes, 2), "bankroll": round(w["cash"] + open_stakes, 2),
                     "bets_settled": len(settled), "bets_open": int((mine.status == "open").sum()),
                     "profit": round(settled.pnl.sum(), 2),
                     "roi": round(settled.pnl.sum() / settled.stake.sum(), 4) if len(settled) else 0.0})
    hist = pd.read_csv(HISTORY) if HISTORY.exists() else pd.DataFrame()
    if len(hist):
        hist = hist[hist.date != now.date().isoformat()]  # re-running today replaces today's row
    pd.concat([hist, pd.DataFrame(rows)], ignore_index=True).to_csv(HISTORY, index=False)


# ------------------------------------------------------------------- settling


def settle(api: OddsAPI, ledger: pd.DataFrame, wallets: dict, now: pd.Timestamp,
           score_cache: dict[str, list[dict]]) -> list[str]:
    log = []
    open_idx = ledger.index[ledger.status == "open"]
    for sport_key in ledger.loc[open_idx, "sport_key"].unique():
        events = {e["id"]: e for e in get_scores(api, sport_key, score_cache)}
        for i in open_idx[ledger.loc[open_idx, "sport_key"] == sport_key]:
            b = ledger.loc[i]
            winner = winner_from_scores(events[b.event_id]) if b.event_id in events else None
            if winner is None:
                if now - pd.Timestamp(b.commence_time) > timedelta(days=VOID_AFTER_DAYS):
                    wallets[b.wallet]["cash"] += b.stake
                    ledger.loc[i, ["status", "pnl", "settled_at"]] = ["void", 0.0, now.isoformat()]
                    log.append(f"VOID {b.wallet} {b.match} (no result after {VOID_AFTER_DAYS} days)")
                continue
            won = winner == b.pick
            pnl = b.stake * (b.odds - 1) if won else -b.stake
            if won:
                wallets[b.wallet]["cash"] += b.stake * b.odds
            ledger.loc[i, ["status", "result", "pnl", "settled_at"]] = [
                "won" if won else "lost", winner, round(pnl, 2), now.isoformat()]
            log.append(f"{'WON ' if won else 'LOST'} {b.wallet} {b.match}: {b.pick} @ {b.odds} "
                       f"-> {pnl:+.2f}")
    return log


def get_scores(api: OddsAPI, sport_key: str, cache: dict) -> list[dict]:
    if sport_key not in cache:
        try:
            cache[sport_key] = api.scores(sport_key)
        except requests.HTTPError as e:  # finished tournaments' keys can disappear
            print(f"  scores unavailable for {sport_key}: {e}")
            cache[sport_key] = []
    return cache[sport_key]


def record_atp_results(score_cache: dict, titles: dict[str, str], known: set[str],
                       surfaces: dict[str, str]) -> int:
    """Store finished ATP matches in history format so Elo keeps learning even if the
    Kaggle dataset lags. backtest.load_atp() only uses rows newer than the Kaggle data."""
    rows = []
    for key, events in score_cache.items():
        if not key.startswith("tennis_atp_"):
            continue
        for e in events:
            winner = winner_from_scores(e)
            if winner in (None, "Draw"):
                continue
            when = pd.Timestamp(e["commence_time"])
            p1, p2 = tennis_player(e["home_team"], known), tennis_player(e["away_team"], known)
            title = titles.get(key, key)
            rows.append({"Tournament": title, "Date": when.date().isoformat(),
                         "Surface": guess_surface(title, when, surfaces), "Player_1": p1, "Player_2": p2,
                         "Winner": p1 if winner == e["home_team"] else p2, "event_id": e["id"]})
    if not rows:
        return 0
    old = pd.read_csv(ATP_RECENT) if ATP_RECENT.exists() else pd.DataFrame()
    new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("event_id", keep="last")
    STATE.mkdir(exist_ok=True)
    new.to_csv(ATP_RECENT, index=False)
    return len(new) - len(old)


def guess_surface(title: str, when: pd.Timestamp, surfaces: dict[str, str]) -> str:
    """Match the tournament name against history; otherwise use the tennis calendar."""
    match = difflib.get_close_matches(title.removeprefix("ATP ").strip(), surfaces, n=1, cutoff=0.6)
    if match:
        return surfaces[match[0]]
    md = (when.month, when.day)
    return "Clay" if (4, 1) <= md <= (6, 8) else "Grass" if (6, 9) <= md <= (7, 15) else "Hard"


# ---------------------------------------------------------------- predicting


def predict_epl(api: OddsAPI, now: pd.Timestamp) -> list[dict]:
    df = bt.load_epl()
    diffs, elo = bt.epl_elo_diffs(df, **EPL_PARAMS)
    train = df.season.isin(bt.EPL_TRAIN).to_numpy()
    model = bt.fit_outcome_model(diffs[train], df.result[train].to_numpy())

    rows = []
    for e in api.odds("soccer_epl"):
        home, away = epl_team(e["home_team"], elo.season_teams), epl_team(e["away_team"], elo.season_teams)
        if not home or not away:
            print(f"  skip (unknown team name): {e['home_team']} v {e['away_team']}")
            continue
        p = bt.outcome_probs(model, np.array([elo.diff(home, away)])).iloc[0]
        elo_p = {e["home_team"]: p.H, "Draw": p.D, e["away_team"]: p.A}
        rows += event_rows("epl", "soccer_epl", "Premier League", e, elo_p)
    return rows


def predict_atp(api: OddsAPI, now: pd.Timestamp, score_cache: dict) -> tuple[list[dict], int]:
    df = bt.load_atp(ATP_RECENT)
    known = set(df.Player_1) | set(df.Player_2)
    recent = df[df.date >= df.date.max() - pd.Timedelta(days=730)]
    surfaces = dict(zip(recent.Tournament, recent.Surface))

    sports = api.active_atp_keys()
    titles = {s["key"]: s["title"] for s in sports}
    for s in sports:  # finished matches feed Elo tomorrow
        get_scores(api, s["key"], score_cache)
    added = record_atp_results(score_cache, titles, known, surfaces)
    if added:
        df = bt.load_atp(ATP_RECENT)
        known = set(df.Player_1) | set(df.Player_2)
    _, elo = bt.tennis_probs(df, **ATP_PARAMS)

    rows = []
    for s in sports:
        for e in api.odds(s["key"]):
            when = pd.Timestamp(e["commence_time"])
            surface = guess_surface(s["title"], when, surfaces)
            a, b = tennis_player(e["home_team"], known), tennis_player(e["away_team"], known)
            p = elo.prob(a, b, surface)
            rows += event_rows("atp", s["key"], f"{s['title']} ({surface})", e,
                               {e["home_team"]: p, e["away_team"]: 1 - p})
    return rows, added


def event_rows(sport: str, sport_key: str, competition: str, e: dict, elo_p: dict) -> list[dict]:
    """One row per outcome: what Elo thinks vs what the market thinks."""
    prices, n_books = consensus_prices(e)
    if not prices or set(prices) != set(elo_p):
        return []
    implied = {k: 1 / v for k, v in prices.items()}
    total = sum(implied.values())  # > 1 because of the bookmaker's cut; divide it out
    return [{"sport": sport, "sport_key": sport_key, "competition": competition, "event_id": e["id"],
             "commence_time": e["commence_time"], "match": f"{e['home_team']} v {e['away_team']}",
             "outcome": name, "elo_p": round(float(elo_p[name]), 4),
             "market_p": round(implied[name] / total, 4), "odds": prices[name], "n_books": n_books,
             "edge": round(float(elo_p[name]) * prices[name] - 1, 4)}
            for name in elo_p]


# ------------------------------------------------------------------- betting


def place_bets(preds: pd.DataFrame, ledger: pd.DataFrame, wallets: dict, now: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    log, new = [], []
    if preds.empty:
        return ledger, log
    start = pd.to_datetime(preds.commence_time)
    window = preds[(start > now) & (start <= now + timedelta(hours=LOOKAHEAD_HOURS))]
    for (sport, event_id), outcomes in window.groupby(["sport", "event_id"], sort=False):
        for name, strat in STRATEGIES.items():
            wallet_name, bet_id = f"{sport}:{name}", f"{event_id}:{name}"
            if bet_id in set(ledger.bet_id):
                continue  # already bet on this match
            w = Wallet(bankroll=wallets[wallet_name]["cash"], min_edge=strat["min_edge"])
            options = [(r["outcome"], float(strat["prob"](r)), float(r["odds"])) for _, r in outcomes.iterrows()]
            bet = w.consider(options)
            if not bet or bet[3] < 1:
                continue
            pick, p, odds, stake = bet
            r = outcomes[outcomes.outcome == pick].iloc[0]
            wallets[wallet_name]["cash"] -= stake
            new.append({"bet_id": bet_id, "wallet": wallet_name, "sport": sport, "strategy": name,
                        "placed_at": now.isoformat(), "commence_time": r.commence_time,
                        "sport_key": r.sport_key, "event_id": event_id, "competition": r.competition,
                        "match": r.match, "pick": pick, "model_p": round(p, 4), "market_p": r.market_p,
                        "odds": odds, "n_books": r.n_books, "stake": stake, "status": "open",
                        "result": "", "pnl": 0.0, "settled_at": ""})
            log.append(f"BET  {wallet_name} {r.match}: {pick} @ {odds} stake ${stake:.2f} "
                       f"(model {p:.0%} vs market {r.market_p:.0%})")
    if new:
        ledger = pd.concat([ledger, pd.DataFrame(new)], ignore_index=True)
    return ledger, log


# ---------------------------------------------------------------------- main


def main(api: OddsAPI | None = None, now: pd.Timestamp | None = None, download: bool = True) -> None:
    api = api or OddsAPI()
    now = now or pd.Timestamp.now(tz="UTC")
    if download:
        fetch_data.main()
    ledger, wallets = load_state()
    score_cache: dict[str, list[dict]] = {}

    print("\n== Settling open bets")
    settled = settle(api, ledger, wallets, now, score_cache)
    print("\n".join(settled) or "  nothing to settle")

    print("\n== Predicting")
    preds = predict_epl(api, now)
    atp_preds, added = predict_atp(api, now, score_cache)
    preds = pd.DataFrame(preds + atp_preds)
    print(f"  {preds.event_id.nunique() if len(preds) else 0} upcoming matches priced; "
          f"{added} new ATP results recorded")

    print("\n== Betting")
    ledger, placed = place_bets(preds, ledger, wallets, now)
    print("\n".join(placed) or "  no bets met the edge threshold")

    save_state(ledger, wallets, preds, now)
    print("\n== Wallets")
    print(pd.read_csv(HISTORY).query("date == @now.date().isoformat()").to_string(index=False))
    print(f"\nOdds API credits remaining: {api.remaining}")


if __name__ == "__main__":
    main(download="--no-download" not in sys.argv)
