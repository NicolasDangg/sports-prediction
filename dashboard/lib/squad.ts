// Squad, player stats, injuries, fixtures and coach for an EPL team page (from ../state, built daily by fpl.py).
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";

const STATE = path.join(process.cwd(), "..", "state");

export type FplPlayer = {
  id: number; team: string; name: string; first_name: string; second_name: string; position: "GKP" | "DEF" | "MID" | "FWD";
  photo: string; status: "a" | "d" | "i" | "s" | "u" | "n"; chance_next: number | null; news: string; price: number;
  selected_pct: number; form: number; total_points: number; ppg: number; ep_next: number | null; minutes: number; starts: number;
  goals: number; assists: number; xg: number; xa: number; xgi: number; xgc: number; xg90: number; xa90: number; xgi90: number;
  xgc90: number; clean_sheets: number; goals_conceded: number; saves: number; pens_saved: number; yellow: number; red: number;
  bonus: number; bps: number; ict: number; def_contrib: number | null; tackles: number | null; recoveries: number | null;
  penalties_order: number | null; corners_order: number | null; freekicks_order: number | null; birth_date: string;
};
export type Fixture = { team: string; gw: number; opponent: string; home: boolean | string; difficulty: number; kickoff: string };
export type Coach = { team: string; coach: string; since: string; image: string };

function read<T>(file: string, text: string[] = []): T[] {
  const p = path.join(STATE, file);
  if (!fs.existsSync(p)) return [];
  const asText = new Set(text);
  return Papa.parse<T>(fs.readFileSync(p, "utf8"), {
    header: true, skipEmptyLines: true, dynamicTyping: (f) => !asText.has(String(f)),
  }).data;
}

const fit = (p: FplPlayer) => p.status === "a" || (p.status === "d" && (p.chance_next ?? 0) >= 75);
const LIMITS = { DEF: [3, 5], MID: [2, 5], FWD: [1, 3] } as const;

/** Probable XI: fit players, ranked by starts then minutes, filling a legal formation
 *  (1 GK, 3–5 DEF, 2–5 MID, 1–3 FWD). A heuristic, not a confirmed team sheet. */
function probableXI(players: FplPlayer[]) {
  const rank = (a: FplPlayer, b: FplPlayer) => b.starts - a.starts || b.minutes - a.minutes || b.total_points - a.total_points;
  const pool = players.filter(fit).sort(rank);
  const gk = pool.find((p) => p.position === "GKP") ?? null;
  const outfield = pool.filter((p) => p.position !== "GKP");
  const pick: FplPlayer[] = [];
  const count = (pos: keyof typeof LIMITS) => pick.filter((p) => p.position === pos).length;
  // reserve the minimum for each position first, then fill by rank up to the maximums
  for (const pos of ["DEF", "MID", "FWD"] as const) {
    for (const p of outfield.filter((x) => x.position === pos).slice(0, LIMITS[pos][0])) pick.push(p);
  }
  for (const p of outfield) {
    if (pick.length >= 10) break;
    const pos = p.position as keyof typeof LIMITS;
    if (!pick.includes(p) && count(pos) < LIMITS[pos][1]) pick.push(p);
  }
  const byPos = (pos: string) => pick.filter((p) => p.position === pos).sort(rank);
  return { gk, df: byPos("DEF"), mid: byPos("MID"), fw: byPos("FWD"),
           formation: `${byPos("DEF").length}-${byPos("MID").length}-${byPos("FWD").length}` };
}

export function loadSquad(team: string) {
  const all = read<FplPlayer>("fpl_players.csv", ["name", "first_name", "second_name", "photo", "status", "news", "news_added", "birth_date", "team", "position"])
    .filter((p) => p.team === team);
  if (!all.length) return null;
  const squad = all.filter((p) => p.status !== "u"); // "u" = left the club / loaned out
  const xi = probableXI(squad);
  const inXI = new Set([xi.gk, ...xi.df, ...xi.mid, ...xi.fw].filter(Boolean).map((p) => p!.id));
  const order = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };
  return {
    players: squad,
    xi,
    bench: squad.filter((p) => !inXI.has(p.id) && fit(p)).sort((a, b) => order[a.position] - order[b.position] || b.minutes - a.minutes),
    unavailable: squad.filter((p) => !fit(p)).sort((a, b) => (a.chance_next ?? 0) - (b.chance_next ?? 0) || b.minutes - a.minutes),
    departed: all.filter((p) => p.status === "u").length,
    coach: read<Coach>("coaches.csv", ["team", "coach", "since", "image"]).find((c) => c.team === team) ?? null,
    fixtures: read<Fixture>("fpl_fixtures.csv", ["team", "opponent", "kickoff"]).filter((f) => f.team === team),
  };
}

export type Squad = NonNullable<ReturnType<typeof loadSquad>>;
