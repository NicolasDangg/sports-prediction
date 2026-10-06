# Experiment log

Every strategy experiment goes here, **including the ones that failed**. Newest at the top.
The test years are a limited budget: each experiment that looks at them adds to the counter.
If the counter climbs fast, results on the test years stop being trustworthy (see docs/REFERENCE.md §7).

**Test-set looks used: 2**
**Live strategies:** `elo_v0` (control, since 2026-10-06)

---

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
