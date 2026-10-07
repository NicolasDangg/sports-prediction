# Sports Prediction: Reference

Elo models for **EPL football** and **ATP tennis** place **paper bets** (virtual money only) and are scored against the bookmaker. The goal for the year to Oct 2027 is a strategy that measurably beats the market. Being right a lot of the time doesn't count; it has to beat the odds.

Read this before changing anything. For changes to the betting algorithm, use the `refine-strategy` skill (`.claude/skills/refine-strategy/SKILL.md`).

---

## 1. How the system fits together

```
06:00 Saigon (23:00 UTC)  Cloud routine "Sports prediction - morning paper trading"
        │                 runs: uv run python daily.py
        ▼
   daily.py ── downloads results ── settles open bets ── rebuilds Elo ── fetches odds (saved as snapshots)
        │          ── news check (ATP) ── places bets
        │
06:00 + 12:00 UTC  snapshot routine runs: uv run python snapshots.py  (ATP prices nearer the start, for CLV)
        │
        ▼
   state/*.csv  ── committed to main by the routine
        │
        ├──► Vercel redeploys dashboard/ (reads ../state at build) → https://sports-prediction-theta.vercel.app (password)
        └──► Google Sheet pulls the CSVs at 09:00 via Apps Script (sheets/sync.gs)
```

The LLM agent only orchestrates; all maths is in Python, so every number is reproducible. The one LLM judgment that
feeds decisions, the news label, is made by a fixed prompt in `news.py` and logged verbatim in `state/news.csv`. The routine's prompt forbids it from editing code. Code changes happen in interactive sessions.

## 2. Files

| Path | What it is |
|---|---|
| `fetch_data.py` | Downloads EPL seasons (football-data.co.uk) and ATP history (Kaggle, fallback GitHub mirror) into `data/` (gitignored) |
| `elo.py` | `FootballElo`, `TennisElo`, `expected_score`, `log_loss` |
| `wallet.py` | `Wallet`: edge test, fractional Kelly staking, settlement, summary stats |
| `backtest.py` | Replays history, tunes Elo on train years, scores the test years, writes `results/` |
| `daily.py` | The live morning job. **`STRATEGIES` dict lives here.** |
| `odds_api.py` | The Odds API client: odds (1 credit), scores (2 credits), median consensus price |
| `names.py` | Maps API names to history names ("Manchester City"→"Man City", "Bu Yunchaokete"→"Bu Y."). Tennis resolver refuses to guess: unknown / ambiguous / stale → not bettable |
| `aliases.csv` | Manual name fixes (`sport,api_name,history_name`) for anything the resolver can't match |
| `records.py` | Append-only research records: forecasts, outcomes, closing prices, CLV; history-file lookups |
| `accounts.py` | Wallet money: opening balances, deposits, refills (`list` / `deposit` / `refill`) |
| `ratings_history.py` | Elo after every match + recent form → `state/*_elo_history.csv`, `*_form.csv`, `*_matches.csv` (per-match ratings before/after + model probabilities), `name_map.csv` (bookmaker → history names). Feeds the dashboard Ratings page and the per-team/player pages `/ratings/epl/<slug>`, `/ratings/atp/<slug>` |
| `strategies.py` | Pure probability rules shared by experiments and `daily.py` (e.g. `format_calibrated`, E004) |
| `snapshots.py` | Odds snapshots over time → `state/odds_snapshots.csv`; opening / closing price per outcome; standalone run with a credit guard |
| `news.py` | News signal: Google News headlines per ATP player → LLM label (OpenRouter) → `state/news.csv` and `news_*` columns on forecasts |
| `experiments/e008_timing.py` | Timing / CLV study on our own snapshots (E008); says when there's enough data |
| `experiments/e004_format_calibration.py`, `e005_xgboost.py`, `e006_serve_stats.py` | Per-format calibration (E004), XGBoost (E005), XGBoost + Sackmann serve/return stats (E006) experiments. XGBoost is in the optional `experiments` dependency group: `uv run --group experiments ...` (macOS: `brew install libomp` once) |
| `experiments/e003_decision_tree.py` | Decision tree exploration (see experiments/LOG.md E003) → `results/e003_decision_tree.json` |
| `fpl.py` | Daily squads, player stats (goals, assists, xG, xA, xGI, minutes, FPL points/price/ownership/expected points), injuries + news, next fixtures with difficulty (Fantasy Premier League API), and head coaches (Wikidata) → `state/fpl_players.csv`, `fpl_fixtures.csv`, `coaches.csv`. Failures keep yesterday's files and never stop the betting run. Shown in the Squad section of each team page |
| `tests/smoke_daily.py` | End-to-end test of the daily job against a fake API on a temp copy (no credits, real state untouched) |
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
| TennisMyLife `stats.tennismylife.org/data/` | Same match format as Sackmann with serve/return stats, 1968–today incl. tournaments in progress; main tour, challengers, qualifying | Official CSV downloads (robots.txt allows `/data/`). Opt-in for now: `uv run python fetch_data.py tml` → `data/tml/`. Matches Sackmann on 94% of joined 2019 matches. The way to run an E006-style model live |
| Google News RSS | Recent headlines per player (`news.py`) | Free, no key. Untrusted text: only ever labelled by the LLM into a fixed set |
| OpenRouter | LLM that labels the headlines | `OPENROUTER_API_KEY`; default model `anthropic/claude-haiku-4.5` (`OPENROUTER_MODEL`) |
| tennisdata.app (owner download) | ATP Tour + Challenger + qualifying 2021–2026: results, one match-winner price per side (same as Kaggle's), first-set odds, % serve stats | Hand-downloaded into `data/retrieved_tennis_data/`, not committed; not fetched automatically (bot challenge). Its value: **challenger/qualifying odds** for backtests (I002) |
| tennisabstract.com Elo report (owner download) | Weekly ATP Elo (overall + per surface) | Saved page in `data/retrieved_tennis_data/`; benchmark for our ratings (I002). Match-data paths are disallowed by its robots.txt, so nothing else is taken |
| Jeff Sackmann `tennis_atp` (public mirror, pinned commit) | Point-level serve/return stats, 2008–2024, main tour + qualifying/challenger | Experiments only, opt-in: `uv run python fetch_data.py sackmann` → `data/sackmann/`. Original repo taken down in 2026; ends 2024, so not usable live |

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

- **Market probability (benchmark):** the median price across bookmakers. Implied probabilities are normalised to remove the vig.
- **Execution price:** bets are placed at a **real quote**, the highest actual bookmaker price that is at or below the median. The bookmaker and quote time are recorded. It's never the best price, which would flatter results. Pinnacle's price is logged when quoted.
- **Edge:** `model_p × execution_odds − 1`. At most one bet per match per strategy, on the outcome with the best edge.
- **Identity gate:** a tennis match is only bettable if both players resolve to exactly one recently active history player. Otherwise it's logged as a forecast with `eligible=False` and skipped. Results with untrusted names are not stored, so phantom players can't appear.
- **Stake:** `bankroll × min(¼ × Kelly, 5%)`, where Kelly = `edge / (odds − 1)`. No daily exposure cap yet (v0 once put 49% of a wallet in play in one day).
- **Thresholds:** live `elo_v0` requires +5% edge. The backtest wallet uses +3%.
- **Timing:** only bets on matches starting within 30 hours of the run.
- **News veto (`news_v1` only):** never back an ATP player whose news label is `injured`, `ill`, `withdrawn` or `doubt` with confidence ≥ 0.6 (`strategies.news_veto`). The opponent can still be backed on its own edge.
- **Settlement:** from The Odds API scores. If there's no API result 24h after kickoff, the job looks in the history files (football-data / Kaggle). After 14 days with no result anywhere, the bet becomes `unresolved` and the stake is refunded. Check those manually; they are not genuine voids. `result_source` records where each result came from.

## 6. Strategies and versioning

`daily.py`:
```python
STRATEGIES = {
    "elo_v0": {"prob": lambda row: row["elo_p"], "min_edge": 0.05},
    "news_v1": {"prob": lambda row: 0.0 if strategies.news_veto(row) else row["elo_p"], "min_edge": 0.05,
                "sports": ("atp",)},
}
```
- Optional `"sports"`: only those sports get a wallet and bets (default both). `news_v1` is ATP only.
- Each strategy gets one wallet per sport (`epl:<name>`, `atp:<name>`), opened with **$5,000** (or the strategy's `start_bankroll`) and created automatically on the next run. The opening amount is recorded in `deposits.csv`.
- **Money in is tracked separately from betting.** Profit = bankroll − total deposited, so a refill never looks like a win. Stakes are a percentage of the bankroll, so a bigger wallet doesn't change percentage results; it just stays above the $1 minimum stake longer.
- **Refills:** `uv run python accounts.py refill <wallet> [--to 5000] --reason "..."` tops the bankroll (cash + open bets) back up. `deposit` adds a fixed amount. When a new version ships, the owner chooses whether to refill the older wallets (see the `refine-strategy` skill).
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
| `deposits.csv` | Every money movement: `at`, `wallet`, `amount`, `kind` (open/deposit/refill), `reason` |
| `bankroll_history.csv` | One row per wallet per day: `cash`, `open_stakes`, `bankroll`, `deposits`, `net` (bankroll − deposits), `bets_settled`, `bets_open`, `profit` (settled P&L), `roi` |
| `predictions.csv` | Latest run's forecasts (dashboard snapshot, overwritten each run) |
| `forecasts.csv` | **Append-only**: every forecast on every run, passes included. `run_at`, `elo_p`, `market_p`, `odds` (execution quote), `exec_book`, `quote_at`, `median_odds`, `pinnacle_odds`, `n_books`, `edge`, `eligible`, `identity`, `resolved_as`, `surface`, `best_of`, `news_status`, `news_confidence`, `news_summary` (ATP rows in the betting window, from 2026-10-08) |
| `odds_snapshots.csv` | **Append-only**: every odds response, one row per outcome: `at`, `source` (daily/snapshot), `sport`, `sport_key`, `event_id`, `commence_time`, `outcome`, `median_odds`, `pinnacle_odds`, `best_odds`, `n_books` |
| `news.csv` | **Append-only**: every news verdict: `run_at`, `player`, `event_id`, `match`, `commence_time`, `n_headlines`, `status`, `confidence`, `summary`, `evidence` (cited headlines), `model` |
| `outcomes.csv` | Final result per event: `winner`, `source` |
| `closing.csv` | Closing prices per event outcome. EPL: football-data `pinnacle_close` / `avg_close`. ATP: `snapshot_median` (our last snapshot before the start, `minutes_before` says how close), else `kaggle_odds` (one bookmaker, unclear timing; approximate) |
| `bet_flags.csv` | Annotations on bets without touching the ledger, e.g. `identity_error` for the three 2026-10-06 bets placed against misresolved players |
| `epl_ratings.csv`, `atp_ratings.csv` | Current ratings (ATP: overall, hard, clay, grass) |
| `atp_recent.csv` | Live-collected ATP results in history format |

## 9. Results so far

| | Baseline | Elo | Bookmaker | Backtest wallet |
|---|---|---|---|---|
| EPL (2022/23 onward, 1,570 matches) | 1.0687 | 0.9846 | **0.9635** | −12% ROI, $1,000 → $33 |
| ATP (2023 to Sep 2026, 9,844 matches) | 0.6931 | 0.6298 | **0.5888** | −28% ROI, went bust |

- Blending Elo into the market probabilities made log loss *worse* at every weight. Everything Elo knows is already in the odds.
- ATP probability quality on 2020–22 (E005): raw Elo 0.6232 → calibrated per format 0.6185 → XGBoost on pre-match features 0.6146, bookmaker 0.5841. Better probabilities did **not** improve the wallet (XGBoost ROI −11.3% vs −8.0%): without new information, our disagreements with the market are mostly our errors.
- Adding Sackmann serve/return stats (E006) improved log loss to **0.6048** (65.9% accuracy), but a blend with the bookmaker gives the model ~zero weight (0.5840 vs 0.5841): **public historical stats are already priced in.** Edges must come from information or timing the market lacks.
- v0's claimed edges are concentrated on underdogs, which shows overconfidence rather than real value.
- **So the edge has to come from information the market doesn't have yet, or from timing**, not from a better-tuned Elo.

## 10. Operations

| Thing | Where |
|---|---|
| Routine | claude.ai/code/routines/trig_01J7sKStghiTiFzGNCzMXmuX (Sonnet 5.5, no connectors, pushes `state/` to main) |
| Snapshot routine | claude.ai/code/routines/trig_01BdgHUsso3mociBChjxYimR: runs `uv run python snapshots.py` at 06:00 and 12:00 UTC (13:00, 19:00 Saigon) and pushes `state/odds_snapshots.csv`. 1 credit per ATP tournament with a match in the next 8h; never spends the credits reserved for the rest of the month's daily runs (12/day) |
| Cloud secrets | `ODDS_API_KEY`, `KAGGLE_API_TOKEN`, `OPENROUTER_API_KEY` in the Default environment |
| Local run | `uv run --env-file .env python daily.py` (writes real state; don't run it when the routine is about to) |
| Smoke test | `uv run python -W ignore tests/smoke_daily.py`: run after any change to `daily.py`, `names.py`, `records.py`, `accounts.py`, `wallet.py`, `news.py`, `snapshots.py`, `strategies.py` |
| Timing study | `uv run python -W ignore experiments/e008_timing.py` (any time; reports when there's enough data) |
| Wallets | `uv run python accounts.py list` |
| Backtest | `uv run python -W ignore backtest.py` (~40s) |
| Dashboard | `dashboard/`, password in `DASHBOARD_PASSWORD` on Vercel (production and preview); local copy in `dashboard/.env.local` |
| Sheet | "Sports Prediction - Paper Trading" in Google Drive. Apps Script `sync` runs daily at 09:00 |

## 11. Known gaps and idea backlog

- **Closing line value (CLV):** ATP closing prices now come from our own snapshots (E008). Still to do: show CLV on the dashboard.
- **Run an E006-style model live** on TennisMyLife stats (needs the daily download + a new strategy experiment; E006 showed it adds nothing on top of closing odds, so only worth it if E008 finds early prices are soft).
- `best_of` is recorded per forecast but **not used by the model yet**. E004 showed a per-format calibration improves log loss (0.6243 → 0.6192 on 2017–22) but missed its pre-registered best-of-3 calibration bar and didn't help the wallet; Elo's best-of-3 overconfidence grows each year, so a recency-weighted calibration is the next variant to try.
- Daily exposure cap per wallet.
- Dashboard: strategies other than `elo_v0` are drawn dashed in their sport's colour.
- News signal v1 is a veto only. Once ~200 flagged forecasts have settled, fit a real probability adjustment per label (E007 follow-up). Fine-tuning a small open model (v4).
- EPL bets are only placed within 30 hours of kickoff, so weekend fixtures get bet on Friday or Saturday morning only.

## 12. Glossary

- **Odds (decimal):** total return per $1 staked. 2.00 means about 50%.
- **Vig:** the bookmaker's built-in margin. Implied probabilities sum to more than 100%.
- **Log loss:** the average of −ln(probability given to what happened). It punishes confident mistakes.
- **Edge:** expected profit per $1 if our probability is right.
- **Kelly:** the stake that maximises long-run growth *if* the probabilities are correct. We use a quarter of it.
- **CLV:** did the odds move toward our pick after we bet? The best fast signal of real skill.
- **Overfitting:** fitting noise in the data you evaluate on, so the result fails on new games.
