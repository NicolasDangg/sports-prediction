# Experiment log

Every strategy experiment goes here, **including the ones that failed**. Newest at the top.
The test years are a limited budget: each experiment that looks at them adds to the counter.
If the counter climbs fast, results on the test years stop being trustworthy (see docs/REFERENCE.md §7).

**Test-set looks used: 4** (2 experiments + 2 diagnostic calibration checks on 2023+ during the 2026-10-06 review)
**Live strategies:** `elo_v0` (control, since 2026-10-06)
**Next up:** E005, gradient boosting (XGBoost) on pre-match ATP features incl. serve/return stats; then recency-weighted calibration (E004 follow-up)

---

## E004 · 2026-10-07 · Format-aware calibration of tennis Elo (experiment A) · FAILED pre-registered rule 3, not shipped
- **Report:** reports/2026-10-06-experiment-a-format-calibration.md
- **Script:** `experiments/e004_format_calibration.py` → `results/e004_format_calibration.json`. Rule in `strategies.format_calibrated`.
- **Hypothesis:** Elo is overconfident in best-of-3 only; a calibration curve with its own slope for best-of-5 fixes it.
- **Change:** `p' = sigmoid(slope_format × logit(p))` on top of raw `elo_v0` probabilities, one slope for best-of-3 and one for best-of-5. No intercept, so swapping the players gives exactly `1 − p'`. Compared against raw Elo and a single curve. **Variants tried: 1.**
- **Pass rules (pre-registered before running), ALL must hold:** (1) 95% CI of the per-match log-loss improvement vs raw Elo excludes zero (tournament bootstrap); (2) better in ≥ 4 of 6 walk-forward years; (3) calibration gap best-of-3 under 2 pts and best-of-5 no worse than raw.
- **Walk-forward 2017–2022 (fit 2010…Y−1, score Y; 13,771 matches, 2,798 best-of-5):**

  | | Log loss | Gap Bo3 | Gap Bo5 |
  |---|---:|---:|---:|
  | Raw Elo (`elo_v0`) | 0.6243 | +5.1 | −1.6 |
  | Single curve | 0.6211 | +3.5 | −3.3 |
  | **Per-format** | **0.6192** | +2.6 | +0.4 |

  Improvement vs raw +0.0051/match, 95% CI [+0.0037, +0.0064] ✅ · better in 6/6 years ✅ · Bo3 gap 2.6 pts ❌ (Bo5 fine). Format adds +0.0019 [+0.0009, +0.0028] beyond a single curve, so the format effect is real.
- **Wallet (walk-forward years, live rules, $1,000):** raw Elo 8,098 bets, ROI −7.7%, bust · per-format 8,123 bets, ROI −8.3%, bust. Better probabilities did not make the bets profitable; the bookmaker is still far ahead (≈0.58).
- **Why the gap stays:** the fitted best-of-3 slope falls every year (0.87 in 2017 → 0.79 in 2022), so Elo is getting more overconfident over time and a curve fitted on all past years lags. Final 2010–2022 fit: Bo3 0.793, Bo5 1.116 (best-of-5 is slightly *under*-confident).
- **Test-set look:** no (failed before it). Counter unchanged at 4.
- **Live evidence used:** 2 settled ATP bets (both won). Anecdote.
- **Decision:** not shipped. Follow-ups: (a) recency-weighted or rolling-window calibration (new experiment, as the drift suggests); (b) use `logit(p)` and best-of-5 as inputs to the gradient-boosting experiment (E005), where the model can learn the format effect itself.

## E003 · 2026-10-06 · Decision tree on ATP pre-match features (exploration, not shipped)
- **Report:** owner request ("find the variable that best splits the data… split, split, split").
- **Script:** `experiments/e003_decision_tree.py` → `results/e003_decision_tree.json` (shown on the dashboard Model page).
- **Features (all pre-match, P1 − P2):** Elo gap, surface Elo gap, log ranking ratio, log points ratio, last-10 win rate, log career matches, days since last match, best-of-5, surface. Training rows mirrored (players swapped) so listing order can't be learned; P1 win rate is 50.0%.
- **Best single split (Gini gain, train 2010–19):** Elo gap 0.064 > surface Elo 0.061 > ranking 0.054 > points 0.054 > form 0.030 > experience 0.030 > rest ≈ 0.
- **Depth chosen on validation 2020–22:** 6 (10 depths tried, min 300 matches per leaf). Elo gap carries 86% of the tree's importance.
- **Validation log loss (6,167 matches):** tree 0.6209 · calibrated Elo 0.6211 · raw Elo 0.6239 · bookmaker 0.5841.
- **Conclusion:** a tree on the same information only matches calibrated Elo. Rankings and form add almost nothing once Elo is known. **Not shipped. No test-set look.** Points toward experiment A (calibration + format) as the cheap gain, and toward new information sources for anything more.

## I001 · 2026-10-06 · Step 0: data and execution integrity (infrastructure, not a strategy change)
- **Why:** the review found problems that invalidate experiments: misresolved player identities (phantom 1500-rated players → fake edges, 3 live bets affected), no log of forecasts we passed on, synthetic median execution prices, and silent 7-day voids.
- **Changes:** tennis name resolver with an identity gate (unknown/ambiguous/stale → not bettable; untrusted results not stored); `aliases.csv`; append-only `forecasts.csv` / `outcomes.csv` / `closing.csv`; bets execute at a real bookmaker quote ≤ median, with bookmaker and quote time recorded; settlement falls back to history files and marks `unresolved` instead of `void`; `deposits.csv` + `accounts.py`; wallets raised to $5,000 (deposit, not profit); `tests/smoke_daily.py`.
- **Effect on elo_v0:** same probabilities and rules. Execution price is now a real quote at or below the median (slightly worse or equal), and untrusted-identity matches are skipped. Its live record from 2026-10-07 reflects this. The 3 bets placed on 2026-10-06 against misresolved players are flagged `identity_error` in `bet_flags.csv`; exclude them from evaluation.
- **No test-set look.**

## E002 · 2026-10-06 · Blend Elo into the market probability (negative result)
- **Report:** none (exploration during setup)
- **Hypothesis:** starting from the bookmaker's probability and nudging it toward Elo (`p = market + w × (elo − market)`) keeps the market's accuracy while still finding value.
- **Tried:** w ∈ {0, 0.1, 0.2, 0.3, 0.5} × min_edge ∈ {3%, 5%}, on both train and test years. **This counts as 1 test-set look.**
- **Result:** log loss got worse at every w > 0 in both sports and both periods. Every wallet lost (ROI −7% to −74%).
- **Conclusion:** Elo has no information the closing odds lack. Not shipped. New edges must come from information or timing the market doesn't have.

## E001 · 2026-10-06 · Elo v0 baseline
- **Hypothesis:** tuned Elo plus quarter-Kelly finds value against the bookmaker.
- **Tuned on train years:** EPL k=15, home_adv=40, carryover=0.9 · ATP k_scale=200, surface_weight=0.5. **1 test-set look.**
- **Result (test years):** EPL log loss 0.9846 vs bookmaker 0.9635 · ATP 0.6298 vs 0.5888. Backtest wallets: EPL −12% ROI, ATP −28% ROI (bust).
- **Conclusion:** loses to the market; claimed edges are mostly overconfidence on underdogs. Shipped live anyway as **`elo_v0`, the control group** every later version must beat.

---

<!-- Template for new entries (copy above the newest entry):

## E00N · YYYY-MM-DD · <short title>
- **Report:** reports/<file>.md
- **Hypothesis:**
- **Change:** (new strategy name, exact rule)
- **Train-period result:** (log loss / wallet vs elo_v0 on the same years; how many variants tried)
- **Test-set look:** yes/no. If yes, the one final variant only, and the counter above incremented
- **Live evidence used:** (ledger stats, n settled bets)
- **Decision:** shipped as `<name>` / not shipped, and why
-->
