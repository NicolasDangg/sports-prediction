# Closing Line

**Can a model beat the bookmaker? This project tries to find out honestly, with paper money.**

Closing Line forecasts **Premier League football** and **ATP tennis** matches, places virtual bets on them every morning, and scores every forecast and bet against the bookmaker's closing odds. Being right a lot of the time doesn't count here. The only test that matters is whether it beats the market.

Dashboard: [sports-prediction-theta.vercel.app](https://sports-prediction-theta.vercel.app) (password-protected)

---

## Why

Most "AI betting picks" tools are a prompt wrapped around a chatbot, with no record of how they actually perform. This project does the opposite. Every forecast is saved before the match, every bet is logged in an append-only ledger, and every strategy is compared with the price the market closed at. Failed experiments are written up too.

## How it works

```
Every morning (06:00 Saigon), a scheduled cloud agent runs daily.py:
  download results → settle open bets → rebuild Elo ratings → fetch live odds
  → check player news (ATP) → place paper bets for each strategy
        │
        ▼
  state/*.csv  (committed to the repo by the agent: the live record)
        │
        ├──► Next.js dashboard on Vercel (redeploys on every push)
        └──► Google Sheet (pulled by an Apps Script)
```

The AI agent only runs the pipeline. All the maths is plain Python, so every number can be reproduced. The agent isn't allowed to edit code.

## What's inside

- **Elo ratings.** Football Elo with home advantage and season carry-over. Tennis Elo that blends overall and surface-specific ratings. Parameters are tuned on training years only.
- **Paper wallets.** Each strategy has its own $5,000 wallet with quarter-Kelly staking and a 5% cap per bet. Bets are placed at a real bookmaker quote, not an idealised price.
- **Several strategies running side by side:**
  - `elo_v0`: the control. It bets when Elo disagrees with the market by enough.
  - `news_v1`: like `elo_v0`, but skips ATP players with injury or withdrawal news. Headlines are labelled by an LLM using a fixed prompt, and every label is logged.
  - `sharp_v1`: no model at all. It treats Pinnacle's margin-free price as the truth and bets other bookmakers when they pay more.
  - `casual_*`: reference wallets that copy a common "only bet on safe favourites" approach, to show what it actually does.
- **An experiment log** (`experiments/LOG.md`). Every idea is written up with its rule, its result and a verdict before it ships: decision trees, XGBoost, serve/return stats, calibration, timing and more. The test years are treated as a limited budget, and a counter records every time they've been looked at, which stops the model being overfitted to them.
- **Closing-line value (CLV).** A measure of whether a bet got a better price than the market's final price. It's the best early sign of real skill, long before profit stops being mostly luck.

## Results so far

Reported as they are.

**Backtest of the Elo baseline (test years 2022–2026):**

| | Matches | Elo log loss | Bookmaker log loss | Wallet |
|---|---:|---:|---:|---|
| EPL | 1,570 | 0.985 | **0.964** | $1,000 → $33 |
| ATP | 9,844 | 0.630 | **0.589** | $1,000 → $0.10 |

Lower log loss is better. Elo beats a naive baseline in both sports but loses to the bookmaker, and betting on its "edges" goes bust, mostly on longshots. That result is the reason for the experiments above.

**Live paper trading** (since 6 October 2026, as of 30 October): 190+ bets placed. The best Elo variant (`news_v1`) is down about 5%, and `sharp_v1` is being judged on CLV after 150 settled bets, using a decision rule written before any live data came in. The dashboard has the current numbers.

## Tech

Python 3.12 (pandas, NumPy, scikit-learn, XGBoost for experiments), managed with `uv` · Next.js and Tailwind dashboard on Vercel · Google Apps Script · Claude Code scheduled cloud routines

**Data:** football-data.co.uk (EPL results and odds since 2005) · Kaggle ATP dataset (since 2000, updated daily) · TennisMyLife (serve/return stats) · The Odds API (live odds and scores) · Fantasy Premier League API (squads, injuries) · Google News RSS + OpenRouter (news labels)

## Run it

```bash
uv sync
export ODDS_API_KEY=...        # the-odds-api.com, free plan is enough
export KAGGLE_API_TOKEN=...    # ATP history
export OPENROUTER_API_KEY=...  # optional, for the news labels

uv run python fetch_data.py    # download history into data/
uv run python backtest.py      # tune on train years, score test years → results/
uv run python daily.py         # the live morning job (updates state/)
uv run python tests/smoke_daily.py   # end-to-end test against a fake API, no credits used

cd dashboard && pnpm install && pnpm dev
```

## Layout

| Path | What it is |
|---|---|
| `elo.py`, `tml.py` | Rating models |
| `wallet.py`, `accounts.py` | Staking, settlement, deposits |
| `daily.py`, `snapshots.py` | Live jobs. Strategies are defined in `daily.py` |
| `strategies.py` | Probability rules shared by the experiments and the live job |
| `backtest.py`, `experiments/` | Backtests and every experiment, including the ones that failed |
| `state/` | The live, append-only record (bets, forecasts, closing prices) |
| `reports/` | Written reviews that led to strategy changes |
| `dashboard/` | Next.js dashboard |
| `docs/REFERENCE.md` | Full technical reference |

Paper money only. Nothing here is betting advice.
