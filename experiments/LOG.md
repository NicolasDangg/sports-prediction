# Experiment log

Every strategy experiment goes here, **including the ones that failed**. Newest at the top.
The test years are a limited budget: each experiment that looks at them adds to the counter.
If the counter climbs fast, results on the test years stop being trustworthy (see docs/REFERENCE.md §7).

**Test-set looks used: 4** (2 experiments + 2 diagnostic calibration checks on 2023+ during the 2026-10-06 review)
**Live strategies:** `elo_v0` (control, since 2026-10-06) · `news_v1` (ATP only, from the 2026-10-08 run, E007)
**Next up:** collect data for E007 (news veto) and E008 (timing/CLV); judge at the pre-registered sample sizes

---

## I002 · 2026-10-07 · Hand-downloaded tennisdata.app CSVs + tennisabstract Elo page (data check, not a strategy)
- **Files:** `data/retrieved_tennis_data/` (owner download, not committed): tennisdata.app ATP seasons 2021–2026 (79k finished matches: 24k ATP Tour incl. qualifying, 55k Challenger; one match-winner price per side, first-set odds, % serve stats) and tennisabstract's ATP Elo report (as of 2026-09-28). Script: `experiments/i002_external_sources.py`.
- **1. Odds timing:** on 13,854 ATP matches joined to Kaggle, tennisdata.app's price is the same as Kaggle's (corr 0.9985, mean |Δp| 0.001, margin 5.26% both, log loss 0.5872 vs 0.5874). **No timing information**; E008 still relies on our own snapshots.
- **2. Lower-tier markets (market-only, no model, no test-set look):** bookmaker log loss / margin / favourites' actual − implied win rate: ATP main 0.589 / 5.3% / +0.2 pts · ATP qualifying 0.597 / 6.5% / +1.1 · Challenger main 0.618 / 7.2% / +0.6 · Challenger qualifying 0.548 / 7.3% / +1.7. Higher margins below the main tour, prices still calibrated; a small favourite–longshot bias that grows in qualifying, smaller than the margin.
- **3. Our Elo vs tennisabstract:** rank correlation 0.81 on their top 100. Our top players sit higher than theirs (Alcaraz +183, Sinner +162 after rescaling), and low-level players are rated too high too (Mmoh, Torres, Bailly: we start everyone at 1500 and only see main-tour matches). We overrate long-absent players (Draper +201, Djokovic, Dimitrov, Nishikori) and underrate challenger risers (Toby Samuel −171).
- **Leads (each would be its own experiment):** (a) Elo rebuilt on TennisMyLife incl. challengers + qualifying, with an inactivity adjustment; (b) favourite–longshot bias in qualifying/challenger markets, with a model that can price those matches; (c) tennisdata.app gives 2021–2026 challenger odds for backtesting (b).

## E008 · 2026-10-07 · Timing and closing line value from our own odds snapshots · PRE-REGISTERED, collecting data
- **Why:** E004–E006 showed better models from public data don't beat the odds. If an edge exists it's in timing: early prices may be softer than closing ones.
- **Setup:** every odds response is saved (`snapshots.py` → `state/odds_snapshots.csv`); extra ATP snapshots at 06:00 and 12:00 UTC on the free plan with a credit guard. Closing = last snapshot ≤ 180 min before the start.
- **Questions:** (1) does the close beat our first price on log loss? (2) do prices move toward Elo between first sighting and close? (3) per-wallet CLV = our odds / closing median − 1.
- **Decision rules (written before any data):** judge after **150 usable events and 150 ATP bets** (`experiments/e008_timing.py` says when). If prices move toward Elo in > 55% of moves (binomial p < 0.05) **and** `elo_v0`'s mean CLV CI excludes 0 on the positive side, pursue earlier betting (bet at first sighting, more snapshots). Otherwise the market is efficient at the times we can see and timing is dropped. No test-set years involved.

## E007 · 2026-10-07 · News veto (`news_v1`), live only · PRE-REGISTERED, shipped as a live experiment
- **Report:** owner request: feed injuries and news into the prediction.
- **Rule:** `news_v1` = `elo_v0`, except it never backs an ATP player whose news label (Google News headlines, last 7 days, labelled by `anthropic/claude-haiku-4.5` via OpenRouter into a fixed set) is injured / ill / withdrawn / doubt with confidence ≥ 0.6 (`strategies.news_veto`). ATP only, fresh $5,000 wallet. The LLM never sets a probability.
- **Why a veto and not an adjustment:** there's no history of past news, so nothing to fit an adjustment on. Every forecast now logs its news label, so the size of the effect can be learned later.
- **No train/test years:** there's no historical news. Evaluation is live only:
  1. Every vetoed pick that `elo_v0` bet: compare its result with what `elo_v0` expected (win rate vs mean model probability, P&L). The veto helps if vetoed picks lose more than Elo expected.
  2. Log loss of `elo_p` vs `market_p` on forecasts with and without a flag: does the market already price the news (then the veto can't add value)?
- **Decision rule (written before any data):** after **≥ 50 vetoed `elo_v0` bets**: keep `news_v1` if vetoed picks' P&L is negative with a 90% CI below 0; then fit a probability adjustment per label as E00N. Otherwise drop the veto but keep logging labels.
- **Smoke-tested:** veto blocks the injured player, opponent still bettable, ATP-only wallet, no key → "unknown" and identical to `elo_v0`.

## E006 · 2026-10-07 · XGBoost + serve/return stats (Sackmann) · FAILED pre-registered rule 3 (wallet), not shipped
- **Report:** owner request (follow-up to E005; the video's model used Sackmann's serve stats).
- **Data:** Jeff Sackmann `tennis_atp` 2008–2024, main tour + qualifying/challenger (original repo taken down in 2026; public mirror pinned to commit `8e5415c`, cross-checked against a second mirror: 2,796/2,796 shared 2019 matches identical). `uv run python fetch_data.py sackmann`.
- **Script:** `experiments/e006_serve_stats.py` → `results/e006_serve_stats.json`; market-blend diagnostic `experiments/e006_market_blend.py` (`uv run --group experiments ...`).
- **Hypothesis:** how a player wins points (serve and return quality, aces, double faults, break points) carries information the Elo-based features in E005 miss.
- **Features added (fixed in advance, not tuned):** per player, exponentially decayed totals over all prior matches with stats (×0.95 per match, ≈ 14-match half-life; all levels incl. challengers), ≥ 3 prior stat matches else missing: serve / return / total points won %, ace rate, double-fault rate, first-serve-in %, break points saved %, break points converted %, as P1 − P2 differences, plus a serve-vs-return matchup term and log count of stat matches. Joined to the odds data by name keys + tournament week: 96–99.8% of matches linked per year (spot-checked).
- **Protocol:** identical to E005; baseline = E005's features retrained in the same script (reproduced E005 exactly). **16 variants per feature set.** Chosen for E006: depth 2, lr 0.1, min child 50, 325 trees.
- **Pass rules (pre-registered):** (1) CI of improvement vs E005 excludes 0; (2) ≥ 2/3 years; (3) wallet ROI not worse than `elo_v0`.
- **Validation 2020–2022 (6,178 matches):**

  | | Log loss | Accuracy | Gap Bo3 | Gap Bo5 | Wallet (live rules, $1,000) |
  |---|---:|---:|---:|---:|---|
  | Raw Elo (`elo_v0`) | 0.6232 | 63.9% | +5.3 | −0.7 | 3,847 bets, ROI −8.0%, bust |
  | E005 XGBoost | 0.6146 | 64.6% | +1.1 | −2.2 | 4,069 bets, ROI −11.3%, bust |
  | **E006 + serve stats** | **0.6048** | **65.9%** | +2.2 | +0.7 | 3,397 bets, ROI **−9.3%**, bust |
  | Bookmaker | 0.5841 | 68.3% | 0.0 | −1.9 | |

  Improvement vs E005 +0.0098/match, 95% CI [+0.0060, +0.0136] ✅ · 3/3 years (+0.0079, +0.0083, +0.0121) ✅ · ROI −9.3% vs −8.0% ❌. Closes about a third of the gap to the bookmaker (0.031 → 0.021).
- **Feature importance (gain):** Elo log-odds 32%, Elo gap 16%, ranking 12%, surface Elo 12%, serve-vs-return 6%, points 6%, total points won 5%, serve won 2%.
- **Diagnostic (post-hoc, not a pass rule):** does the model add anything *on top of* the market? Logistic blend of logit(bookmaker) and logit(model), each 2020–22 year scored by a blend fitted on the other two: model weight +0.10 / −0.01 / +0.03; log loss bookmaker 0.5841 vs blend 0.5840, improvement +0.0002, 95% CI [−0.0008, +0.0011]. **The market already prices serve/return form.** This is the clearest evidence yet that public historical stats can't beat closing-ish odds.
- **Test-set look:** no. Counter unchanged at 4.
- **Decision:** not shipped (also not deployable: the stats source ended in 2024). Best probability model to date (useful for the dashboard / forecasts, not for betting). Next ideas must be information or timing the market lacks: early-line timing / CLV on opening prices, news and injuries (v3 roadmap), or markets where the bookmaker is softer (e.g. lower-tier events, other books vs Pinnacle).

## E005 · 2026-10-07 · XGBoost on pre-match ATP features · FAILED pre-registered rule 3 (wallet), not shipped
- **Report:** owner request (Green Code "I Trained AI to Predict Sports (again)": XGBoost vs IBM at Wimbledon 2025; their final 66.3% vs IBM 63.8% vs bookmakers 72% accuracy).
- **Script:** `experiments/e005_xgboost.py` → `results/e005_xgboost.json`. Run with `uv run --group experiments ...` (xgboost lives in an optional dependency group so the morning routine never installs it).
- **Hypothesis:** gradient-boosted trees on E003's pre-match features (plus Elo log-odds and format) give better probabilities than Elo calibrated per format.
- **Protocol:** fit 2010–2017, hyperparameters chosen on 2018–2019 (**16 variants**: depth {2,3,4,6} × learning rate {0.03, 0.1} × min child weight {50, 200}, early stopping), refit 2010–2019, scored 2020–2022 once. Rows mirrored; predictions averaged over both player orders. Chosen: depth 6, lr 0.03, min child 50, 74 trees.
- **Pass rules (pre-registered):** (1) 95% tournament-bootstrap CI of improvement vs calibrated Elo excludes 0; (2) better in ≥ 2 of 3 years; (3) wallet ROI not worse than `elo_v0`.
- **Validation 2020–2022 (6,178 matches):**

  | | Log loss | Accuracy | Gap Bo3 | Gap Bo5 | Wallet (live rules, $1,000) |
  |---|---:|---:|---:|---:|---|
  | Raw Elo (`elo_v0`) | 0.6232 | 63.9% | +5.3 | −0.7 | 3,847 bets, ROI −8.0%, bust |
  | Calibrated Elo (E004 rule) | 0.6185 | 63.9% | +2.6 | +1.0 | 3,921 bets, ROI −8.1%, bust |
  | **XGBoost** | **0.6146** | **64.6%** | +1.1 | −2.2 | 4,069 bets, ROI **−11.3%**, bust |
  | Bookmaker | 0.5841 | 68.3% | 0.0 | −1.9 | |

  Improvement vs calibrated Elo +0.0039/match, 95% CI [+0.0011, +0.0068] ✅ · 3/3 years (2020 +0.0049, 2021 +0.0063, 2022 +0.0012) ✅ · ROI −11.3% vs −8.0% ❌.
- **Feature importance (gain):** Elo log-odds 44%, Elo gap 28%, surface Elo 10%, ranking 6%, points 3%, rust 2%, format 2%, rest ≈ 1% each. Same picture as E003: Elo carries almost everything.
- **Why better probabilities still lose money:** the model is still ~0.03 log loss behind the bookmaker. Bets only happen where we disagree with the market, and with no new information those disagreements are mostly our errors. A sharper model disagrees in more places (4,069 vs 3,847 bets) and loses more.
- **Test-set look:** no. Counter unchanged at 4.
- **Decision:** not shipped. The best probability model so far, but no betting edge. Next: E006 adds information the market may price imperfectly (Sackmann serve/return stats); a model only becomes bettable if it closes most of the 0.03 gap to the bookmaker.

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
