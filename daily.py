"""The morning job: settle paper bets, rebuild ratings, forecast every match, bet on today.

    uv run python daily.py

Steps
  1. Download the latest results (football-data.co.uk, Kaggle ATP).
  2. Settle open bets from The Odds API scores, falling back to the history files.
  3. Rebuild Elo from all history (takes seconds; nothing is cached between runs).
  4. Fetch today's odds, resolve player identities, forecast every match, let each
     strategy's wallet bet at a real bookmaker quote.
  5. Write everything to state/ (committed to git = permanent record):
       ledger.csv             every paper bet ever placed, open and settled
       wallets.json           cash per wallet;  deposits.csv  money put in (see accounts.py)
       bankroll_history.csv   one snapshot per wallet per day (for the chart)
       predictions.csv        today's forecasts (latest snapshot, for the dashboard)
       forecasts.csv          EVERY forecast ever made, passes included (append-only)
       outcomes.csv, closing.csv   results and closing prices for evaluation
       atp_recent.csv         tennis results collected from The Odds API
       *_elo_history.csv, *_form.csv   ratings after every match + recent form (dashboard)
       bet_flags.csv          manual annotations on bets (e.g. identity errors); ledger stays untouched

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

import accounts
import backtest as bt
import fetch_data
import ratings_history
import records
from names import epl_team, load_aliases, player_profiles, tennis_player
from odds_api import OddsAPI, price_summary, winner_from_scores
from wallet import Wallet

ROOT = Path(__file__).parent
STATE = ROOT / "state"
LEDGER, WALLETS = STATE / "ledger.csv", STATE / "wallets.json"
HISTORY, PREDICTIONS = STATE / "bankroll_history.csv", STATE / "predictions.csv"
ATP_RECENT = STATE / "atp_recent.csv"

START_BANKROLL = 5000.0  # new wallets open with this (a strategy may override with "start_bankroll")
LEGACY_START = 1000.0  # what wallets created before deposits.csv existed were opened with
LOOKAHEAD_HOURS = 30  # bet on matches starting within the next 30 hours
FALLBACK_AFTER_HOURS = 24  # no API result a day after kickoff -> look in the history files
UNRESOLVED_AFTER_DAYS = 14  # still no result anywhere -> refund, marked "unresolved" (not "void")
EPL_PARAMS = dict(k=15, home_adv=40, carryover=0.9)  # chosen by backtest.py tuning
ATP_PARAMS = dict(k_scale=200, surface_weight=0.5)
GRAND_SLAMS = ("Australian Open", "French Open", "Roland Garros", "Wimbledon", "US Open")

# Each strategy gets its own wallet per sport, so versions can be compared side by side.
# A strategy turns a forecast row into the probability it believes for that outcome.
# Add new versions here; never edit an old one, or its history stops meaning anything.
# Optional keys: "start_bankroll" (default START_BANKROLL).
STRATEGIES = {
    "elo_v0": {"prob": lambda row: row["elo_p"], "min_edge": 0.05},
}

LEDGER_COLS = ["bet_id", "wallet", "sport", "strategy", "placed_at", "commence_time", "sport_key",
               "event_id", "competition", "match", "pick", "model_p", "market_p", "odds", "n_books",
               "stake", "status", "result", "pnl", "settled_at",
               "exec_book", "quote_at", "median_odds", "result_source"]
TEXT_COLS = ["result", "settled_at", "pick", "match", "event_id", "exec_book", "quote_at", "result_source"]


# ------------------------------------------------------------------- state I/O


def load_state(now: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    dtypes = {c: "object" for c in TEXT_COLS}
    ledger = pd.read_csv(LEDGER, dtype=dtypes) if LEDGER.exists() else pd.DataFrame(columns=LEDGER_COLS)
    for c in LEDGER_COLS:  # older ledgers lack the newer columns
        if c not in ledger.columns:
            ledger[c] = np.nan
    ledger = ledger.astype({c: "object" for c in TEXT_COLS})
    wallets = json.loads(WALLETS.read_text()) if WALLETS.exists() else {}
    deposits = accounts.load_deposits()
    at = now.isoformat(timespec="seconds")

    for name in [w for w in wallets if accounts.deposited(deposits, w) == 0]:  # one-off migration
        deposits = pd.concat([deposits, pd.DataFrame([{"at": at, "wallet": name, "amount": LEGACY_START,
                              "kind": "open", "reason": "opening balance (created before deposits were tracked)"}])],
                             ignore_index=True)
    for sport in ["epl", "atp"]:
        for name, strat in STRATEGIES.items():
            w = f"{sport}:{name}"
            if w not in wallets:
                deposits = accounts.record(deposits, wallets, w, strat.get("start_bankroll", START_BANKROLL),
                                           "open", f"new wallet for strategy {name}", at)
    return ledger, wallets, deposits


def save_state(ledger: pd.DataFrame, wallets: dict, deposits: pd.DataFrame, predictions: pd.DataFrame,
               now: pd.Timestamp) -> None:
    STATE.mkdir(exist_ok=True)
    ledger.to_csv(LEDGER, index=False)
    WALLETS.write_text(json.dumps(wallets, indent=2))
    deposits.to_csv(accounts.DEPOSITS, index=False)
    predictions.to_csv(PREDICTIONS, index=False)

    rows = []
    for name, w in wallets.items():
        mine = ledger[ledger.wallet == name]
        open_stakes = mine.loc[mine.status == "open", "stake"].sum()
        settled = mine[mine.status.isin(["won", "lost"])]
        bankroll = w["cash"] + open_stakes
        dep = accounts.deposited(deposits, name)
        rows.append({"date": now.date().isoformat(), "wallet": name, "cash": round(w["cash"], 2),
                     "open_stakes": round(open_stakes, 2), "bankroll": round(bankroll, 2),
                     "deposits": round(dep, 2), "net": round(bankroll - dep, 2),
                     "bets_settled": len(settled), "bets_open": int((mine.status == "open").sum()),
                     "profit": round(settled.pnl.sum(), 2),
                     "roi": round(settled.pnl.sum() / settled.stake.sum(), 4) if len(settled) else 0.0})
    hist = pd.read_csv(HISTORY) if HISTORY.exists() else pd.DataFrame()
    if len(hist):
        hist = hist[hist.date != now.date().isoformat()]  # re-running today replaces today's row
    pd.concat([hist, pd.DataFrame(rows)], ignore_index=True).to_csv(HISTORY, index=False)


# ------------------------------------------------------------------- settling


def settle(api: OddsAPI, ledger: pd.DataFrame, wallets: dict, now: pd.Timestamp,
           score_cache: dict[str, list[dict]], history: "records.History") -> list[str]:
    log = []
    open_idx = ledger.index[ledger.status == "open"]
    for sport_key in ledger.loc[open_idx, "sport_key"].unique():
        events = {e["id"]: e for e in get_scores(api, sport_key, score_cache)}
        for i in open_idx[ledger.loc[open_idx, "sport_key"] == sport_key]:
            b = ledger.loc[i]
            age = now - pd.Timestamp(b.commence_time)
            winner = winner_from_scores(events[b.event_id]) if b.event_id in events else None
            source = "odds_api"
            if winner is None and age > timedelta(hours=FALLBACK_AFTER_HOURS):
                found = history.lookup(b.sport, b.match, b.commence_time)
                winner, source = (found["winner"], "history") if found else (None, None)
            if winner is None:
                if age > timedelta(days=UNRESOLVED_AFTER_DAYS):
                    wallets[b.wallet]["cash"] += b.stake
                    ledger.loc[i, ["status", "pnl", "settled_at", "result_source"]] = [
                        "unresolved", 0.0, now.isoformat(), "none"]
                    log.append(f"UNRESOLVED {b.wallet} {b.match}: no result in any source after "
                               f"{UNRESOLVED_AFTER_DAYS} days, stake refunded (check manually)")
                continue
            won = winner == b.pick
            pnl = b.stake * (b.odds - 1) if won else -b.stake
            if won:
                wallets[b.wallet]["cash"] += b.stake * b.odds
            ledger.loc[i, ["status", "result", "pnl", "settled_at", "result_source"]] = [
                "won" if won else "lost", winner, round(pnl, 2), now.isoformat(), source]
            log.append(f"{'WON ' if won else 'LOST'} {b.wallet} {b.match}: {b.pick} @ {b.odds} "
                       f"-> {pnl:+.2f}" + ("  [result from history files]" if source == "history" else ""))
    return log


def get_scores(api: OddsAPI, sport_key: str, cache: dict) -> list[dict]:
    if sport_key not in cache:
        try:
            cache[sport_key] = api.scores(sport_key)
        except requests.HTTPError as e:  # finished tournaments' keys can disappear
            print(f"  scores unavailable for {sport_key}: {e}")
            cache[sport_key] = []
    return cache[sport_key]


def record_atp_results(score_cache: dict, titles: dict[str, str], profiles: dict, since: pd.Timestamp,
                       surfaces: dict[str, str], aliases: dict[str, str]) -> tuple[int, list[str]]:
    """Store finished ATP matches in history format so Elo keeps learning even if Kaggle lags.
    Only matches where BOTH players resolve to a trusted history identity are stored:
    a guessed identity would create a phantom player that real results then keep updating."""
    rows, skipped = [], []
    for key, events in score_cache.items():
        if not key.startswith("tennis_atp_"):
            continue
        for e in events:
            winner = winner_from_scores(e)
            if winner in (None, "Draw"):
                continue
            a, b = (tennis_player(x, profiles, since, aliases) for x in (e["home_team"], e["away_team"]))
            if not (a.ok and b.ok):
                skipped.append(f"{e['home_team']} v {e['away_team']} ({a.status}/{b.status})")
                continue
            when = pd.Timestamp(e["commence_time"])
            title = titles.get(key, key)
            rows.append({"Tournament": title, "Date": when.date().isoformat(),
                         "Surface": guess_surface(title, when, surfaces), "Player_1": a.name, "Player_2": b.name,
                         "Winner": a.name if winner == e["home_team"] else b.name, "event_id": e["id"],
                         "api_player_1": e["home_team"], "api_player_2": e["away_team"]})
    if not rows:
        return 0, skipped
    old = pd.read_csv(ATP_RECENT) if ATP_RECENT.exists() else pd.DataFrame()
    new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("event_id", keep="last")
    STATE.mkdir(exist_ok=True)
    new.to_csv(ATP_RECENT, index=False)
    return len(new) - len(old), skipped


def guess_surface(title: str, when: pd.Timestamp, surfaces: dict[str, str]) -> str:
    """Match the tournament name against history; otherwise use the tennis calendar.
    (Known weakness: fuzzy matching can pick the wrong tournament; logged per forecast.)"""
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
    STATE.mkdir(exist_ok=True)
    (pd.Series({t: elo.ratings[t] for t in elo.season_teams}, name="elo").rename_axis("team")
     .sort_values(ascending=False).round(1).to_csv(STATE / "epl_ratings.csv"))

    rows = []
    for e in api.odds("soccer_epl"):
        home, away = epl_team(e["home_team"], elo.season_teams), epl_team(e["away_team"], elo.season_teams)
        ctx = {"resolved_as": f"{home} | {away}", "identity": "matched" if home and away else "unknown",
               "surface": "", "best_of": ""}
        elo_p = None
        if home and away:
            p = bt.outcome_probs(model, np.array([elo.diff(home, away)])).iloc[0]
            elo_p = {e["home_team"]: p.H, "Draw": p.D, e["away_team"]: p.A}
        rows += event_rows("epl", "soccer_epl", "Premier League", e, elo_p, ctx)
    return rows


def predict_atp(api: OddsAPI, now: pd.Timestamp, score_cache: dict) -> tuple[list[dict], int, list[str]]:
    df = bt.load_atp(ATP_RECENT)
    profiles = player_profiles(df)
    since = df.date.max() - pd.Timedelta(days=365)
    aliases = load_aliases("atp")
    recent = df[df.date >= df.date.max() - pd.Timedelta(days=730)]
    surfaces = dict(zip(recent.Tournament, recent.Surface))

    sports = api.active_atp_keys()
    titles = {s["key"]: s["title"] for s in sports}
    for s in sports:  # finished matches feed Elo tomorrow
        get_scores(api, s["key"], score_cache)
    added, skipped = record_atp_results(score_cache, titles, profiles, since, surfaces, aliases)
    if added:
        df = bt.load_atp(ATP_RECENT)
        profiles = player_profiles(df)
    _, elo = bt.tennis_probs(df, **ATP_PARAMS)
    active = recent[recent.date >= df.date.max() - pd.Timedelta(days=365)]
    players = sorted(set(active.Player_1) | set(active.Player_2))
    (pd.DataFrame({"player": players, "elo": [elo.overall[x] for x in players],
                   **{f"elo_{srf.lower()}": [elo.surface[(x, srf)] for x in players]
                      for srf in ["Hard", "Clay", "Grass"]}})
     .sort_values("elo", ascending=False).head(200).round(1).to_csv(STATE / "atp_ratings.csv", index=False))

    rows, unresolved = [], []
    for s in sports:
        best_of = 5 if any(g in s["title"] for g in GRAND_SLAMS) else 3
        for e in api.odds(s["key"]):
            when = pd.Timestamp(e["commence_time"])
            surface = guess_surface(s["title"], when, surfaces)
            a, b = (tennis_player(x, profiles, since, aliases) for x in (e["home_team"], e["away_team"]))
            ok = a.ok and b.ok
            if not ok:
                unresolved += [f"{r.api_name} ({r.status}{': ' + ', '.join(r.candidates) if r.candidates else ''})"
                               for r in (a, b) if not r.ok]
            p = elo.prob(a.name, b.name, surface) if ok else None
            ctx = {"resolved_as": f"{a.name} | {b.name}", "identity": "matched" if ok else f"{a.status}/{b.status}",
                   "surface": surface, "best_of": best_of}
            rows += event_rows("atp", s["key"], f"{s['title']} ({surface})", e,
                               {e["home_team"]: p, e["away_team"]: 1 - p} if ok else None, ctx)
    if skipped:
        unresolved += [f"result not stored: {x}" for x in skipped]
    return rows, added, unresolved


def event_rows(sport: str, sport_key: str, competition: str, e: dict, elo_p: dict | None, ctx: dict) -> list[dict]:
    """One row per outcome: what Elo thinks vs what the market thinks, plus the quote we'd bet at.
    elo_p=None means we don't trust the identities: the row is logged but not bettable."""
    prices, n_books = price_summary(e)
    names = [e["home_team"], "Draw", e["away_team"]] if sport == "epl" else [e["home_team"], e["away_team"]]
    if not prices or set(prices) != set(names):
        return []
    implied = {k: 1 / v["median"] for k, v in prices.items()}
    total = sum(implied.values())  # > 1 because of the bookmaker's cut; divide it out
    rows = []
    for name in names:
        q, p = prices[name], (float(elo_p[name]) if elo_p else np.nan)
        rows.append({"sport": sport, "sport_key": sport_key, "competition": competition, "event_id": e["id"],
                     "commence_time": e["commence_time"], "match": f"{e['home_team']} v {e['away_team']}",
                     "outcome": name, "elo_p": round(p, 4), "market_p": round(implied[name] / total, 4),
                     "odds": q["exec"], "exec_book": q["exec_book"], "quote_at": q["exec_at"],
                     "median_odds": q["median"], "pinnacle_odds": q["pinnacle"], "n_books": n_books,
                     "edge": round(p * q["exec"] - 1, 4), "eligible": elo_p is not None, **ctx})
    return rows


# ------------------------------------------------------------------- betting


def place_bets(preds: pd.DataFrame, ledger: pd.DataFrame, wallets: dict, now: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    log, new = [], []
    if preds.empty:
        return ledger, log
    start = pd.to_datetime(preds.commence_time)
    window = preds[(start > now) & (start <= now + timedelta(hours=LOOKAHEAD_HOURS))]
    if "eligible" in window.columns:  # identity not trusted -> never bet
        window = window[window.eligible.astype(str) == "True"]
    existing = set(ledger.bet_id)
    for (sport, event_id), outcomes in window.groupby(["sport", "event_id"], sort=False):
        for name, strat in STRATEGIES.items():
            wallet_name, bet_id = f"{sport}:{name}", f"{event_id}:{name}"
            if bet_id in existing:
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
                        "result": "", "pnl": 0.0, "settled_at": "",
                        "exec_book": r.get("exec_book", ""), "quote_at": r.get("quote_at", ""),
                        "median_odds": r.get("median_odds", np.nan), "result_source": ""})
            log.append(f"BET  {wallet_name} {r.match}: {pick} @ {odds} ({r.get('exec_book', '?')}) "
                       f"stake ${stake:.2f} (model {p:.0%} vs market {r.market_p:.0%})")
    if new:
        ledger = pd.concat([ledger, pd.DataFrame(new)], ignore_index=True)
    return ledger, log


# ---------------------------------------------------------------------- main


def epl_scores_needed(now: pd.Timestamp) -> bool:
    """Fetch EPL scores (2 credits) only when forecast EPL matches finished in the last 3 days."""
    if not records.FORECASTS.exists():
        return False
    f = pd.read_csv(records.FORECASTS, usecols=["sport", "commence_time"])
    start = pd.to_datetime(f.commence_time[f.sport == "epl"], utc=True)
    return bool(((start < now - timedelta(hours=2)) & (start > now - timedelta(days=3))).any())


def main(api: OddsAPI | None = None, now: pd.Timestamp | None = None, download: bool = True) -> None:
    api = api or OddsAPI()
    now = now or pd.Timestamp.now(tz="UTC")
    if download:
        fetch_data.main()
    ledger, wallets, deposits = load_state(now)
    score_cache: dict[str, list[dict]] = {}
    history = records.History()

    print("\n== Settling open bets")
    settled = settle(api, ledger, wallets, now, score_cache, history)
    print("\n".join(settled) or "  nothing to settle")

    print("\n== Predicting")
    if epl_scores_needed(now):
        get_scores(api, "soccer_epl", score_cache)
    preds = predict_epl(api, now)
    atp_preds, added, unresolved = predict_atp(api, now, score_cache)
    preds = pd.DataFrame(preds + atp_preds)
    n_events = preds.event_id.nunique() if len(preds) else 0
    n_blocked = preds.loc[~preds.eligible, "event_id"].nunique() if len(preds) else 0
    print(f"  {n_events} upcoming matches priced ({n_blocked} not bettable: identity not trusted); "
          f"{added} new ATP results recorded")
    for u in dict.fromkeys(unresolved):
        print(f"  IDENTITY {u}  -> fix with a line in aliases.csv if this is a real player")

    print("\n== Betting")
    ledger, placed = place_bets(preds, ledger, wallets, now)
    print("\n".join(placed) or "  no bets met the edge threshold")

    print("\n== Records")
    print(f"  forecasts logged: {records.append_forecasts(preds, now)}, "
          f"outcomes: {records.record_outcomes(score_cache, now)}, "
          f"closing prices: {records.record_closing(history, now)}")
    print(" ", records.clv_summary(ledger).replace("\n", "\n  "))

    ratings_history.write_all(bt.load_epl(), EPL_PARAMS, bt.load_atp(ATP_RECENT), ATP_PARAMS)  # dashboard charts
    save_state(ledger, wallets, deposits, preds, now)
    print("\n== Wallets")
    print(pd.read_csv(HISTORY).query("date == @now.date().isoformat()").to_string(index=False))
    print(f"\nOdds API credits remaining: {api.remaining}")


if __name__ == "__main__":
    main(download="--no-download" not in sys.argv)
