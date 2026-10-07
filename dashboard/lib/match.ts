// ATP match pages + the search index (read at build time from ../state).
// A match is anything in atp_quotes.csv: every book's price for today's priced ATP matches.
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";
import { loadDashboard } from "./data";
import type { AtpMatch } from "./entities";
import { slugify } from "./format";

const STATE = path.join(process.cwd(), "..", "state");

function read<T>(file: string, numeric: string[]): T[] {
  const p = path.join(STATE, file);
  if (!fs.existsSync(p)) return [];
  const num = new Set(numeric);
  return Papa.parse<T>(fs.readFileSync(p, "utf8"), { header: true, skipEmptyLines: true, dynamicTyping: (f) => num.has(String(f)) }).data;
}

type Quote = {
  event_id: string; sport_key: string; competition: string; surface: string; commence_time: string;
  home: string; away: string; outcome: string; book: string; price: number; at: string;
};

/** Same blend as the live model (daily.py ATP_PARAMS): half overall Elo, half surface Elo. */
const SURFACE_WEIGHT = 0.5;
const expected = (diff: number) => 1 / (1 + 10 ** (-diff / 400));

const BOOK_LABEL: Record<string, string> = {
  pinnacle: "Pinnacle", onexbet: "1xBet", betonlineag: "BetOnline", betsson: "Betsson", coolbet: "Coolbet",
  gtbets: "GTbets", leovegas_se: "LeoVegas", nordicbet: "NordicBet", pmu_fr: "PMU", sport888: "888sport",
  unibet_fr: "Unibet FR", unibet_nl: "Unibet NL", unibet_se: "Unibet SE", unibet_eu: "Unibet", marathonbet: "Marathonbet",
  williamhill: "William Hill", betfair_ex_eu: "Betfair Exchange", matchbook: "Matchbook", tipico_de: "Tipico",
};
const bookLabel = (key: string) => BOOK_LABEL[key] ?? key;
/** Books we single out on the board. */
export const FEATURED_BOOKS = new Set(["pinnacle", "onexbet"]);

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};

/** Players with a page (same list as the Ratings page), strongest first. */
const ratedPlayers = () =>
  read<{ player: string; elo: number }>("atp_form.csv", ["elo"]).sort((x, y) => y.elo - x.elo);

const quotes = () => read<Quote>("atp_quotes.csv", ["price"]);
const atpMatches = () => read<AtpMatch>("atp_matches.csv", ["p1_before", "p2_before", "p1_after", "p2_after", "p1_prob", "odd_1", "odd_2"]);
const nameMap = () =>
  new Map(read<{ sport: string; api_name: string; name: string }>("name_map.csv", []).filter((m) => m.sport === "atp").map((m) => [m.api_name, m.name]));

/** Latest overall + per-surface Elo: atp_ratings.csv (top 200, as the live model has them),
 *  else the player's last rating in our match file (overall only). */
function latestElo(all: AtpMatch[]) {
  const out = new Map<string, { elo: number; surface: Record<string, number> | null }>();
  for (const m of all) {
    out.set(m.p1, { elo: m.p1_after, surface: null });
    out.set(m.p2, { elo: m.p2_after, surface: null });
  }
  for (const r of read<{ player: string; elo: number; elo_hard: number; elo_clay: number; elo_grass: number }>(
    "atp_ratings.csv", ["elo", "elo_hard", "elo_clay", "elo_grass"])) {
    out.set(r.player, { elo: r.elo, surface: { Hard: r.elo_hard, Clay: r.elo_clay, Grass: r.elo_grass } });
  }
  return out;
}

/** One summary per event, soonest first. */
export function loadAtpMatchList() {
  const byEvent = new Map<string, Quote>();
  for (const q of quotes()) if (!byEvent.has(q.event_id)) byEvent.set(q.event_id, q);
  return [...byEvent.values()]
    .map((q) => ({ id: q.event_id, home: q.home, away: q.away, competition: q.competition, surface: q.surface, commence_time: q.commence_time }))
    .sort((a, b) => a.commence_time.localeCompare(b.commence_time));
}

export const atpMatchIds = () => loadAtpMatchList().map((m) => ({ id: m.id }));

export function loadAtpMatch(id: string) {
  const qs = quotes().filter((q) => q.event_id === id);
  if (!qs.length) return null;
  const { home, away, competition, surface, commence_time, sport_key } = qs[0];
  const names = nameMap();
  const all = atpMatches();
  const elo = latestElo(all);
  const playerSlugs = new Set(ratedPlayers().map((p) => slugify(p.player)));
  const prediction = loadDashboard().upcoming.find((u) => u.event_id === id) ?? null;

  const side = (api: string) => {
    const name = names.get(api) ?? null;
    const r = name ? elo.get(name) : undefined;
    return {
      api, name, slug: name && playerSlugs.has(slugify(name)) ? slugify(name) : null,
      elo: r?.elo ?? null, surfaceElo: r?.surface?.[surface] ?? null,
    };
  };
  const a = side(home);
  const b = side(away);

  // Model: the morning's forecast when there is one; otherwise the same formula on the latest ratings.
  let modelHome: number | null = null;
  let modelSource: "forecast" | "ratings" | null = null;
  const fromForecast = prediction?.outcomes.find((o) => o.outcome === home)?.elo_p;
  if (typeof fromForecast === "number" && !Number.isNaN(fromForecast)) {
    modelHome = fromForecast;
    modelSource = "forecast";
  } else if (a.elo !== null && b.elo !== null && a.surfaceElo !== null && b.surfaceElo !== null) {
    modelHome = expected((1 - SURFACE_WEIGHT) * (a.elo - b.elo) + SURFACE_WEIGHT * (a.surfaceElo - b.surfaceElo));
    modelSource = "ratings";
  }

  // E009 forecaster (ATP only): shown next to Elo, never bet on.
  const fc = prediction?.outcomes.find((o) => o.outcome === home)?.forecast_p;
  const forecastHome = typeof fc === "number" && !Number.isNaN(fc) ? fc : null;

  // The board: one row per book, both prices side by side.
  const books = new Map<string, { book: string; label: string; home?: number; away?: number; at: string }>();
  for (const q of qs) {
    const row = books.get(q.book) ?? { book: q.book, label: bookLabel(q.book), at: q.at };
    if (q.outcome === home) row.home = q.price;
    if (q.outcome === away) row.away = q.price;
    if (q.at > row.at) row.at = q.at;
    books.set(q.book, row);
  }
  const board = [...books.values()]
    .filter((r): r is typeof r & { home: number; away: number } => r.home !== undefined && r.away !== undefined)
    .map((r) => ({ ...r, margin: 1 / r.home + 1 / r.away - 1 }))
    .sort((x, y) => Number(FEATURED_BOOKS.has(y.book)) - Number(FEATURED_BOOKS.has(x.book)) || x.margin - y.margin);
  const medHome = median(board.map((r) => r.home));
  const medAway = median(board.map((r) => r.away));
  const marketHome = (1 / medHome) / (1 / medHome + 1 / medAway); // margin removed
  const bestHome = Math.max(...board.map((r) => r.home));
  const bestAway = Math.max(...board.map((r) => r.away));
  const pinnacle = board.find((r) => r.book === "pinnacle") ?? null;
  const onexbet = board.find((r) => r.book === "onexbet") ?? null;
  const pricedAt = board.reduce((m, r) => (r.at > m ? r.at : m), "");

  // History between the two, and each player's recent run, from our own match file.
  const h2h = a.name && b.name
    ? all.filter((m) => (m.p1 === a.name && m.p2 === b.name) || (m.p1 === b.name && m.p2 === a.name)).reverse()
    : [];
  const recent = (name: string | null) => {
    if (!name) return null;
    const rows = all.filter((m) => m.p1 === name || m.p2 === name);
    const last10 = rows.slice(-10).reverse().map((m) => ({
      date: m.date, opponent: m.p1 === name ? m.p2 : m.p1, result: m.winner === name ? ("W" as const) : ("L" as const),
      tournament: m.tournament, round: m.round, surface: m.surface,
    }));
    const onSurface = rows.filter((m) => m.surface === surface);
    return {
      last10, wins10: last10.filter((r) => r.result === "W").length,
      surfaceW: onSurface.filter((m) => m.winner === name).length, surfaceP: onSurface.length,
    };
  };

  const widget = read<{ sport_key: string; widget_src: string }>("sofascore.csv", [])
    .find((w) => w.sport_key === sport_key && /^https:\/\/widgets\.sofascore\.com\//.test(w.widget_src))?.widget_src ?? null;

  return {
    id, home: a, away: b, competition, surface, commence_time, sport_key,
    model: modelHome === null ? null : { home: modelHome, away: 1 - modelHome, source: modelSource },
    forecast: forecastHome,
    ratingNote: prediction?.rating_note || null, // a player's rating is too old to bet on
    market: { home: marketHome, away: 1 - marketHome, medianHome: medHome, medianAway: medAway },
    best: { home: bestHome, away: bestAway },
    pinnacle, onexbet, board, pricedAt,
    h2h: h2h.map((m) => ({ date: m.date, tournament: m.tournament, round: m.round, surface: m.surface, winner: m.winner, score: m.score, p1: m.p1 })),
    form: { home: recent(a.name), away: recent(b.name) },
    bet: loadDashboard().bets.find((x) => x.event_id === id) ?? null,
    sofascore: {
      widget,
      search: `https://www.google.com/search?q=${encodeURIComponent(`site:sofascore.com ${home} ${away}`)}`,
    },
  };
}

export type AtpMatchDetail = NonNullable<ReturnType<typeof loadAtpMatch>>;

/** What the search box can find: today's ATP matches and every rated player. Small enough to ship whole. */
export type SearchItem = { kind: "match" | "player"; label: string; sub: string; href: string; terms: string; when?: string };

export function loadSearchIndex(): SearchItem[] {
  const names = nameMap();
  const matches: SearchItem[] = loadAtpMatchList().map((m) => ({
    kind: "match", label: `${m.home} v ${m.away}`, sub: `${m.competition} · ${m.surface}`, href: `/match/${m.id}`, when: m.commence_time,
    terms: [m.home, m.away, names.get(m.home), names.get(m.away), m.competition].filter(Boolean).join(" "),
  }));
  const players: SearchItem[] = ratedPlayers().map((p, i) => ({
    kind: "player", label: p.player, sub: `Elo ${Math.round(p.elo)} · #${i + 1}`, href: `/ratings/atp/${slugify(p.player)}`,
    terms: [p.player, ...[...names].filter(([, n]) => n === p.player).map(([api]) => api)].join(" "),
  }));
  return [...matches, ...players];
}
