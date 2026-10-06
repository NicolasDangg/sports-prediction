// Reads the Python pipeline's output (../state and ../results) at build time.
// Every morning the agent commits new state, Vercel rebuilds, and the page is fresh.
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";

const REPO_ROOT = path.join(process.cwd(), "..");
// Only these columns become numbers; everything else (dates, ids, names) stays text.
const NUMERIC = new Set([
  "cash", "open_stakes", "bankroll", "bets_settled", "bets_open", "profit", "roi", "model_p", "market_p",
  "odds", "n_books", "stake", "pnl", "elo_p", "edge", "elo", "elo_hard", "elo_clay", "elo_grass",
]);

function readCsv<T>(rel: string): T[] {
  const file = path.join(REPO_ROOT, rel);
  if (!fs.existsSync(file)) return [];
  const { data } = Papa.parse<T>(fs.readFileSync(file, "utf8"), {
    header: true,
    dynamicTyping: (field) => NUMERIC.has(String(field)),
    skipEmptyLines: true,
  });
  return data;
}

export type WalletDay = {
  date: string; wallet: string; cash: number; open_stakes: number; bankroll: number;
  bets_settled: number; bets_open: number; profit: number; roi: number;
};
export type Bet = {
  bet_id: string; wallet: string; sport: string; strategy: string; placed_at: string;
  commence_time: string; event_id: string; competition: string; match: string; pick: string; model_p: number;
  market_p: number; odds: number; stake: number; status: "open" | "won" | "lost" | "void";
  result: string | null; pnl: number; settled_at: string | null;
};
export type Prediction = {
  sport: string; competition: string; event_id: string; commence_time: string; match: string;
  outcome: string; elo_p: number; market_p: number; odds: number; n_books: number; edge: number;
};
export type BacktestBet = { date: string; bankroll: number };
export type BacktestSummary = Record<"epl" | "atp", {
  test_period: string; matches: number; baseline_label: string; params: Record<string, number>;
  log_loss: { baseline: number; elo: number; bookmaker: number };
  wallet: { bets: number; win_rate: number; roi: number; final_bankroll: number; max_drawdown: number; min_edge: number };
}>;

export type Point = { x: string; y: number };

export type Dashboard = ReturnType<typeof loadDashboard>;

export function loadDashboard() {
  const history = readCsv<WalletDay>("state/bankroll_history.csv");
  const ledger = readCsv<Bet>("state/ledger.csv");
  const predictions = readCsv<Prediction>("state/predictions.csv");
  const eplRatings = readCsv<{ team: string; elo: number }>("state/epl_ratings.csv");
  const atpRatings = readCsv<{ player: string; elo: number; elo_hard: number; elo_clay: number; elo_grass: number }>(
    "state/atp_ratings.csv",
  );

  const summaryFile = path.join(REPO_ROOT, "results/summary.json");
  const backtest: BacktestSummary | null = fs.existsSync(summaryFile)
    ? JSON.parse(fs.readFileSync(summaryFile, "utf8"))
    : null;

  // Backtest bankroll: keep the last value of each day (thousands of bets -> one point per day).
  const backtestCurve = (file: string): Point[] => {
    const byDay = new Map<string, number>();
    for (const b of readCsv<BacktestBet>(file)) byDay.set(String(b.date), b.bankroll);
    return [...byDay].map(([x, y]) => ({ x, y }));
  };

  const latestDate = history.reduce((m, r) => (String(r.date) > m ? String(r.date) : m), "");
  const latest = history.filter((r) => String(r.date) === latestDate);
  const wallets = [...new Set(history.map((r) => r.wallet))];
  const liveCurves = wallets.map((w) => ({
    wallet: w,
    points: history.filter((r) => r.wallet === w).map((r) => ({ x: String(r.date), y: r.bankroll })),
  }));

  // Group today's predictions by match (one row per outcome in the CSV).
  const matches = new Map<string, Prediction[]>();
  for (const p of predictions) {
    const list = matches.get(p.event_id) ?? [];
    list.push(p);
    matches.set(p.event_id, list);
  }
  const pickByEvent = new Map(ledger.map((b) => [b.event_id, b.pick]));
  const upcoming = [...matches.values()]
    .map((outcomes) => ({
      ...outcomes[0],
      outcomes,
      hasBet: pickByEvent.has(outcomes[0].event_id),
      pick: pickByEvent.get(outcomes[0].event_id) ?? null,
    }))
    .sort((a, b) => a.commence_time.localeCompare(b.commence_time));

  // Total bankroll across wallets, per day (hero sparkline).
  const totals = new Map<string, number>();
  for (const r of history) totals.set(String(r.date), (totals.get(String(r.date)) ?? 0) + r.bankroll);

  return {
    latestDate,
    totalCurve: [...totals].map(([x, y]) => ({ x, y })),
    bets: [...ledger].reverse(),
    latest,
    liveCurves,
    openBets: ledger.filter((b) => b.status === "open").sort((a, b) => a.commence_time.localeCompare(b.commence_time)),
    settledBets: ledger.filter((b) => b.status !== "open").reverse().slice(0, 50),
    upcoming,
    eplRatings,
    atpRatings: atpRatings.slice(0, 60),
    backtest,
    backtestCurves: {
      epl: backtestCurve("results/epl_bets.csv"),
      atp: backtestCurve("results/tennis_bets.csv"),
    },
  };
}
