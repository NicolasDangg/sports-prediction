// Elo history + form for the Ratings page (read at build time from ../state).
import fs from "node:fs";
import path from "node:path";
import Papa from "papaparse";

const STATE = path.join(process.cwd(), "..", "state");

function read<T>(file: string, numeric: string[]): T[] {
  const p = path.join(STATE, file);
  if (!fs.existsSync(p)) return [];
  const num = new Set(numeric);
  return Papa.parse<T>(fs.readFileSync(p, "utf8"), {
    header: true, skipEmptyLines: true, dynamicTyping: (f) => num.has(String(f)),
  }).data;
}

export type Entity = {
  name: string;
  elo: number;
  change10: number; // Elo change over the last 10 recorded matches
  spark: number[]; // last 20 ratings, oldest first
  form: string; // recent results, oldest first (W/D/L)
  pos?: number; played?: number; pts?: number; pts10?: number; wins10?: number;
};

/** One row per date; every entity's latest rating carried forward so lines are continuous. */
export type SeriesRow = { t: number } & Record<string, number>;

const GAP_DAYS = 150; // longer than a summer break: the team/player was absent, so break the line

function build(hist: { date: string; name: string; elo: number; kind?: string }[]) {
  const byName = new Map<string, { t: number; elo: number; match: boolean }[]>();
  for (const h of hist) {
    const t = Date.parse(h.date);
    const list = byName.get(h.name) ?? [];
    list.push({ t, elo: h.elo, match: h.kind !== "reset" });
    byName.set(h.name, list);
  }
  const dates = [...new Set(hist.map((h) => Date.parse(h.date)))].sort((a, b) => a - b);
  const last: Record<string, { t: number; elo: number }> = {};
  const cursor = new Map<string, number>();
  const rows: SeriesRow[] = dates.map((t) => {
    const row = { t } as SeriesRow;
    for (const [name, pts] of byName) {
      let i = cursor.get(name) ?? 0;
      while (i < pts.length && pts[i].t <= t) { last[name] = pts[i]; i++; }
      cursor.set(name, i);
      const prev = last[name];
      const next = pts[i];
      // carry the rating forward, except across a long absence (e.g. a season outside the league)
      const absent = prev && next && next.t - prev.t > GAP_DAYS * 86400000;
      if (prev && !absent) row[name] = Math.round(prev.elo);
    }
    return row;
  });
  return { byName, rows };
}

export function loadRatings() {
  const eplHist = read<{ date: string; team: string; elo: number; kind: string }>("epl_elo_history.csv", ["elo"]);
  const atpHist = read<{ date: string; player: string; elo: number }>("atp_elo_history.csv", ["elo"]);
  const eplForm = read<{ team: string; pos: number; played: number; pts: number; last5: string; last10: string; pts10: number }>(
    "epl_form.csv", ["pos", "played", "pts", "pts10"]);
  const atpForm = read<{ player: string; elo: number; last10: string; wins10: number }>("atp_form.csv", ["elo", "wins10"]);

  const epl = build(eplHist.map((h) => ({ date: h.date, name: h.team, elo: h.elo, kind: h.kind })));
  const atp = build(atpHist.map((h) => ({ date: h.date, name: h.player, elo: h.elo })));

  const summarise = (byName: Map<string, { t: number; elo: number; match: boolean }[]>, name: string) => {
    const pts = (byName.get(name) ?? []).filter((p) => p.match); // matches only, not season resets
    const elos = pts.map((p) => p.elo);
    const now = elos.at(-1) ?? 0;
    return { elo: now, change10: elos.length > 10 ? now - elos[elos.length - 11] : 0, spark: elos.slice(-20) };
  };

  const eplTeams: Entity[] = eplForm
    .map((f) => ({ name: f.team, ...summarise(epl.byName, f.team), form: f.last10, pos: f.pos, played: f.played, pts: f.pts, pts10: f.pts10 }))
    .sort((a, b) => b.elo - a.elo);
  const atpPlayers: Entity[] = atpForm
    .map((f) => ({ name: f.player, ...summarise(atp.byName, f.player), form: f.last10, wins10: f.wins10 }))
    .sort((a, b) => b.elo - a.elo);

  // EPL season starts, drawn as reference lines on the chart.
  const seasonStarts = [...new Set(eplHist.filter((h) => h.kind === "reset").map((h) => Date.parse(h.date)))].sort((a, b) => a - b);

  return { epl: { entities: eplTeams, rows: epl.rows, seasonStarts }, atp: { entities: atpPlayers, rows: atp.rows, seasonStarts: [] as number[] } };
}

export type RatingsData = ReturnType<typeof loadRatings>;
