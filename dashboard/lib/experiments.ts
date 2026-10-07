// Experiments index + live progress, from experiments/registry.json and the state files.
import { readJson, readState } from "@/lib/data";
import { loadStrategies, type WalletStats } from "@/lib/strategies";

export type Status = "planned" | "running" | "collecting" | "live" | "shipped" | "not_shipped" | "done";
export type Rule = { text: string; passed: boolean | null };
export type Metric = { model: string; log_loss?: number; accuracy?: number; roi?: number; highlight?: boolean };
export type Experiment = {
  id: string; date: string; title: string; status: Status; kind: string; sport: "atp" | "epl" | "both";
  hypothesis: string; change: string; protocol?: string; report?: string; strategy?: string;
  rules: Rule[]; metrics?: Metric[]; metrics_note?: string; verdict?: string;
  progress?: { metric: string; target: number; source: string };
  script?: string; results_file?: string; test_look: boolean; depends_on?: string[]; followups: string[];
};
type Registry = {
  test_looks_used: number; test_looks_note: string;
  benchmark: { label: string; bookmaker: number; raw_elo: number };
  experiments: Experiment[];
};

export const STATUS_LABEL: Record<Status, string> = {
  planned: "Planned", running: "Running", collecting: "Collecting data", live: "Live",
  shipped: "Shipped", not_shipped: "Not shipped", done: "Done",
};
export const TEST_BUDGET = 10; // beyond this many looks the test years are "worn out" (docs/REFERENCE.md §7)
const VETO = new Set(["injured", "ill", "withdrawn", "doubt"]);

/** Live progress toward an experiment's pre-registered sample size. */
function progressOf(e: Experiment): { value: number; target: number; label: string } | null {
  if (!e.progress) return null;
  if (e.progress.source === "news") {
    // elo_v0 ATP bets on a player news_v1 would have refused (flag present when the forecast was made).
    const flagged = new Set(
      readState<{ event_id: string; outcome: string; news_status?: string; news_confidence?: number }>("forecasts.csv")
        .filter((f) => VETO.has(String(f.news_status ?? "")) && Number(f.news_confidence ?? 0) >= 0.6)
        .map((f) => `${f.event_id}|${f.outcome}`),
    );
    const n = readState<{ wallet: string; event_id: string; pick: string }>("ledger.csv")
      .filter((b) => b.wallet === "atp:elo_v0" && flagged.has(`${b.event_id}|${b.pick}`)).length;
    return { value: n, target: e.progress.target, label: "vetoed elo_v0 bets" };
  }
  if (e.progress.source === "snapshots") {
    const snaps = readState<{ at: string; event_id: string; commence_time: string; sport: string }>("odds_snapshots.csv")
      .filter((s) => s.sport === "atp" && s.at < s.commence_time);
    const byEvent = new Map<string, { n: Set<string>; last: string; start: string }>();
    for (const s of snaps) {
      const r = byEvent.get(s.event_id) ?? { n: new Set<string>(), last: "", start: s.commence_time };
      r.n.add(s.at);
      if (s.at > r.last) r.last = s.at;
      byEvent.set(s.event_id, r);
    }
    const usable = [...byEvent.values()].filter(
      (r) => r.n.size >= 2 && (Date.parse(r.start) - Date.parse(r.last)) / 60000 <= 180).length;
    return { value: usable, target: e.progress.target, label: "matches with an early and a closing price" };
  }
  if (e.progress.source === "bets" && e.strategy) {
    const n = readState<{ strategy: string; status: string }>("ledger.csv")
      .filter((b) => b.strategy === e.strategy && (b.status === "won" || b.status === "lost")).length;
    return { value: n, target: e.progress.target, label: `settled ${e.strategy} bets` };
  }
  return null;
}

export function loadExperiments() {
  const reg = readJson<Registry>("experiments/registry.json");
  const { stats } = loadStrategies();
  const walletsOf = (strategy?: string) => (strategy ? stats.filter((s) => s.strategy === strategy) : []);
  const list = (reg?.experiments ?? []).map((raw) => ({ ...raw, rules: raw.rules ?? [], followups: raw.followups ?? [] }))
    .map((e) => ({
    ...e,
    progress_now: progressOf(e),
    wallets: walletsOf(e.strategy),
    rulesPassed: e.rules.filter((r) => r.passed === true).length,
    rulesKnown: e.rules.filter((r) => r.passed !== null).length,
  }));

  // Best forecaster on the shared benchmark (ATP validation 2020–22): highlighted rows without a different note.
  const leaderboard = list
    .filter((e) => !e.metrics_note)
    .flatMap((e) => (e.metrics ?? []).filter((m) => m.highlight && m.log_loss).map((m) => ({ id: e.id, model: m.model, log_loss: m.log_loss! })))
    .sort((a, b) => a.log_loss - b.log_loss);

  const next = list.filter((e) => e.status === "running").concat(list.filter((e) => e.status === "planned").reverse());
  const live = list.filter((e) => e.status === "live" || e.status === "collecting");
  const bestLive: WalletStats | null = [...stats]
    .filter((s) => s.settled > 0)
    .sort((a, b) => (b.roi ?? -Infinity) - (a.roi ?? -Infinity))[0] ?? null;

  return {
    list, leaderboard, next, live, bestLive, stats,
    testLooks: reg?.test_looks_used ?? 0, testLooksNote: reg?.test_looks_note ?? "",
    benchmark: reg?.benchmark ?? null,
    counts: list.reduce<Record<string, number>>((c, e) => ({ ...c, [e.status]: (c[e.status] ?? 0) + 1 }), {}),
  };
}

export type LoadedExperiment = ReturnType<typeof loadExperiments>["list"][number];

export function loadExperiment(id: string) {
  const all = loadExperiments();
  const e = all.list.find((x) => x.id.toLowerCase() === id.toLowerCase());
  return e ? { e, all } : null;
}

export const experimentIds = () =>
  (readJson<Registry>("experiments/registry.json")?.experiments ?? []).map((e) => ({ id: e.id.toLowerCase() }));
