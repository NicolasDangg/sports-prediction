# E015: minimum ATP rating coverage

**Decision: not shipped.** The frozen validation passed, but the one registered historical test failed its wallet finish and drawdown checks. No strategy is active. No live ledger, wallet, or bet rule changed.

E015 tests a single idea: skip a match when either player's existing v0 Elo has too few previous matches overall or on the tournament surface. It keeps the Elo probabilities, prices, edge threshold and stakes fixed. Six pairs were declared before evaluation: overall minimum {10, 20, 40} × surface minimum {5, 10}. Selection was restricted to 2017–2019; validation to 2020–2022.

The replay included 58,955 matches from January 2000 through December 2022 as Elo warmup and evaluation history. Each player's counts were recorded before the match result updated Elo. The maximum probability difference from the existing `backtest.tennis_probs` replay was **zero**. Only 4,251 of 2017–2019 matches created an Elo v0 betting opportunity at +5% edge with valid prices; these same opportunities form the paired comparison for every candidate. “Paired improvement” is the average amount the gate changes profit per original opportunity, counting a skipped bet as zero. Skipping a winner therefore loses its profit; skipping a loser avoids its loss.

## Selection, 2017–2019

| Overall / surface minimum | Accepted / 4,251 | Retained | Gated flat ROI | Paired improvement per original bet |
|---|---:|---:|---:|---:|
| 10 / 5 | 3,484 | 82.0% | −10.25% | +2.76¢ |
| 10 / 10 | 3,152 | 74.1% | −9.74% | +3.93¢ |
| 20 / 5 | 3,222 | 75.8% | −10.11% | +3.50¢ |
| 20 / 10 | 3,010 | 70.8% | −9.77% | +4.24¢ |
| 40 / 5 | 2,717 | 63.9% | −10.15% | +4.67¢ |
| **40 / 10** | **2,596** | **61.1%** | **−10.10%** | **+4.99¢** |

Unfiltered v0 flat ROI was −11.16%. All six passed the predeclared minimum sample and 50% retention. The rule selects 40/10 because it had the largest paired improvement. It still lost about ten cents per dollar staked, so this is a smaller historical loss, not a profitable strategy. Its $1,000 immediately settling wallet finished at $0.29; v0 finished at $0.10.

## Frozen validation, 2020–2022

The selected 40/10 gate retained **2,256 of 3,847** v0 betting opportunities (58.6%) and skipped 1,591. At equal stakes, v0 returned −9.84%; accepted bets returned −9.67%; rejected bets returned −10.09%. The mean paired improvement was **+4.17¢ per original opportunity**, with a 95% tournament-year cluster-bootstrap interval of **+1.02¢ to +7.05¢** (159 year/tournament clusters; 2,000 replicates, seed 15).

The paired improvement was positive in all three years: +7.88¢ in 2020, +2.91¢ in 2021 and +3.50¢ in 2022. The accepted-bet flat ROI was slightly worse than v0 in 2021 and 2022 individually, but higher over all validation years combined, as specified in the predeclared rule.

Both wallet replays still essentially went broke. Starting from $1,000, v0 finished at $0.09 and the gate at $0.20; each had over 99.98% maximum drawdown. Their small final difference satisfies the wallet comparison, but is not a meaningful safety margin. Immediate settlement also does not reproduce overlapping live cash commitments.

The gate does **not** improve probabilities. On all 6,178 validation matches, v0 and gated Elo both scored 0.6232 log loss and 0.2176 Brier score, compared with 0.5841 and 0.2006 for the market. Accepted and rejected subsets scored exactly the same under v0 and gated Elo, as intended.

## Frozen one-look test, 2023-01-01–2026-10-05

The data contained 9,859 scored matches through **2026-09-29** and 6,048 baseline betting opportunities. The 40/10 gate accepted 3,487 (57.7%), above the predeclared 500-bet and 50% retention minimums. Equal-stake results improved: accepted bets returned −11.08% versus v0's −13.03%, or +6.64¢ per original opportunity. That is a smaller historical loss, not positive ROI.

| Year | Baseline ROI | Accepted ROI | Paired improvement per original opportunity |
|---|---:|---:|---:|
| 2023 | −16.52% | −18.79% | +6.13¢ |
| 2024 | −16.74% | −9.58% | +11.12¢ |
| 2025 | −9.50% | −7.75% | +4.81¢ |
| 2026 through Sep 29 | −8.35% | −7.96% | +3.89¢ |

Three of four years had better accepted flat ROI than v0; 2023 was worse. The paired comparison was positive every year. By surface, paired gains were strongest on grass (+11.10¢, 783 baseline opportunities), then hard (+6.03¢, 3,272), and clay (+5.90¢, 1,993); accepted clay bets themselves lost more than v0 (−15.26% vs −14.38%).

The test failed both wallet safeguards. Under the existing quarter-Kelly/5%-cap replay, v0 finished at **$0.10** and the gate at **$0.09** from $1,000; both lost essentially the full bankroll. The gate's 99.991% maximum drawdown was slightly worse than v0's 99.990%. Thus the flat-stake pairing is directionally encouraging, but does not satisfy the frozen requirement that bankroll outcome and drawdown be no worse. This one-look result is final; do not tune against it or rerun it.

The look was consumed at 2026-10-12 11:21 UTC, before test outcomes were loaded. The global counter is now **6**. These dates were previously examined by project work and are not an untouched test set. The experiment is **not shipped** and does not qualify the gate for activation or a paper wallet.

## Limits and reproduction

Counts measure only matches that updated the current v0 rating. This tests limited observed rating history, not missing recent results, source completeness, current player fitness or probability calibration. Historical source rows have dates but usually no match start times, so ordering within a day is an approximation. Historical odds timestamps are not established. The selected gate only covers ATP.

The original deterministic development/selection/validation command was `uv run python -W ignore experiments/e015_data_coverage.py`. It records all six gate masks and reasons for every scored match in `results/e015_data_coverage_bets.csv`, plus summaries and source hashes in `results/e015_data_coverage.json`. Both recorded stages now refuse to run again. The separate `--test` command is guarded by the frozen result and the experiment log's one-look counter; do not remove the artifacts to bypass it. For implementation verification without historical outcomes, run `uv run python tests/check_coverage.py` and `uv run python tests/check_e015.py`. The [original plan](../docs/superpowers/plans/2026-10-08-e015-data-coverage.md) is preserved verbatim as the hashed pre-experiment protocol; its planned status describes the time it was written.
