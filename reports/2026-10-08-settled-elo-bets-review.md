# Settled Elo bets review — 2026-10-08

The owner noticed that Hijikata was priced near 48% by `elo_v0` against a market estimate near 28%, generating a large losing bet, and suspected the same issue for Trungelliti–Sakamoto.

Reviewed the local ledger used by `/bets`, archived forecasts, closing snapshots, model inputs and betting code. This is a diagnostic review, not a new strategy experiment. No live state or strategy was changed, no API credits were spent, and no historical test-set evaluation was rerun.

## Settled gains and losses exceeding $100

All four were placed at the 2026-10-06 23:02 UTC run for October 7 matches. Probabilities and odds below are the values recorded when betting, not today's updated ratings.

| Pick | Opponent | Elo probability | Market probability, margin removed | Executed odds | Stake | Net P&L |
|---|---|---:|---:|---:|---:|---:|
| Marco Trungelliti | Rei Sakamoto | 55.22% | 34.36% | 2.77 | $223.82 | −$223.82 |
| Rinky Hijikata | Roman Safiullin | 47.60% | 28.57% | 3.35 | $211.43 | −$211.43 |
| Adrian Mannarino | Nikoloz Basilashvili | 58.10% | 48.29% | 1.97 | $173.25 | +$168.05 |
| Wu Yibing | Michael Zheng | 61.94% | 51.97% | 1.83 | $161.54 | +$134.08 |

The two losses cost $435.25; the two wins returned $302.13 in profit, for −$133.12 across these four. The entire settled ledger contains 13 bets, nine wins, $1,085.13 staked and −$29.13 profit (−2.68% ROI). This is too small a live sample to establish calibration or the profitability of a new rule. Dollar comparisons also reflect the October 6 wallet deposit: earlier bets used much smaller balances.

## Why Hijikata was 47.60%

Replaying `backtest.load_atp(state/atp_recent.csv)` with rows dated before October 7 and the live parameters (`k_scale=200`, `surface_weight=0.5`) reproduces the archived probability exactly to four decimals.

| Player | Overall Elo | Hard Elo | Effective rating: 50% overall + 50% hard | Matches in v0 / hard matches |
|---|---:|---:|---:|---:|
| Hijikata | 1672.07 | 1650.25 | 1661.16 | 119 / 83 |
| Safiullin | 1689.72 | 1666.05 | 1677.88 | 134 / 91 |
| Trungelliti | 1587.77 | 1482.32 | 1535.04 | 60 / 13 |
| Sakamoto | 1505.55 | 1491.79 | 1498.67 | 8 / 8 |

Hijikata's effective gap is only −16.72 Elo points. `1 / (1 + 10 ** (16.72 / 400)) = 0.475956`, rounded to 47.60%. The code therefore sees almost equal players. The archived identities are correct and the surface is Hard; these bets do not show the earlier phantom-player identity bug.

`elo_v0` uses match winners and surfaces. It does not use market odds, rankings, score margins, injury news or serve statistics to estimate the probability. Market probability is recorded for comparison; it does not constrain the model's claimed edge.

## Why Trungelliti was the favourite

Trungelliti's +36.37 effective Elo advantage yields 55.2153%, rounded to 55.22%. His overall rating outweighs a slightly *lower* hard-court rating than Sakamoto's. Only eight historical matches inform Sakamoto's rating, which remains near the universal 1500 starting point. The eligibility gate checks identity and long absences, but does not impose a minimum number of career or surface matches or reduce stakes for uncertain ratings.

## Confirmed coverage gaps

The main `data/tennis/atp_tennis.csv` ends September 29. `state/atp_recent.csv` supplements it with some later results, but does not supply a complete intervening history.

The separate local TennisMyLife files contain Safiullin's October 1 Beijing win over Cobolli and October 3 loss to Rublev, plus October 5–6 Shanghai qualifying wins. None appears in his pre-bet v0 history. Sakamoto's September 30 Tokyo loss and October 5–6 Shanghai qualifying wins are also absent. His latest v0 result was September 3.

For 2026 entries dated before October 7, TennisMyLife contains 28 Challenger and 10 qualifying matches for Safiullin, and 29 Challenger and 17 qualifying matches for Sakamoto. These levels never feed v0. This is direct evidence of information being omitted, especially for Sakamoto. It does not establish that filling the gaps would yield exactly the market's probabilities.

These comparisons use the currently available local source files retrospectively; they do not prove every source row was available at the original betting timestamp. No post-match probability from the newer forecaster is substituted for an archived pre-bet forecast: both `forecast_p` and `tml_elo_p` were blank for these bets.

## Why the losses were large

`Wallet.consider()` chooses the outcome with the largest `p × odds − 1`, provided this is at least 5% for live v0. It does not choose the side with the smallest probability disagreement.

- Hijikata: `0.4760 × 3.35 − 1 = +59.46%` claimed expected return. Quarter-Kelly asks for 6.33% of available cash; the 5% cap produces $211.43.
- Trungelliti: `0.5522 × 2.77 − 1 = +52.96%`. Quarter-Kelly asks for 7.48%; the 5% cap produces $223.82.
- Mannarino: +14.46% claimed edge, 3.73% of available cash.
- Wu: +13.35% claimed edge, 4.02% of available cash.

The live implementation sizes against remaining cash at each placement, not cash plus open stakes. The two losses are therefore the stake rule amplifying the largest model disagreements. At Hijikata's actual odds, break-even is 29.85%; at the recorded market estimate of 28.57%, the same bet would have negative expected value. A loss alone cannot tell us which probability was correct.

The last stored median prices give limited additional evidence: Hijikata stayed at 3.35 (61 minutes before start), Trungelliti drifted from 2.77 to 2.80 (31 minutes), and Wu shortened from 1.83 to 1.75 (231 minutes). No closing row is stored for Mannarino. These are approximate snapshots, not exact closing prices or proof of betting skill.

## Implication for the next experiment

The investigation supports incomplete and thin rating histories plus aggressive sizing of model disagreement. It does not support an arithmetic patch to the Elo formula or treating either loss as proof of the player's true win probability.

The existing E009 model already uses broader match coverage and additional features. Its recorded 2020–2022 validation improved probability quality but worsened wallet ROI: v0 −8.1%, TML Elo −14.0%, forecaster −15.3%. It is displayed but intentionally not used for bets. Replacing v0 with it is not an established profitability fix.

A focused next experiment would test a data-coverage eligibility rule in a new strategy: measure whether excluding insufficiently observed players improves results on training-period validation, including the winning bets that such a rule also removes. The specific threshold must not be selected to erase these two losses. A smaller stake or exposure cap is a separate risk-control experiment; it reduces exposure without establishing a predictive edge. Keep v0 as the existing control.

Sources: `state/ledger.csv`, `state/forecasts.csv`, `state/closing.csv`, `state/atp_recent.csv`, local `data/tennis/` and `data/tml/`, `elo.py`, `backtest.py`, `daily.py`, `wallet.py`, `names.py`, and the already-recorded E009 results in `experiments/LOG.md`.
