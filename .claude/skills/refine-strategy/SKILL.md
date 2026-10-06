---
name: refine-strategy
description: Refine the sports-prediction betting algorithm from the owner's written report. Checks the report's claims against the live ledger, tests the change on training years without overfitting, and ships it as a new versioned strategy with its own wallet beside elo_v0. Use when the user shares a report, observations or ideas about the EPL/ATP models or wallets, asks to refine, improve or tune the algorithm or strategy, or runs /refine-strategy (optionally with a path to a report).
---

# Refine the strategy from the owner's report

The owner writes a report: what they noticed on the dashboard and what they want to try. Your job is to turn it into **one honest experiment**. Check the claims, test the change, then either ship a new strategy version or record why not. The owner is new to ML and betting maths, so explain each step in plain words with a small number example.

## Before anything

0. Work from the project root: `/Users/nicolasdangg/studies/self/machine-learning/sports-prediction`. `cd` there first; all paths below are relative to it. This skill can be invoked from any folder.
1. Read `docs/REFERENCE.md` in full. It defines the system, the rules and the evaluation protocol.
2. Read `experiments/LOG.md`: the past experiments, the **test-set looks used** counter, and the live strategies.
3. Find the report:
   - A path given in the arguments, or else the newest `reports/*.md` that isn't `TEMPLATE.md`.
   - If the owner pasted the report into chat, save it as `reports/YYYY-MM-DD-<slug>.md` first.
   - If there's no report, point them to `reports/TEMPLATE.md` and stop.
4. Run `git pull` so `state/` includes the latest morning run.

## Ground rules (never break these)

- **Never edit or delete an existing strategy** in `daily.py` `STRATEGIES`, and never touch past rows in `state/`. A new idea is a new name: `elo_v1`, `elo_v2`, ... (or a descriptive name like `elo_cap_v1`).
- **Tune only on train years** (EPL 2012/13–2021/22, ATP 2010–2019). Try as many variants as you like there, and count them.
- **Test years are a budget.** Look at them **once per experiment, with the single final variant**. Increment the counter in `experiments/LOG.md`. If the counter is 10 or more, tell the owner the test years are getting worn out and weight live results more heavily.
- **The live wallet is the final judge.** Fewer than ~100 settled bets is anecdote, not evidence. Say so when the report leans on a handful of results.
- **Don't spend Odds API credits.** Don't run `daily.py` for real. Never use the historical-odds endpoint (10× cost).
- Change **one idea per experiment**. If the report has several ideas, rank them, do the most promising, and list the rest as follow-ups.
- Keep `backtest.py`'s v0 behaviour and outputs unchanged. New experiments go in their own script.
- **Live evaluation uses `state/forecasts.csv`** (every forecast, passes included) joined to `state/outcomes.csv`, not just the bets. Measure probability quality (log loss vs `market_p`) on *all* eligible forecasts made after the strategy shipped. Measure betting with CLV (`state/closing.csv`) and P&L. Exclude bets listed in `state/bet_flags.csv`.

## Workflow

### 1. Restate the report as testable claims
Make a short list:
- each **observation** (e.g. "ATP wallet loses on favourites under 1.40"),
- the owner's **hypothesis** for it,
- the **change** they want.

Ask a question only if a change is genuinely ambiguous, such as a stake cap with no number. Otherwise pick a sensible default and say so.

### 2. Check the observations against the data
Use pandas on `state/ledger.csv` (live bets), `state/bankroll_history.csv`, and the backtest bets in `results/*_bets.csv`. For each observation, report:
- whether it holds,
- the sample size,
- whether it could just be noise.

Example check: win rate and ROI by odds band, by sport, by edge size, by surface, by day exposure. Show the small table to the owner. If an observation is false or too thin to act on, say so plainly. That is a useful result.

### 3. Write the change as a precise rule
Make it something code can do exactly. "Be more careful with favourites" is not a rule. "Skip ATP picks with decimal odds < 1.40" is.

Check that it fits the strategy interface (`prob(row)` + `min_edge`). If it needs more (a daily cap, a different stake size, a filter), extend `daily.py` / `wallet.py` **backward-compatibly**, with new optional keys whose defaults reproduce today's behaviour exactly.

Put the rule in a pure function (e.g. in `strategies.py`) so the live job and the experiment use the same code.

### 4. Experiment on train years
Create `experiments/e<NNN>_<slug>.py`. It should:
- use `backtest.load_epl` / `load_atp`, `epl_elo_diffs` / `tennis_probs` and `Wallet`;
- replay the **train years** with `elo_v0` and the new rule **side by side, on the same matches**;
- report log loss where probabilities changed, plus bets, ROI, final bankroll and max drawdown for each;
- tune any new knob here only, and record how many variants were tried.

If the new rule can't beat `elo_v0` on the train years, stop: log a negative result (step 7) and tell the owner why.

### 5. One look at the test years
Run the single final variant on the test years, again side by side with `elo_v0`. Increment **Test-set looks used**.

- **Ship** only if it is not worse than `elo_v0` on the test years.
- A small improvement on test years after heavy tuning on train years is weak evidence. Say how strong the evidence is.

### 6. Ship it (with the owner's OK)
1. Show the owner a summary: the rule, the train and test numbers, and the evidence strength.
2. Ask before changing the live system.
3. **Ask the owner about money**, as one question with these options (they can pick more than one):
   - **New wallet only** (default): the new strategy opens fresh $5,000 wallets per sport. Old wallets carry on untouched as the control group.
   - **Refill the old wallets** back to $5,000, so the control keeps a full bankroll: `uv run python accounts.py refill <sport>:<old_strategy> --reason "<new strategy> shipped (E00N)"`. Explain that the refill is logged in `state/deposits.csv` and **doesn't count as profit**. Charts show profit as bankroll − deposits.
   - **Custom starting amount** for the new strategy: set `"start_bankroll": <amount>` in its `STRATEGIES` entry.
   Never refill or deposit without the owner choosing it. Never withdraw money or rewrite past deposits.
4. Once approved:
   - Add the strategy to `STRATEGIES` in `daily.py` under its new name. Each sport gets a new wallet automatically on the next run, with the opening amount recorded in `deposits.csv`.
   - Apply the refill choice with `accounts.py` (it updates `state/wallets.json` and `state/deposits.csv`), then show `uv run python accounts.py list`.
   - Dry-run what it would bet today **without touching real state**. Everything stays in memory:
     ```python
     import pandas as pd, daily
     preds = pd.read_csv("state/predictions.csv")
     ledger = pd.read_csv("state/ledger.csv")
     wallets = {f"{s}:{n}": {"cash": 1000.0} for s in ("epl", "atp") for n in daily.STRATEGIES}
     now = pd.Timestamp(ledger.placed_at.max())
     _, log = daily.place_bets(preds, ledger.iloc[0:0].copy(), wallets, now)
     print("\n".join(log))
     ```
     Confirm that `elo_v0`'s lines match its real bets in `state/ledger.csv` for that morning, and that the new strategy's bets follow the rule. Only rows with `eligible == True` are ever bet on.
   - Run `uv run python -W ignore tests/smoke_daily.py`. It must end with "all smoke checks passed". If the change added a new interface key, add a check for it there.
   - If this is the second strategy in a sport, make the dashboard tell them apart: the colour is per sport today, so add a line style or shade per strategy. Then run `pnpm build` in `dashboard/` and check it passes.

### 7. Record and commit
1. Add an entry at the top of `experiments/LOG.md` using the template there, even for negative results. Update the counter and the live-strategy list.
2. Update `docs/REFERENCE.md` if the rules, interface or results changed (§5, §6, §9, §11).
3. Commit everything with a message like `elo_v1: skip ATP odds < 1.40 (E003, report 2026-11-02)` and push to `main`. The morning routine picks it up at 06:00 Saigon, and Vercel redeploys.

### 8. Report back to the owner
In plain language:
- what the report claimed and what the data actually showed,
- what was tried and how many variants,
- the train and test results next to `elo_v0`,
- whether it shipped, what to watch on the dashboard (the new wallet's name),
- roughly how many settled bets before judging it,
- the next idea from the backlog.

Keep it short. Use tables for numbers. Explain any new term once.
