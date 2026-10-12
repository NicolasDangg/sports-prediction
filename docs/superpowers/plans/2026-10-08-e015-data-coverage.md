# E015: Minimum tennis rating coverage — implementation plan

> For future agentic implementation: use `executing-plans` to work through the checklist. This document specifies future work; it does not authorize activating a strategy or moving wallet money.

**Status:** Planned, 2026-10-08. No experiment run; zero variants evaluated; no new test-set look.

**Goal:** Test whether refusing ATP bets when either player's Elo has too little match history improves the betting results of the unchanged `elo_v0` probabilities.

**Architecture:** Reuse `TennisElo`, the current v0 history and `Wallet`. Add a small, symmetric eligibility function and evaluate it in an isolated experiment. Only after a successful evaluation should a new ATP strategy consume pre-match counts; `elo_v0` stays the control.

**Tech stack:** Existing Python, pandas and NumPy; no new dependencies.

The owner originally requested E0013, then selected **E015** because E013 and E014 already exist. E013 remains the casual-bettor experiment.

## Evidence and scope

See [the October 8 diagnostic](../../../reports/2026-10-08-settled-elo-bets-review.md). Sakamoto had eight total/eight hard-court matches in v0 before the $223.82 losing Trungelliti bet. Hijikata had 119/83 and Safiullin 134/91 before the $211.43 Hijikata loss. Both archived probabilities were reproduced from their pre-match ratings.

**This gate would reject the Sakamoto matchup under every proposed threshold. It would allow the Hijikata matchup.** It measures how much evidence the current rating has, not whether that evidence is complete, recent enough, or predictive enough. It must not be presented as a fix for every large model/market disagreement.

Three approaches were considered:

| Approach | What changes | Decision |
|---|---|---|
| Minimum observed match counts | Bet eligibility only | E015: smallest isolated test |
| Broader history and uncertainty-aware ratings | Probabilities and coverage | Separate follow-up; E009 already tested broader history with worse wallet ROI |
| Lower stakes/daily exposure | Financial exposure only | Separate risk experiment |

E015 does not add Challenger matches, change the Elo formula, blend market probabilities, filter odds bands, alter stakes or repair the input feed. Mixing those changes would prevent attributing the result to the gate.

## Exact candidate rule

For an upcoming match between A and B on surface s, let `N_A`, `N_B` be counts of prior matches that actually updated each player's **v0 overall rating**, and `N_As`, `N_Bs` counts that updated their **v0 rating on s**.

```text
coverage_ok = min(N_A, N_B) >= min_total
              AND min(N_As, N_Bs) >= min_surface

bettable = existing identity/staleness eligibility AND coverage_ok
```

The gate applies to the whole matchup, before choosing either outcome. Failing it means no bet on either player. Passing it leaves both probabilities, execution odds, +5% minimum edge, quarter-Kelly and 5% stake cap unchanged. Live staking continues to use remaining cash as it does today.

Predeclare exactly six threshold pairs:

```python
THRESHOLDS = [(n, s) for n in (10, 20, 40) for s in (5, 10)]
```

These are design candidates, not validated settings. No default threshold is shipped. Do not add thresholds after seeing validation results. Equal counts pass; missing, non-finite, negative or fractional counts fail closed for this strategy. The existing `eligible` column must not be changed globally, because that would also change v0/news strategies.

## Point-in-time feature contract

Use `elo.n_overall` and `elo.n_surface`; do not count rows from a richer dataset that did not feed that rating.

- Historical replay: read both players' counts and probability **before** `elo.update()` for the current match. Use `.get(..., 0)` for unseen players. Replay all earlier history as warmup, even though scoring starts in 2010.
- Preserve `backtest.load_atp()` stable chronological order so probabilities reproduce v0. The source often has dates without start times. Disclose within-day ordering uncertainty; this is a retrospective replay, not proof of information available before every real kickoff.
- Live forecasting: write `min_total_matches` and `min_surface_matches` into the shared match context in `daily.predict_atp()`. Both outcome rows receive the same values. These two fields are sufficient for the gate; player-level diagnostics can be produced by the experiment from its replay.
- When identities are unresolved, counts are missing and the new rule rejects the match. Old archive rows lacking counts remain missing; do not backfill them from today's ratings.
- Keep all forecasts, including rejected matches, with `coverage_ok` and a reason in the experiment output. If deployed, append a strategy-specific `coverage_reason` to new forecasts (e.g. `insufficient_total`, `insufficient_surface`, `missing_counts`, `ok`). Do not rewrite prior archive rows.
- No TML hindsight reconciliation in E015. A future source-completeness experiment needs download/availability timestamps and match-level deduplication; a later file cannot prove what was knowable at the original bet time.

## Evaluation protocol, fixed before running

### 1. Development and selection: train years only

Use ATP 2010–2016 for implementation diagnostics. Select one pair on **2017–2019**, still within the project's 2010–2019 training budget. Run all six pairs once and report every result, including failures. Do not choose thresholds using the October 2026 motivating bets.

For each v0 bet opportunity j, record its decimal price `o_j` and win indicator `y_j`. Its unit-stake profit is `r_j = o_j*y_j - 1`. The gate's profit on that same opportunity is `g_j*r_j`, where `g_j` is 0 or 1. The paired difference is:

```text
d_j = (g_j - 1) * r_j
```

Compare `mean(d_j)` over **all baseline opportunities**, including zero profit for skipped bets. Also report flat ROI on accepted bets and accepted/removed counts. This exposes the profits forfeited by skipping winners and prevents comparing two unexplained, different samples.

Candidate eligibility for selection: retain at least 50% of baseline bet opportunities and at least 500 accepted bets over 2017–2019. Select the pair with the highest `mean(d_j)`; ties within `1e-12` prefer smaller `min_total`, then smaller `min_surface`. If no pair qualifies, or the selected pair has nonpositive improvement or lower accepted-bet flat ROI than v0, record failure and stop.

### 2. Validation: 2020–2022, one frozen candidate

Evaluate the selected pair once. Report both strategies on identical source rows/prices and report the accepted and rejected subgroups. Gate passes validation only if all hold:

1. At least 500 accepted bets and at least 50% of baseline opportunities retained.
2. Paired unit-profit improvement has a tournament-cluster bootstrap 95% interval entirely above zero.
3. Accepted-bet flat ROI exceeds the unfiltered v0 flat ROI, and unit-profit improvement is positive in at least two of the three individual years.
4. The chronological wallet ends at least as high as v0 and has no worse maximum drawdown.

Use 2,000 bootstrap replicates and `np.random.default_rng(15)`, resampling whole `year + Tournament` clusters and averaging over their bet opportunities. Reuse the structure of `cluster_ci` in `experiments/e004_format_calibration.py`, but give this experiment its own RNG so results do not depend on calls made by earlier experiments. The interval pertains to fixed-stake paired returns; it is not a confidence interval for a compounded wallet.

Because probabilities do not change, all-match log loss and Brier score must equal v0 exactly. Show v0 and market scores separately on retained/rejected subsets for diagnosis, with denominators. Improved subset scores do not mean the model itself improved.

### 3. Existing historical test window: one look only after validation passes

Evaluate the single frozen candidate on **2023-01-01 through 2026-10-05**. Increment the test-look counter in both the log and registry once. Do not call this virgin or unseen data: prior project experiments already used these years. October 6–7 motivating bets are excluded from this test decision and can only appear as labelled examples.

For a future paper comparison, require at least 500 accepted bets, at least 50% retention, nonnegative paired unit-profit improvement, flat ROI no lower than v0, final wallet no lower and maximum drawdown no worse. Failure means `not_shipped`; do not retune on this window. Passing means eligible for a separately authorized live paper comparison, not evidence of profitability. Report explicitly if both versions still lose money.

### 4. Wallet conventions and forward evaluation

Reuse `Wallet(min_edge=0.05)` and the existing $1,000 historical starting balance. Both backtest wallets settle immediately after each match, as existing experiments do. Report that this does not reproduce overlapping live cash commitments; do not advertise it as an exact live simulation. Reuse prices from the same historical row and never substitute later best prices or closing odds as execution prices.

If activated later, use a fresh `atp:elo_coverage_v1` paper wallet with the project's normal $5,000 opening balance. First forward review is after at least 100 settled accepted bets **and** 100 settled v0 bets excluded by the gate; report uncertainty if this takes a long time. No P&L-based early promotion. Join immutable forecasts to outcomes, exclude existing identity-error flags, and show paired fixed-stake outcomes, wallet results, number rejected and CLV with its sample count. Use only closing snapshots meeting the existing timestamp-quality rules. Evaluate full-population and accepted/rejected forecast scores; do not select only placed bets for probability-quality claims.

## Implementation checklist for later

### Task 1: Shared gate and one runnable check

Files: modify `strategies.py`; create `tests/check_coverage.py`. Use one assert-based script and existing dependencies.

- [ ] Add the pure helper below. Reject bad count fields only; callers supply the frozen positive integer thresholds from the experiment result.

```python
def coverage_ok(row, min_total: int, min_surface: int) -> bool:
    counts = []
    for key in ("min_total_matches", "min_surface_matches"):
        try:
            n = float(row.get(key))
        except (TypeError, ValueError):
            return False
        if not np.isfinite(n) or n < 0 or not n.is_integer():
            return False
        counts.append(n)
    return counts[0] >= min_total and counts[1] >= min_surface
```

- [ ] Before implementation, make these assertions fail for the absent helper; afterward make them pass. Give the script a root-path import setup like the existing smoke test.

```python
assert coverage_ok({"min_total_matches": 20, "min_surface_matches": 10}, 20, 10)
assert not coverage_ok({"min_total_matches": 19, "min_surface_matches": 10}, 20, 10)
assert not coverage_ok({"min_total_matches": 20, "min_surface_matches": 9}, 20, 10)
assert not coverage_ok({}, 20, 10)
for bad in (None, "bad", float("nan"), float("inf"), -1, 2.5):
    assert not coverage_ok({"min_total_matches": bad, "min_surface_matches": 10}, 20, 10)
    assert not coverage_ok({"min_total_matches": 20, "min_surface_matches": bad}, 20, 10)
```

Command: `uv run python tests/check_coverage.py`. No test framework is needed.

### Task 2: Isolated replay and metrics

Create `experiments/e015_data_coverage.py`; future outputs are `results/e015_data_coverage.json` and `results/e015_data_coverage_bets.csv`.

- [ ] Import existing `backtest`, `TennisElo`, `Wallet` and the shared gate. Do not change v0 loaders, Elo parameters or historical output files.
- [ ] Capture pre-update features using this order inside the replay, with `elo = TennisElo(k_scale=200, surface_weight=0.5)`:

```python
p = elo.prob(a, b, surface)
counts = {
    "min_total_matches": min(elo.n_overall.get(a, 0), elo.n_overall.get(b, 0)),
    "min_surface_matches": min(elo.n_surface.get((a, surface), 0),
                               elo.n_surface.get((b, surface), 0)),
}
# Store p and counts for the row, then update after its known result.
elo.update(winner, loser, surface)
```

- [ ] Verify all replay probabilities equal `bt.tennis_probs(df, **ATP_PARAMS)` within `1e-12`. Verify the first ever matchup has zero counts; after one result the next matchup has one; swapping players preserves the gate and complements p; switching surface changes only surface counts.
- [ ] Build baseline options once per match with valid odds, obtain the v0 selection, then apply the gate to both sides. Keep fixed-stake comparisons separate from independently compounded wallets: different prior bets change their balances.
- [ ] Implement the split/selection/stop rules above. Default invocation runs train selection and, only if it passes, validation. `--test` loads the frozen successful result and adds the single test evaluation; refuse if one is already recorded for this experiment or the input hashes/thresholds differ.
- [ ] Record source SHA-256 hashes, date ranges, parameters, selected pair, six candidate results, retention, accepted/rejected counts, both flat ROI and wallet metrics, seed, bootstrap interval, per-year summaries, data-order caveat and verdict. No uncomputed metric gets a fabricated zero.
- [ ] Keep every baseline opportunity in the diagnostic CSV with date, tournament, players, surface, counts, p, odds, pick, outcome, gate reason and both unit-profit columns. These result rows are analysis artifacts, never replacement ledger entries.

Commands, after the script exists:

```sh
uv run python -W ignore experiments/e015_data_coverage.py
# Only after frozen validation passes and the test look is logged:
uv run python -W ignore experiments/e015_data_coverage.py --test
```

### Task 3: Record the decision before any live change

- [ ] Update E015 in `experiments/LOG.md` and `experiments/registry.json` with actual numbers, variant count and outcome. Update test-look counts only if the test stage ran. Preserve failed results.
- [ ] If the experiment fails or is inconclusive, stop here with its artifacts. Do not turn a failure into a different experiment by moving the threshold.

### Task 4: Future approved live integration

Files: `daily.py`, `tests/smoke_daily.py`, `docs/REFERENCE.md`, log and registry. This task is contingent on evidence and a later instruction to activate it.

- [ ] Populate the two count fields in `predict_atp()`'s match context, safely handling unresolved identities.
- [ ] Bind the selected pair from the frozen result into the new ATP-only strategy. Reuse the existing probability-veto pattern rather than adding a new strategy interface:

```python
# MIN_TOTAL and MIN_SURFACE are literal values copied from the successful,
# frozen E015 result at integration time. No thresholds have been selected yet.
"elo_coverage_v1": {
    "prob": lambda row: row["elo_p"] if strategies.coverage_ok(
        row, MIN_TOTAL, MIN_SURFACE) else 0.0,
    "min_edge": 0.05,
    "sports": ("atp",),
}
```

- [ ] Add smoke cases showing a high-edge insufficient-history match is skipped only by the new strategy, a qualifying match uses unchanged p/odds/staking, absent counts fail closed, and v0's existing bets remain identical. Add archive checks for count/reason fields and player-order symmetry.
- [ ] Run `uv run python -W ignore tests/smoke_daily.py` against its temporary state copy. Perform the in-memory placement comparison described in the refine-strategy skill. Do not invoke real `daily.py` for a test.
- [ ] Record the activation date and frozen thresholds. No refills, deposits, historical edits or automated activation are part of E015 documentation.

## Research follow-ups

The [GPT-6-Astra High research review](../../2026-10-08-tennis-probability-formulas.md) documents alternative probability formulas, variables, worked examples, primary sources and evaluation requirements. Those are independent hypotheses, not extra E015 variants. A model that agrees more closely with the market can forecast better while still failing to produce profitable execution prices. Preserve E009's failed wallet result when considering richer data or more elaborate ratings.
