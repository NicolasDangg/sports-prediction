# Sports Prediction: Reference

Elo models for **EPL football** and **ATP tennis** place **paper bets** (virtual money only) and are scored against the bookmaker. The goal for the year to Oct 2027 is a strategy that measurably beats the market. Being right a lot of the time doesn't count; it has to beat the odds.

Read this before changing anything. For changes to the betting algorithm, use the `refine-strategy` skill (`.claude/skills/refine-strategy/SKILL.md`).

---

## 1. How the system fits together

```
06:00 Saigon (23:00 UTC)  Cloud routine "Sports prediction - morning paper trading"
        │                 runs: uv run python daily.py
        ▼
   daily.py ── downloads results ── settles open bets ── rebuilds Elo ── fetches odds ── places bets
        │
        ▼
   state/*.csv  ── committed to main by the routine
        │
        ├──► Vercel redeploys dashboard/ (reads ../state at build) → https://sports-prediction-theta.vercel.app (password)
        └──► Google Sheet pulls the CSVs at 09:00 via Apps Script (sheets/sync.gs)
```

The LLM agent only orchestrates; all maths is in Python, so every number is reproducible. The routine's prompt forbids it from editing code. Code changes happen in interactive sessions.

## 2. Files

| Path | What it is |
|---|---|
| `fetch_data.py` | Downloads EPL seasons (football-data.co.uk) and ATP history (Kaggle, fallback GitHub mirror) into `data/` (gitignored) |
| `elo.py` | `FootballElo`, `TennisElo`, `expected_score`, `log_loss` |
| `wallet.py` | `Wallet`: edge test, fractional Kelly staking, settlement, summary stats |
| `backtest.py` | Replays history, tunes Elo on train years, scores the test years, writes `results/` |
| `daily.py` | The live morning job. **`STRATEGIES` dict lives here.** |
| `odds_api.py` | The Odds API client: odds (1 credit), scores (2 credits), median consensus price |
| `names.py` | Maps API names to history names ("Manchester City"→"Man City", "Jan-Lennard Struff"→"Struff J.L.") |
| `state/` | Live, committed record. **Never rewrite history here by hand.** |
| `results/` | Backtest outputs: `summary.json`, `*_bets.csv`, `*_ratings.csv` |
| `experiments/LOG.md` | Every strategy experiment, including failures, and the test-set budget |
| `reports/` | The owner's written reports that drive refinements |
| `dashboard/` | Next.js site (Vercel root dir). Password gate in `dashboard/proxy.ts` |
| `sheets/sync.gs` | Apps Script that mirrors `state/*.csv` into the Google Sheet |

## 3. Data sources

| Source | Gives | Notes |
|---|---|---|
| football-data.co.uk `mmz4281/{season}/E0.csv` | EPL results + odds, 2005/06 onward | Closing odds: Pinnacle `PSC*` until mid-2025/26, then market average `AvgC*`. Older seasons only have opening averages |
| Kaggle `dissfya/atp-tennis-2000-2023daily-pull` | ATP results + one set of odds, 2000 onward, updated daily | Needs `KAGGLE_API_TOKEN`. Fallback mirror ends April 2026. Some names have trailing spaces (stripped) |
| The Odds API (`regions=eu`, `markets=h2h`) | Live odds and scores | Free plan, 500 credits/month, about 10 per run. One sport key per ATP tournament |
| `state/atp_recent.csv` | ATP results collected live | Only rows newer than the Kaggle data are used |

## 4. The models

**Elo basics.** `expected = 1 / (1 + 10^(-(Ra - Rb)/400))`, then `R += K × (actual − expected)`. A 400-point gap is about 91%.

**EPL (`FootballElo`)**, tuned settings `k=15, home_adv=40, carryover=0.9`:
- Home side plays as if 40 points stronger.
- Goal-difference multiplier: 1 for a margin of 0–1, 1.5 for 2, (11+gd)/8 for 3 or more.
- Between seasons, ratings shrink 10% toward the mean. Promoted teams inherit the mean rating of the relegated teams.
- The Elo gap becomes H/D/A probabilities through a multinomial logistic regression fitted on the train seasons.

**ATP (`TennisElo`)**, tuned settings `k_scale=200, surface_weight=0.5`:
- Overall and per-surface ratings. The prediction uses a 50/50 blend of the two gaps.
- K = 200 / (matches + 5)^0.4, so new players move fast and veterans slowly.
- Live surface comes from the tournament name, falling back to a calendar rule (clay Apr–early Jun, grass Jun 9–Jul 15).

## 5. Betting rules

- **Market probability:** the median price across bookmakers. Implied probabilities are normalised to remove the vig.
- **Edge:** `model_p × decimal_odds − 1`. At most one bet per match per strategy, on the outcome with the best edge.
- **Stake:** `bankroll × min(¼ × Kelly, 5%)`, where Kelly = `edge / (odds − 1)`. No daily exposure cap yet (v0 once put 49% of a wallet in play in one day).
- **Thresholds:** live `elo_v0` requires +5% edge. The backtest wallet uses +3%.
- **Timing:** only bets on matches starting within 30 hours of the run. A bet with no result after 7 days is voided and the stake refunded.

## 6. Strategies and versioning

`daily.py`:
```python
STRATEGIES = {
    "elo_v0": {"prob": lambda row: row["elo_p"], "min_edge": 0.05},
}
```
- Each strategy gets one wallet per sport (`epl:<name>`, `atp:<name>`), starting at $1,000, and is created automatically on the next run.
- `prob(row)` receives a prediction row with `elo_p`, `market_p`, `odds`, `edge`, `outcome`, `sport`, `n_books`, and so on, and returns the probability the strategy believes.
- **Never edit or delete an existing strategy.** Its live record would stop meaning anything. Add `elo_v1`, `elo_v2`, and so on.
- If a new idea needs more than `prob` + `min_edge` (for example a daily cap or a different stake rule), extend the interface **backward-compatibly**: old strategies must behave exactly as before.

## 7. Evaluation rules

1. **Log loss vs. the bookmaker** is the probability score. Lower is better. Accuracy alone is meaningless.
2. **Train years** (EPL 2012/13–2021/22, ATP 2010–2019 for tuning) are for choosing settings. Do whatever you like there.
3. **Test years** (EPL 2022/23 onward, ATP 2023 onward) are a **limited budget**. Every look at them is logged in `experiments/LOG.md`. Re-checking tweak after tweak on the test years is overfitting, and it makes a lucky variant look like a real one.
4. **The live wallet is the final judge.** Its bets are placed before kickoff and can't be adjusted afterwards. Give a new strategy at least ~100 settled bets before concluding anything from its P&L. Profit is noisy; log loss and (later) closing line value settle faster.
5. A change ships only if it beats `elo_v0` on train-period validation and isn't worse on the test years. The live wallet then decides whether it stays promoted.

## 8. State file formats (`state/`)

| File | Columns / content |
|---|---|
| `ledger.csv` | `bet_id` (`event_id:strategy`), `wallet`, `sport`, `strategy`, `placed_at`, `commence_time`, `sport_key`, `event_id`, `competition`, `match`, `pick`, `model_p`, `market_p`, `odds`, `n_books`, `stake`, `status` (open/won/lost/void), `result`, `pnl`, `settled_at` |
| `wallets.json` | `{wallet: {cash}}`. Bankroll = cash + open stakes |
| `bankroll_history.csv` | One row per wallet per day: `cash`, `open_stakes`, `bankroll`, `bets_settled`, `bets_open`, `profit`, `roi` |
| `predictions.csv` | Today's priced matches, one row per outcome: `elo_p`, `market_p`, `odds`, `n_books`, `edge` |
| `epl_ratings.csv`, `atp_ratings.csv` | Current ratings (ATP: overall, hard, clay, grass) |
| `atp_recent.csv` | Live-collected ATP results in history format |

## 9. Results so far

| | Baseline | Elo | Bookmaker | Backtest wallet |
|---|---|---|---|---|
| EPL (2022/23 onward, 1,570 matches) | 1.0687 | 0.9846 | **0.9635** | −12% ROI, $1,000 → $33 |
| ATP (2023 to Sep 2026, 9,844 matches) | 0.6931 | 0.6298 | **0.5888** | −28% ROI, went bust |

- Blending Elo into the market probabilities made log loss *worse* at every weight. Everything Elo knows is already in the odds.
- v0's claimed edges are concentrated on underdogs, which shows overconfidence rather than real value.
- **So the edge has to come from information the market doesn't have yet, or from timing**, not from a better-tuned Elo.

## 10. Operations

| Thing | Where |
|---|---|
| Routine | claude.ai/code/routines/trig_01J7sKStghiTiFzGNCzMXmuX (Sonnet 5.5, no connectors, pushes `state/` to main) |
| Cloud secrets | `ODDS_API_KEY`, `KAGGLE_API_TOKEN` in the Default environment |
| Local run | `uv run --env-file .env python daily.py` (writes real state; don't run it when the routine is about to) |
| Backtest | `uv run python -W ignore backtest.py` (~40s) |
| Dashboard | `dashboard/`, password in `DASHBOARD_PASSWORD` on Vercel (production and preview); local copy in `dashboard/.env.local` |
| Sheet | "Sports Prediction - Paper Trading" in Google Drive. Apps Script `sync` runs daily at 09:00 |

## 11. Known gaps and idea backlog

- **Closing line value (CLV):** record the closing price for each bet (EPL `AvgC*` after the match; ATP from Kaggle odds) and report whether our bet beat it. Shows skill much faster than P&L.
- Daily exposure cap per wallet.
- The dashboard colours wallets by sport, so two strategies in the same sport share a colour. Give each strategy its own line style or shade when a second one ships.
- News and injury signals extracted by an LLM (v3 roadmap). Fine-tuning a small open model (v4).
- EPL bets are only placed within 30 hours of kickoff, so weekend fixtures get bet on Friday or Saturday morning only.

## 12. Glossary

- **Odds (decimal):** total return per $1 staked. 2.00 means about 50%.
- **Vig:** the bookmaker's built-in margin. Implied probabilities sum to more than 100%.
- **Log loss:** the average of −ln(probability given to what happened). It punishes confident mistakes.
- **Edge:** expected profit per $1 if our probability is right.
- **Kelly:** the stake that maximises long-run growth *if* the probabilities are correct. We use a quarter of it.
- **CLV:** did the odds move toward our pick after we bet? The best fast signal of real skill.
- **Overfitting:** fitting noise in the data you evaluate on, so the result fails on new games.
