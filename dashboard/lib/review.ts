// Bet review pages: how a match we bet on played out (read at build time from ../state).
// One page per event in the ledger, open or settled; every wallet's bet on it is shown together.
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";
import { loadDashboard } from "./data";
import { playerSlugs, teamSlugs, type AtpMatch, type EplMatch } from "./entities";
import { slugify, sportOf } from "./format";

const STATE = path.join(process.cwd(), "..", "state");

function read<T>(file: string, numeric: string[]): T[] {
  const p = path.join(STATE, file);
  if (!fs.existsSync(p)) return [];
  const num = new Set(numeric);
  return Papa.parse<T>(fs.readFileSync(p, "utf8"), { header: true, skipEmptyLines: true, dynamicTyping: (f) => num.has(String(f)) }).data;
}

type Outcome = { event_id: string; home: string; away: string; winner: string; source: string; recorded_at: string };
type Closing = { event_id: string; outcome: string; closing_odds: number; source: string; minutes_before: number };
type Snapshot = { at: string; event_id: string; outcome: string; median_odds: number; pinnacle_odds: number; best_odds: number; n_books: number };

const DAY = 86_400_000;
/** Our match files are dated by the local match day; the API by UTC kickoff. Allow a little slack. */
const near = (date: string, iso: string) => Math.abs(new Date(date).getTime() - new Date(iso.slice(0, 10)).getTime()) <= 2 * DAY;

export const reviewIds = () => [...new Set(loadDashboard().bets.map((b) => b.event_id))].map((id) => ({ id }));

export function loadBetReview(id: string) {
  const bets = loadDashboard().bets.filter((b) => b.event_id === id);
  if (!bets.length) return null;
  const first = bets[0];
  const sport = sportOf(first.wallet);
  const [home, away] = first.match.split(" v ");
  const names = new Map(
    read<{ sport: string; api_name: string; name: string }>("name_map.csv", []).filter((m) => m.sport === sport).map((m) => [m.api_name, m.name]),
  );
  const homeName = names.get(home) ?? null;
  const awayName = names.get(away) ?? null;

  const outcome = read<Outcome>("outcomes.csv", []).find((o) => o.event_id === id) ?? null;

  // Score and rating moves from our own match files, written from the bettor's (home/away) side.
  let played: {
    score: string | null; detail: string | null;
    homeBefore: number; awayBefore: number; homeAfter: number; awayAfter: number; homeProb: number | null;
  } | null = null;
  if (sport === "atp" && homeName && awayName) {
    const m = read<AtpMatch>("atp_matches.csv", ["p1_before", "p2_before", "p1_after", "p2_after", "p1_prob"])
      .filter((r) => ((r.p1 === homeName && r.p2 === awayName) || (r.p1 === awayName && r.p2 === homeName)) && near(r.date, first.commence_time))
      .at(-1);
    if (m) {
      const flip = m.p1 !== homeName;
      const score = m.score ? (flip ? m.score.split(" ").map((s) => s.split("-").reverse().join("-")).join(" ") : m.score) : null;
      played = {
        score, detail: [m.tournament, m.round, m.surface].filter(Boolean).join(" · ") || null,
        homeBefore: flip ? m.p2_before : m.p1_before, awayBefore: flip ? m.p1_before : m.p2_before,
        homeAfter: flip ? m.p2_after : m.p1_after, awayAfter: flip ? m.p1_after : m.p2_after,
        homeProb: typeof m.p1_prob === "number" ? (flip ? 1 - m.p1_prob : m.p1_prob) : null,
      };
    }
  } else if (sport === "epl" && homeName && awayName) {
    const m = read<EplMatch>("epl_matches.csv", ["hg", "ag", "home_before", "away_before", "home_after", "away_after", "p_home"])
      .find((r) => r.home === homeName && r.away === awayName && near(r.date, first.commence_time));
    if (m) {
      played = {
        score: `${m.hg}–${m.ag}`, detail: "Premier League",
        homeBefore: m.home_before, awayBefore: m.away_before, homeAfter: m.home_after, awayAfter: m.away_after, homeProb: m.p_home,
      };
    }
  }

  // Closing line: what the market said just before the start, per outcome.
  const closing = new Map(read<Closing>("closing.csv", ["closing_odds", "minutes_before"]).filter((c) => c.event_id === id).map((c) => [c.outcome, c]));

  // Price history: one row per snapshot time, each outcome's median / Pinnacle / best price.
  const snaps = read<Snapshot>("odds_snapshots.csv", ["median_odds", "pinnacle_odds", "best_odds", "n_books"]).filter((s) => s.event_id === id);
  const outcomes = [...new Set([home, away, ...snaps.map((s) => s.outcome)])].filter(Boolean);
  const byTime = new Map<string, Record<string, Snapshot>>();
  for (const s of snaps) byTime.set(s.at, { ...byTime.get(s.at), [s.outcome]: s });
  const history = [...byTime].sort(([a], [b]) => a.localeCompare(b)).map(([at, row]) => ({ at, row }));

  // Link names to their ratings page only when one is built.
  const slugs = new Set((sport === "atp" ? playerSlugs() : teamSlugs()).map((s) => s.slug));
  const pageFor = (name: string | null) => (name && slugs.has(slugify(name)) ? `/ratings/${sport}/${slugify(name)}` : null);
  const hasMatchPage = read<{ event_id: string }>("atp_quotes.csv", []).some((q) => q.event_id === id);
  const term = `${home} ${away}`;

  return {
    id, sport, home, away, match: first.match, competition: first.competition, commence_time: first.commence_time,
    homeHref: pageFor(homeName), awayHref: pageFor(awayName),
    bets: bets.map((b) => {
      const close = closing.get(b.pick);
      return { ...b, closing: close?.closing_odds ?? null, clv: close ? b.odds / close.closing_odds - 1 : null };
    }),
    winner: outcome?.winner ?? (bets.find((b) => b.result)?.result || null),
    resultSource: outcome?.source ?? null,
    played, outcomes, history, hasMatchPage,
    sofascore: {
      term,
      search: `https://www.google.com/search?q=${encodeURIComponent(`site:sofascore.com ${term}`)}`,
    },
  };
}

export type BetReview = NonNullable<ReturnType<typeof loadBetReview>>;
