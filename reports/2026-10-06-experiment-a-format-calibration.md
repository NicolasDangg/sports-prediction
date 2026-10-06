# Report: 2026-10-06 · Experiment A, format-aware calibration (tennis)

**Status: ready to run (planned for ~2026-10-20).** To start:

```
/refine-strategy reports/2026-10-06-experiment-a-format-calibration.md
```

Before running, spend 5 minutes on the "Fill in on the day" section at the bottom. It's optional, but it makes the
result easier to judge.

---

## In plain words

Elo says "player X wins 67% of the time", but over the last few years those players actually won about 62% of the
time. The model is **too sure of itself**, and only in **best-of-3** matches. In best-of-5 (Grand Slams) it's
almost exactly right.

That makes sense. A longer match gives the better player more chances to come through, so upsets are rarer in
best-of-5. Elo ignores the format, so it ends up with one in-between confidence level: too high for best-of-3 and
about right for best-of-5.

Being overconfident costs money. The model sees "value" on favourites that isn't really there, then bets on it.
The fix is **calibration**: a small correction layer on top of Elo that turns "Elo says 67%" into "in reality
that's about 62%", fitted separately for each format.

A tiny example: Elo says 70% for a best-of-3 match. The calibration layer has learned that best-of-3 70%s
historically win ~64%. If the bookmaker's odds are 1.50 (66.7% implied), v0 would have bet: 0.70 × 1.50 − 1 = +5%
edge. The calibrated model says 0.64 × 1.50 − 1 = −4%, so **no bet**. That's a bad bet avoided.

## What I looked at
The 2026-10-06 review of `elo_v0` (ATP). Validation years 2020–2022, where the Elo favourite's predicted win
chance was compared with how often they actually won:

| Group | Matches | Elo said | Actually won | Gap |
|---|---:|---:|---:|---:|
| Best-of-3 | 4,830 | 67.1% | 61.8% | **+5.3 pts (overconfident)** |
| Best-of-5 | 1,348 | 71.2% | 71.9% | −0.7 pts (fine) |
| Both players 30+ prior matches | 4,390 | 67.3% | 64.2% | +3.1 pts |
| A player with < 30 prior matches | 1,788 | 69.6% | 63.4% | +6.2 pts (that's experiment B) |

Other relevant numbers:
- Log loss: raw Elo 0.6239, calibrated Elo (one curve for all formats, as fitted in E003)
  0.6211, bookmaker 0.5841. The E003 decision tree (0.6209) couldn't beat calibrated Elo either, so calibration is
  the cheapest gain available.
- `best_of` is already recorded on every live forecast in `state/forecasts.csv` (5 for Grand Slams, else 3), but
  the model doesn't use it yet.

## What I noticed
- The overconfidence is concentrated in best-of-3, which is most of the tour.
- v0's claimed edges are mostly on underdogs and favourites it rates too strongly. That's overconfidence, not
  real value.

## What I think is going on
Elo has one confidence scale for every match. Best-of-3 is more random than best-of-5, so one scale can't fit both.

## What I want to try
**Hypothesis:** most of the overconfidence is a best-of-3 effect, and a calibration fitted per format removes it.

- **Change:** a logistic calibration on logit(Elo probability), with a separate slope (and intercept) for best-of-5.
  Inputs are the current Elo probability and the format. No new data is needed.
- **Baseline:** raw `elo_v0`, plus the existing single-curve calibration, so we can see whether the format part
  adds anything beyond plain calibration.
- **Evaluation (walk-forward):** for each year Y from 2017 to 2022, fit on matches up to year Y−1 and score year Y.
  Compare log loss match by match, with 95% confidence intervals that resample **whole tournaments** (matches at
  one tournament aren't independent).
- **Keep it only if ALL of these hold** (pre-registered: write them into `experiments/LOG.md` *before* running):
  1. The interval for the per-match log-loss improvement vs raw Elo excludes zero.
  2. It improves in at least 4 of the 6 walk-forward years.
  3. The calibration gap shrinks in **both** formats (best-of-3 gap under ~2 pts; best-of-5 doesn't get worse).
- **If it passes:** one final variant gets **one** sealed test-set look (2023+), and the counter in `LOG.md` goes
  from 4 to 5. Then ship it as a **new** strategy `elo_v1` with its own fresh wallet. `elo_v0` keeps running
  unchanged as the control.
- **If it fails:** log it as a negative result in `LOG.md` (E004) and move on to B or new information sources.

## Constraints / anything else
- Tennis only. EPL is untouched.
- Don't edit or delete `elo_v0` or any past ledger rows. `elo_v1` is added alongside it.
- Tune only on training/validation years. The test years (2023+) get at most the one final look.
- Bet sizing (quarter-Kelly, 5% cap, 5% live min edge) stays the same, so any difference comes from the
  probabilities alone.
- Wallet for `elo_v1`: fresh $5,000 (refill choice when the skill asks).
- Possible follow-up, **not part of this run**: experiment B (adds prior match count and days since last match to
  the same calibration layer). Run it only after A, as a separate experiment.

---

## Fill in on the day (optional, ~5 min)
<!-- Look at the dashboard Bets page, filter to tennis. -->
- Live tennis bets settled since 2026-10-07 (excluding the 3 flagged `identity_error` bets): ___
- How many were best-of-3 vs best-of-5: ___ / ___
- Win rate vs what the model predicted on those bets: ___% vs ___%
- CLV (did we beat the closing odds on average?): ___
- Anything else odd: ___
