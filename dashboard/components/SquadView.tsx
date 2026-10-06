"use client";

import { useMemo, useRef, useState } from "react";
import SoccerLineUp, { type Player as PitchPlayer, type Team } from "react-soccer-lineup";
import { FirstAidKit, Warning, X } from "@phosphor-icons/react";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import type { Fixture, FplPlayer, Squad } from "@/lib/squad";

const POS_LABEL = { GKP: "Goalkeeper", DEF: "Defender", MID: "Midfielder", FWD: "Forward" } as const;
const FDR = ["", "bg-[#d7f0e3] text-[#0f5c3a]", "bg-[#e6f4ee] text-up", "bg-sunken text-ink-2", "bg-[#fbe4e4] text-down", "bg-[#f3c9c9] text-[#8e1f1f]"];

type Open = { player: FplPlayer; x: number; y: number } | null;

export default function SquadView({ squad, teamName }: { squad: Squad; teamName: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const lastPointer = useRef({ x: 0, y: 0 });
  const [open, setOpen] = useState<Open>(null);

  // The pitch component's onClick has no event, so remember where the pointer went down.
  const trackPointer = (e: React.PointerEvent) => {
    const r = wrapRef.current!.getBoundingClientRect();
    lastPointer.current = { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const openAt = (player: FplPlayer, el?: HTMLElement) => {
    if (el && wrapRef.current) {
      const r = wrapRef.current.getBoundingClientRect(), b = el.getBoundingClientRect();
      setOpen({ player, x: b.left - r.left + b.width / 2, y: b.top - r.top + b.height / 2 });
    } else {
      setOpen({ player, ...lastPointer.current });
    }
  };

  const team: Team = useMemo(() => {
    const toPitch = (p: FplPlayer | null): PitchPlayer | null =>
      p && {
        name: p.name,
        onClick: () => openAt(p),
        style: p.status === "d" ? { borderColor: "#eda100", color: "#fff7e0" } : undefined,
      };
    return {
      squad: {
        gk: toPitch(squad.xi.gk),
        df: squad.xi.df.map(toPitch),
        cm: squad.xi.mid.map(toPitch),
        fw: squad.xi.fw.map(toPitch),
      },
      style: { color: "#ffffff", borderColor: "#11141a", numberColor: "#11141a", nameColor: "#ffffff",
               nameBackgroundColor: "rgba(17,20,26,0.55)", size: "medium", nameOverflow: "ellipsis" },
    };
  }, [squad]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={wrapRef} className="relative">
      <Popover open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        <PopoverAnchor asChild>
          <span className="pointer-events-none absolute size-0" style={{ left: open?.x ?? 0, top: open?.y ?? 0 }} />
        </PopoverAnchor>
        <PopoverContent side="right" align="center" sideOffset={14} collisionPadding={16}
                        className="w-[340px] rounded-2xl border-line p-0 shadow-diffuse">
          {open && <PlayerCard p={open.player} fixtures={squad.fixtures} onClose={() => setOpen(null)} />}
        </PopoverContent>
      </Popover>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Pitch */}
        <div className="lg:col-span-7">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[13px] font-semibold text-ink">Probable XI <span className="font-normal text-ink-3">· {squad.xi.formation}</span></p>
            <p className="text-[11px] text-ink-3">Most starts among fit players · tap a player</p>
          </div>
          <div className="mx-auto max-w-[460px] overflow-hidden rounded-2xl" onPointerDownCapture={trackPointer}>
            <SoccerLineUp size="responsive" orientation="vertical" color="#4f8a64" pattern="lines" homeTeam={team} />
          </div>
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-ink-3">
            <span className="inline-block size-2.5 rounded-full border-2 border-[#eda100] bg-[#fff7e0]" aria-hidden />
            Doubtful but likely (75%+). FPL positions; a heuristic, not a confirmed team sheet.
          </p>
        </div>

        {/* Coach, injuries, bench */}
        <div className="flex flex-col gap-5 lg:col-span-5">
          {squad.coach && (
            <div className="flex items-center gap-4 rounded-2xl bg-sunken/60 p-4 ring-1 ring-line/70">
              <Avatar src={squad.coach.image} name={squad.coach.coach} size={56} rounded="xl" />
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-ink-3">Head coach</p>
                <p className="text-[16px] font-semibold text-ink">{squad.coach.coach}</p>
                {squad.coach.since && (
                  <p className="text-[12px] text-ink-3">since {new Date(squad.coach.since).toLocaleDateString("en-GB", { month: "short", year: "numeric" })}</p>
                )}
              </div>
            </div>
          )}

          <div>
            <p className="mb-2 flex items-center gap-1.5 text-[13px] font-semibold text-ink">
              <FirstAidKit size={16} className="text-down" aria-hidden /> Injured, doubtful or suspended
              <span className="font-normal text-ink-3">· {squad.unavailable.length + squad.players.filter((p) => p.status === "d" && (p.chance_next ?? 0) >= 75).length}</span>
            </p>
            <ul className="divide-y divide-line-soft">
              {[...squad.unavailable, ...squad.players.filter((p) => p.status === "d" && (p.chance_next ?? 0) >= 75)].map((p) => (
                <li key={p.id}>
                  <button onClick={(e) => openAt(p, e.currentTarget)} className="flex w-full cursor-pointer items-center gap-3 py-2 text-left transition-colors hover:bg-sunken/50">
                    <Avatar src={p.photo} name={p.name} size={36} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-medium text-ink">{p.name} <span className="font-normal text-ink-3">· {p.position}</span></span>
                      <span className="block truncate text-[12px] text-ink-3">{p.news || "No details"}</span>
                    </span>
                    <StatusChip p={p} />
                  </button>
                </li>
              ))}
              {squad.unavailable.length === 0 && <li className="py-2 text-[13px] text-ink-3">Everyone is fit.</li>}
            </ul>
          </div>

          <div>
            <p className="mb-2 text-[13px] font-semibold text-ink">Bench <span className="font-normal text-ink-3">· fit, outside the XI</span></p>
            <div className="flex flex-wrap gap-2">
              {squad.bench.map((p) => (
                <button key={p.id} onClick={(e) => openAt(p, e.currentTarget)}
                        className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full bg-surface py-1 pl-1 pr-3 text-[12px] font-medium text-ink ring-1 ring-line transition-colors hover:bg-sunken active:scale-[0.98]">
                  <Avatar src={p.photo} name={p.name} size={28} />
                  {p.name} <span className="text-ink-3">{p.position}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <SquadTable players={squad.players} onPick={openAt} />
      {squad.departed > 0 && <p className="mt-2 text-[11px] text-ink-3">{squad.departed} players who left or are out on loan are hidden. Data: Fantasy Premier League, Wikidata.</p>}
    </div>
  );
}

function PlayerCard({ p, fixtures, onClose }: { p: FplPlayer; fixtures: Fixture[]; onClose: () => void }) {
  const gk = p.position === "GKP";
  const defensive = p.position === "GKP" || p.position === "DEF";
  const diff = p.goals - p.xg;
  const stats: [string, string | number][] = [
    ["Starts · min", `${p.starts} · ${p.minutes}′`],
    ["Goals", p.goals], ["Assists", p.assists],
    ["xG", p.xg.toFixed(2)], ["xA", p.xa.toFixed(2)], ["xGI / 90", Number(p.xgi90).toFixed(2)],
    ...(defensive ? [["Clean sheets", p.clean_sheets], ["xGC / 90", Number(p.xgc90).toFixed(2)]] as [string, number | string][] : []),
    ...(gk ? [["Saves", p.saves], ["Pens saved", p.pens_saved]] as [string, number][] : []),
    ...(!gk && p.def_contrib != null ? [["Def. contributions", p.def_contrib]] as [string, number][] : []),
    ["Yellow · red", `${p.yellow} · ${p.red}`],
  ];
  const fpl: [string, string | number][] = [
    ["Price", `£${p.price.toFixed(1)}m`], ["Owned", `${p.selected_pct}%`], ["Points", p.total_points],
    ["Form", p.form], ["Exp. pts next", p.ep_next ?? "—"], ["Bonus", p.bonus],
  ];
  const setPieces = [p.penalties_order === 1 && "1st on penalties", p.corners_order === 1 && "1st on corners", p.freekicks_order === 1 && "1st on free kicks"].filter(Boolean);

  return (
    <div>
      <div className="flex items-start gap-3 border-b border-line-soft p-4">
        <Avatar src={p.photo} name={p.name} size={64} rounded="xl" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-[16px] font-semibold text-ink">{p.first_name} {p.second_name}</p>
          <p className="text-[12px] text-ink-3">{POS_LABEL[p.position]}{p.birth_date ? ` · ${age(p.birth_date)} yrs` : ""}</p>
          <div className="mt-1.5"><StatusChip p={p} /></div>
        </div>
        <button onClick={onClose} aria-label="Close" className="grid size-8 cursor-pointer place-items-center rounded-lg text-ink-3 hover:bg-sunken hover:text-ink">
          <X size={16} aria-hidden />
        </button>
      </div>
      {p.news && <p className="flex gap-1.5 border-b border-line-soft bg-[#fffaf0] px-4 py-2 text-[12px] text-[#7a5300]"><Warning size={14} className="mt-0.5 shrink-0" aria-hidden />{p.news}</p>}
      <div className="p-4">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">This season</p>
        <dl className="grid grid-cols-3 gap-x-3 gap-y-2.5">
          {stats.map(([k, v]) => (
            <div key={k}><dt className="text-[11px] text-ink-3">{k}</dt><dd className="font-mono text-[14px] font-semibold text-ink tabular">{v}</dd></div>
          ))}
        </dl>
        {!gk && p.minutes > 0 && (
          <p className={`mt-3 text-[12px] ${Math.abs(diff) < 0.5 ? "text-ink-3" : diff > 0 ? "text-up" : "text-down"}`}>
            {Math.abs(diff) < 0.5 ? "Scoring in line with chances (goals ≈ xG)" : diff > 0 ? `Scoring ${diff.toFixed(1)} above chances: may cool off` : `Scoring ${Math.abs(diff).toFixed(1)} below chances: due goals?`}
          </p>
        )}
        <p className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">FPL</p>
        <dl className="grid grid-cols-3 gap-x-3 gap-y-2.5">
          {fpl.map(([k, v]) => (
            <div key={k}><dt className="text-[11px] text-ink-3">{k}</dt><dd className="font-mono text-[14px] font-semibold text-ink tabular">{v}</dd></div>
          ))}
        </dl>
        {setPieces.length > 0 && <p className="mt-3 text-[12px] text-ink-2">{setPieces.join(" · ")}</p>}
        {fixtures.length > 0 && (
          <>
            <p className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">Next fixtures (difficulty)</p>
            <div className="flex gap-1.5">
              {fixtures.slice(0, 5).map((f) => (
                <span key={f.gw + f.opponent} title={`GW${f.gw} · difficulty ${f.difficulty}/5`}
                      className={`flex-1 rounded-lg px-1 py-1.5 text-center text-[11px] font-semibold ${FDR[f.difficulty] ?? ""}`}>
                  {short(f.opponent)}<span className="block text-[10px] font-medium opacity-80">{isHome(f) ? "H" : "A"}</span>
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

type SortKey = "xgi" | "goals" | "assists" | "xg" | "xa" | "minutes" | "total_points" | "price" | "ep_next";

function SquadTable({ players, onPick }: { players: FplPlayer[]; onPick: (p: FplPlayer, el?: HTMLElement) => void }) {
  const [sort, setSort] = useState<SortKey>("xgi");
  const rows = [...players].sort((a, b) => Number(b[sort] ?? 0) - Number(a[sort] ?? 0));
  const cols: [SortKey, string][] = [["minutes", "Min"], ["goals", "G"], ["assists", "A"], ["xg", "xG"], ["xa", "xA"], ["xgi", "xGI"],
    ["total_points", "Pts"], ["ep_next", "xPts"], ["price", "£"]];
  return (
    <div className="mt-6 overflow-x-auto rounded-2xl ring-1 ring-line/80">
      <table className="w-full min-w-[720px] text-[13px]">
        <thead>
          <tr className="border-b border-line text-left text-[12px] text-ink-3">
            <th className="py-2.5 pl-4 pr-3 font-medium">Player</th>
            {cols.map(([k, label]) => (
              <th key={k} className="px-2 py-2.5 text-right font-medium" aria-sort={sort === k ? "descending" : "none"}>
                <button onClick={() => setSort(k)} className={`cursor-pointer rounded px-1 hover:text-ink ${sort === k ? "font-semibold text-ink" : ""}`}>{label}{sort === k ? " ↓" : ""}</button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} className="border-b border-line-soft last:border-0 hover:bg-sunken/50">
              <td className="py-2 pl-4 pr-3">
                <button onClick={(e) => onPick(p, e.currentTarget)} className="flex cursor-pointer items-center gap-2.5 text-left">
                  <Avatar src={p.photo} name={p.name} size={28} />
                  <span className="font-medium text-ink underline-offset-4 hover:underline">{p.name}</span>
                  <span className="text-[11px] text-ink-3">{p.position}</span>
                  {p.status !== "a" && <StatusChip p={p} compact />}
                </button>
              </td>
              {cols.map(([k]) => (
                <td key={k} className={`px-2 py-2 text-right font-mono tabular ${sort === k ? "text-ink" : "text-ink-2"}`}>
                  {k === "price" ? p.price.toFixed(1) : ["xg", "xa", "xgi"].includes(k) ? Number(p[k]).toFixed(2) : p[k] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusChip({ p, compact = false }: { p: FplPlayer; compact?: boolean }) {
  const map = {
    a: ["Available", "bg-up-soft text-up"], d: [`${p.chance_next ?? "?"}% to play`, "bg-[#fff4dc] text-[#8a5a00]"],
    i: ["Injured", "bg-down-soft text-down"], s: ["Suspended", "bg-down-soft text-down"], u: ["Unavailable", "bg-sunken text-ink-3"],
    n: ["Not in squad", "bg-sunken text-ink-3"],
  } as const;
  const [label, cls] = map[p.status] ?? map.u;
  return <span className={`inline-flex shrink-0 items-center rounded-full font-semibold ${compact ? "px-1.5 py-0 text-[10px]" : "px-2 py-0.5 text-[11px]"} ${cls}`}>{label}</span>;
}

/** Photo with an initials fallback (new signings sometimes have no photo yet). */
function Avatar({ src, name, size, rounded = "full" }: { src: string; name: string; size: number; rounded?: "full" | "xl" }) {
  const [failed, setFailed] = useState(!src);
  const initials = name.split(/[\s.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return failed ? (
    <span className={`grid shrink-0 place-items-center bg-sunken font-semibold text-ink-3 ring-1 ring-line ${rounded === "full" ? "rounded-full" : "rounded-xl"}`}
          style={{ width: size, height: size, fontSize: size * 0.34 }}>{initials}</span>
  ) : (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" width={size} height={size} loading="lazy" onError={() => setFailed(true)}
         className={`shrink-0 bg-sunken object-cover object-top ring-1 ring-line ${rounded === "full" ? "rounded-full" : "rounded-xl"}`}
         style={{ width: size, height: size }} />
  );
}

const isHome = (f: Fixture) => String(f.home).toLowerCase() === "true";
const short = (t: string) => ({ "Man United": "MUN", "Man City": "MCI", "Nott'm Forest": "NFO", "Crystal Palace": "CRY", "Aston Villa": "AVL", Tottenham: "TOT", Newcastle: "NEW", Bournemouth: "BOU", Brentford: "BRE", Brighton: "BHA", Sunderland: "SUN", Liverpool: "LIV", Arsenal: "ARS", Chelsea: "CHE", Everton: "EVE", Fulham: "FUL", Leeds: "LEE", Ipswich: "IPS", Coventry: "COV", Hull: "HUL" } as Record<string, string>)[t] ?? t.slice(0, 3).toUpperCase();
const age = (d: string) => Math.floor((Date.now() - Date.parse(d)) / (365.25 * 86400000));
