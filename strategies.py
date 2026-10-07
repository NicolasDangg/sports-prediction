"""Pure probability rules shared by the experiments and the live job (daily.py STRATEGIES).

Keeping each rule here means the experiment that justified a strategy and the live
wallet that runs it compute exactly the same number.
"""

import numpy as np
import pandas as pd


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def format_calibrated(p, best_of, slope_bo3: float, slope_bo5: float):
    """E004: shrink (slope < 1) or stretch (slope > 1) Elo's confidence, per match format.

    p' = sigmoid(slope × logit(p)), with one slope for best-of-3 and one for best-of-5.
    There's no intercept, so swapping the players always gives exactly 1 − p'.
    Example: p = 0.70 and slope 0.8 → logit 0.847 × 0.8 = 0.678 → p' = 0.663.
    """
    slope = np.where(np.asarray(best_of) == 5, slope_bo5, slope_bo3)
    return 1 / (1 + np.exp(-slope * logit(p)))


NEWS_VETO = {"injured", "ill", "withdrawn", "doubt"}
NEWS_MIN_CONFIDENCE = 0.6


def news_veto(row) -> bool:
    """E007: True when fresh news says this outcome's player has a physical problem.
    The veto only stops us BACKING that player; it never invents a probability for him."""
    try:
        conf = float(row.get("news_confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    return row.get("news_status") in NEWS_VETO and conf >= NEWS_MIN_CONFIDENCE


def sharp_prob(row) -> float:
    """E012: Pinnacle's no-vig probability (0 when Pinnacle didn't price every outcome, so no bet).
    Example: Pinnacle 1.80 / 2.10 -> 0.556 + 0.476 = 1.032 -> fair 0.539 / 0.461."""
    try:
        p = float(row.get("pin_fair_p"))
    except (TypeError, ValueError):
        return 0.0
    return p if np.isfinite(p) else 0.0


def best_price(row) -> tuple[float, str, str]:
    """E012: bet at the highest real bookmaker quote (exchanges excluded), not the typical one."""
    try:
        odds = float(row.get("best_odds"))
    except (TypeError, ValueError):
        odds = float("nan")
    if not np.isfinite(odds):
        return float(row["odds"]), row.get("exec_book", ""), row.get("quote_at", "")
    return odds, row.get("best_book", ""), row.get("best_at", "")


# E013: the casual "safe bets" bettor. Not a strategy we expect to win: a realistic comparison.
CASUAL_MIN_P = 0.80  # only outcomes at least this likely to win (Pinnacle fair p, else market p)
CASUAL_POT = 0.25  # share of the wallet put in play per session
CASUAL_WEEKDAY = 5  # Saturday (Saigon): the morning run that day is the weekly session
CASUAL_TZ = "Asia/Ho_Chi_Minh"


def win_chance(row) -> float:
    """Best available estimate of how likely an outcome is: Pinnacle with the margin removed,
    else the market median with the margin removed."""
    p = sharp_prob(row)
    return p if p > 0 else float(row.get("market_p") or 0)


def casual_session(window: pd.DataFrame, cash: float, now: pd.Timestamp, max_picks: int,
                   smart: bool = False) -> list[tuple[int, float, float]]:
    """E013: once a week, put CASUAL_POT of the wallet on the likeliest winners (>= CASUAL_MIN_P),
    split equally over up to max_picks matches (1 = one big bet). Returns [(row index, p, stake)].
    Example: $5,000 wallet, many-version, 10 qualifying favourites -> $125 on each.
    smart=True (E014, smart_casual_v1): only favourites Pinnacle priced, and only where the best bookmaker
    price pays more than Pinnacle's fair price (sharp_v1's idea), e.g. fair 1.12, best 1.15 -> +2.7%."""
    if now.tz_convert(CASUAL_TZ).dayofweek != CASUAL_WEEKDAY or window.empty:
        return []
    p = window.apply(sharp_prob if smart else win_chance, axis=1)
    keep = p >= CASUAL_MIN_P
    if smart:
        keep &= window.apply(lambda r: best_price(r)[0], axis=1) * p > 1
    cand = window.assign(p=p)[keep]
    if cand.empty:
        return []
    best = cand.sort_values("p", ascending=False).drop_duplicates("event_id").head(max_picks)
    stake = round(cash * CASUAL_POT / len(best), 2)
    return [(i, float(r.p), stake) for i, r in best.iterrows()] if stake >= 1 else []
