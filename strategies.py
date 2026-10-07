"""Pure probability rules shared by the experiments and the live job (daily.py STRATEGIES).

Keeping each rule here means the experiment that justified a strategy and the live
wallet that runs it compute exactly the same number.
"""

import numpy as np


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
