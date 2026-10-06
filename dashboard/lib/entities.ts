// Per-team / per-player detail data (read at build time from ../state).
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";
import { loadDashboard, type Bet } from "./data";
import { loadRatings } from "./ratings";

const STATE = path.join(process.cwd(), "..", "state");

function read<T>(file: string, numeric: string[]): T[] {
  const p = path.join(STATE, file);
  if (!fs.existsSync(p)) return [];
  const num = new Set(numeric);
  return Papa.parse<T>(fs.readFileSync(p, "utf8"), { header: true, skipEmptyLines: true, dynamicTyping: (f) => num.has(String(f)) }).data;
}

import { slugify } from "./format";
export { slugify };

export type EplMatch = {
  season: string; date: string; home: string; away: string; hg: number; ag: number; result: "H" | "D" | "A";
  home_before: number; away_before: number; home_after: number; away_after: number; p_home: number; p_draw: number; p_away: number;
};
export type AtpMatch = {
  date: string; tournament: string; series: string; round: string; surface: string; p1: string; p2: string; winner: string;
  score: string; p1_before: number; p2_before: number; p1_after: number; p2_after: number; p1_prob: number; odd_1: number; odd_2: number;
};

/** One match from a single team's/player's point of view. */
export type Row = {
  date: string; opponent: string; opponentSlug: string | null; venue: string; detail: string; score: string;
  result: "W" | "D" | "L"; modelWin: number; modelDraw?: number; marketWin?: number;
  eloBefore: number; eloAfter: number; upset: boolean;
};

const eplMatches = () => read<EplMatch>("epl_matches.csv", ["hg", "ag", "home_before", "away_before", "home_after", "away_after", "p_home", "p_draw", "p_away"]);
const atpMatches = () => read<AtpMatch>("atp_matches.csv", ["p1_before", "p2_before", "p1_after", "p2_after", "p1_prob", "odd_1", "odd_2"]);
const nameMap = () => read<{ sport: string; api_name: string; name: string }>("name_map.csv", []);

export function teamSlugs() {
  return loadRatings().epl.entities.map((e) => ({ slug: slugify(e.name) }));
}
/** Scores are written from Player 1's side; show them from the other player's side when needed. */
const flipScore = (score: string) => score.split(" ").map((set) => set.split("-").reverse().join("-")).join(" ");

export function playerSlugs() {
  return loadRatings().atp.entities.map((e) => ({ slug: slugify(e.name) }));
}

function linkedBets(sport: "epl" | "atp", name: string) {
  const map = nameMap().filter((m) => m.sport === sport && m.name === name).map((m) => m.api_name);
  const d = loadDashboard();
  const bets: Bet[] = d.bets.filter((b) => b.sport === sport && b.match.split(" v ").some((n) => map.includes(n)));
  const upcoming = d.upcoming.filter((u) => u.sport === sport && u.match.split(" v ").some((n) => map.includes(n)));
  return { apiNames: map, bets, upcoming };
}

export function loadTeam(slug: string) {
  const ratings = loadRatings().epl;
  const index = ratings.entities.findIndex((e) => slugify(e.name) === slug);
  if (index < 0) return null;
  const entity = ratings.entities[index];
  const name = entity.name;
  const teamSlugSet = new Set(ratings.entities.map((e) => slugify(e.name)));

  const rows: (Row & { season: string; home: boolean })[] = eplMatches()
    .filter((m) => m.home === name || m.away === name)
    .map((m) => {
      const home = m.home === name;
      const opp = home ? m.away : m.home;
      const won = (home && m.result === "H") || (!home && m.result === "A");
      const result = m.result === "D" ? "D" : won ? "W" : "L";
      const modelWin = home ? m.p_home : m.p_away;
      const modelLoss = home ? m.p_away : m.p_home;
      const pOfResult = result === "W" ? modelWin : result === "D" ? m.p_draw : modelLoss;
      return {
        season: m.season, home, date: m.date, opponent: opp, opponentSlug: teamSlugSet.has(slugify(opp)) ? slugify(opp) : null,
        venue: home ? "H" : "A", detail: `${m.season.slice(0, 2)}/${m.season.slice(2)}`,
        score: home ? `${m.hg}–${m.ag}` : `${m.ag}–${m.hg}`, result, modelWin, modelDraw: m.p_draw,
        eloBefore: home ? m.home_before : m.away_before, eloAfter: home ? m.home_after : m.away_after,
        upset: pOfResult < 0.25,
      };
    });

  const current = rows.filter((r) => r.season === rows.at(-1)?.season);
  const record = (rs: typeof rows) => ({
    p: rs.length, w: rs.filter((r) => r.result === "W").length, d: rs.filter((r) => r.result === "D").length,
    l: rs.filter((r) => r.result === "L").length,
    gf: rs.reduce((s, r) => s + Number(r.score.split("–")[0]), 0), ga: rs.reduce((s, r) => s + Number(r.score.split("–")[1]), 0),
    expectedWins: rs.reduce((s, r) => s + r.modelWin, 0),
  });

  return {
    name, entity, eloRank: index + 1, total: ratings.entities.length,
    history: ratings.rows.filter((r) => name in r).map((r) => ({ t: r.t, elo: r[name] })),
    seasonStarts: ratings.seasonStarts,
    season: { all: record(current), home: record(current.filter((r) => r.home)), away: record(current.filter((r) => !r.home)) },
    sinceStart: { all: record(rows), home: record(rows.filter((r) => r.home)), away: record(rows.filter((r) => !r.home)) },
    rows: [...rows].reverse(),
    ...linkedBets("epl", name),
  };
}

export function loadPlayer(slug: string) {
  const ratings = loadRatings().atp;
  const index = ratings.entities.findIndex((e) => slugify(e.name) === slug);
  if (index < 0) return null;
  const entity = ratings.entities[index];
  const name = entity.name;
  const playerSlugSet = new Set(ratings.entities.map((e) => slugify(e.name)));
  const surfaces = loadDashboard().atpRatings.find((r) => r.player === name);

  const rows: (Row & { surface: string; tournament: string })[] = atpMatches()
    .filter((m) => m.p1 === name || m.p2 === name)
    .map((m) => {
      const first = m.p1 === name;
      const opp = first ? m.p2 : m.p1;
      const modelWin = first ? m.p1_prob : 1 - m.p1_prob;
      const o = first ? [m.odd_1, m.odd_2] : [m.odd_2, m.odd_1];
      const marketWin = o[0] > 1 && o[1] > 1 ? (1 / o[0]) / (1 / o[0] + 1 / o[1]) : undefined;
      const result = m.winner === name ? "W" : "L";
      return {
        surface: m.surface, tournament: m.tournament, date: m.date, opponent: opp,
        opponentSlug: playerSlugSet.has(slugify(opp)) ? slugify(opp) : null, venue: m.surface,
        detail: `${m.tournament} · ${m.round}`, score: first ? String(m.score ?? "") : flipScore(String(m.score ?? "")), result, modelWin, marketWin,
        eloBefore: first ? m.p1_before : m.p2_before, eloAfter: first ? m.p1_after : m.p2_after,
        upset: (result === "W" ? modelWin : 1 - modelWin) < 0.3,
      };
    });

  const record = (rs: typeof rows) => ({
    p: rs.length, w: rs.filter((r) => r.result === "W").length, l: rs.filter((r) => r.result === "L").length,
    expectedWins: rs.reduce((s, r) => s + r.modelWin, 0),
    marketWins: rs.filter((r) => r.marketWin !== undefined).reduce((s, r) => s + (r.marketWin ?? 0), 0),
    withOdds: rs.filter((r) => r.marketWin !== undefined).length,
    winsWithOdds: rs.filter((r) => r.marketWin !== undefined && r.result === "W").length,
  });
  const bySurface = ["Hard", "Clay", "Grass"].map((s) => ({ surface: s, ...record(rows.filter((r) => r.surface === s)) }));

  return {
    name, entity, eloRank: index + 1, total: ratings.entities.length,
    surfaces: surfaces ? { hard: surfaces.elo_hard, clay: surfaces.elo_clay, grass: surfaces.elo_grass } : null,
    history: ratings.rows.filter((r) => name in r).map((r) => ({ t: r.t, elo: r[name] })),
    all: record(rows), bySurface, rows: [...rows].reverse(),
    ...linkedBets("atp", name),
  };
}
