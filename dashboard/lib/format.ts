export const money = (v: number, opts: { sign?: boolean; cents?: boolean } = {}) => {
  const { sign = false, cents = true } = opts;
  const prefix = v < 0 ? "−" : sign && v > 0 ? "+" : "";
  return `${prefix}$${Math.abs(v).toLocaleString("en-US", {
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })}`;
};

export const pct = (v: number, sign = false, digits = 1) =>
  `${sign && v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`;

export const when = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });

export const dayLabel = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export type Sport = "epl" | "atp";
export const sportOf = (wallet: string): Sport => (wallet.startsWith("epl") ? "epl" : "atp");
export const SPORT_LABEL: Record<Sport, string> = { epl: "Premier League", atp: "ATP Tour" };
export const SPORT_SHORT: Record<Sport, string> = { epl: "EPL", atp: "ATP" };
export const SPORT_COLOR: Record<Sport, string> = { epl: "var(--color-epl)", atp: "var(--color-atp)" };
export const strategyOf = (wallet: string) => wallet.split(":")[1] ?? wallet;

/** URL slug for a team/player page: "Man United" -> "man-united", "Sinner J." -> "sinner-j" */
export const slugify = (name: string) =>
  name.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
