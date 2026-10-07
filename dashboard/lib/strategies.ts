// Side-by-side numbers for every strategy wallet (sport:strategy), from the live state files.
import { loadDashboard, readState, type Bet } from "@/lib/data";
import { sportOf, strategyOf, type Sport } from "@/lib/format";

export type WalletStats = {
  wallet: string; sport: Sport; strategy: string;
  bankroll: number; deposits: number; net: number; cash: number; openStakes: number;
  placed: number; open: number; settled: number; won: number; lost: number; winRate: number | null;
  staked: number; pnl: number; roi: number | null; avgOdds: number | null; avgClaimedEdge: number | null;
  expectedWins: number; maxDrawdown: number; clv: { n: number; mean: number | null; beat: number | null };
  firstDay: string | null; days: number; curve: { x: string; y: number }[];
};

const mean = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);

export function loadStrategies() {
  const d = loadDashboard();
  const history = readState<{ date: string; wallet: string; bankroll: number; deposits: number; net: number; cash: number; open_stakes: number }>(
    "bankroll_history.csv");
  const closing = readState<{ event_id: string; outcome: string; closing_odds: number }>("closing.csv");
  const close = new Map(closing.map((c) => [`${c.event_id}|${c.outcome}`, Number(c.closing_odds)]));
  const bets: Bet[] = [...d.bets].reverse(); // oldest first
  const wallets = [...new Set([...history.map((r) => r.wallet), ...bets.map((b) => b.wallet)])];

  const stats: WalletStats[] = wallets.map((w) => {
    const rows = history.filter((r) => r.wallet === w);
    const last = rows.at(-1);
    const mine = bets.filter((b) => b.wallet === w && !b.flag);
    const settled = mine.filter((b) => b.status === "won" || b.status === "lost");
    const won = settled.filter((b) => b.status === "won").length;
    const staked = settled.reduce((s, b) => s + b.stake, 0);
    const pnl = settled.reduce((s, b) => s + b.pnl, 0);
    let peak = -Infinity, maxDd = 0;
    for (const r of rows) {
      peak = Math.max(peak, r.bankroll);
      if (peak > 0) maxDd = Math.max(maxDd, 1 - r.bankroll / peak);
    }
    const clvs = mine.map((b) => close.get(`${b.event_id}|${b.pick}`)).map((c, i) => (c ? mine[i].odds / c - 1 : null))
      .filter((x): x is number => x !== null);
    return {
      wallet: w, sport: sportOf(w), strategy: strategyOf(w),
      bankroll: last?.bankroll ?? 0, deposits: last?.deposits ?? 0, net: last?.net ?? 0,
      cash: last?.cash ?? 0, openStakes: last?.open_stakes ?? 0,
      placed: mine.length, open: mine.filter((b) => b.status === "open").length,
      settled: settled.length, won, lost: settled.length - won,
      winRate: settled.length ? won / settled.length : null,
      staked, pnl, roi: staked ? pnl / staked : null,
      avgOdds: mean(mine.map((b) => b.odds)),
      avgClaimedEdge: mean(mine.map((b) => b.model_p * b.odds - 1)),
      expectedWins: settled.reduce((s, b) => s + b.model_p, 0),
      maxDrawdown: maxDd,
      clv: { n: clvs.length, mean: mean(clvs), beat: clvs.length ? clvs.filter((x) => x > 0).length / clvs.length : null },
      firstDay: rows[0]?.date ?? null, days: rows.length,
      curve: rows.map((r) => ({ x: String(r.date), y: r.net })),
    };
  });
  const order = (s: WalletStats) => `${s.sport === "epl" ? 0 : 1}${s.strategy === "elo_v0" ? "0" : "1"}${s.strategy}`;
  stats.sort((a, b) => order(a).localeCompare(order(b)));

  // Matches where strategies in the same sport disagreed (one bet, another passed or picked the other side).
  const byEvent = new Map<string, Bet[]>();
  for (const b of bets) byEvent.set(`${b.sport}|${b.event_id}`, [...(byEvent.get(`${b.sport}|${b.event_id}`) ?? []), b]);
  const strategiesBySport = new Map<Sport, string[]>();
  for (const s of stats) strategiesBySport.set(s.sport, [...(strategiesBySport.get(s.sport) ?? []), s.strategy]);
  const disagreements = [...byEvent.values()].flatMap((bs) => {
    const sport = sportOf(bs[0].wallet);
    const all = strategiesBySport.get(sport) ?? [];
    if (all.length < 2) return [];
    const picks = new Map(bs.map((b) => [b.strategy, b]));
    const distinct = new Set(all.map((s) => picks.get(s)?.pick ?? "—"));
    return distinct.size > 1 ? [{ sport, match: bs[0].match, commence: bs[0].commence_time, picks: all.map((s) => ({ strategy: s, bet: picks.get(s) ?? null })) }] : [];
  }).reverse();

  return { stats, disagreements, latestDate: d.latestDate };
}
