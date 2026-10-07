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

/** Line pattern per strategy (wallets in one sport share a colour): the control is solid. */
const DASHES: Record<string, string | undefined> = {
  elo_v0: undefined, news_v1: "7 5", sharp_v1: "1 5", casual_big_v1: "14 5", casual_many_v1: "10 4 1 4",
};
export const strategyDash = (strategy: string) =>
  strategy in DASHES ? DASHES[strategy] : "12 4 2 4";

/** One line on what each live strategy does, in plain words. */
export const STRATEGY_BLURB: Record<string, string> = {
  elo_v0: "Elo model vs the typical bookmaker price. The control.",
  news_v1: "elo_v0, but never backs a player with injury or illness news.",
  sharp_v1: "No model: Pinnacle's fair price vs the best bookmaker price.",
  casual_big_v1: "Once a week, 25% of the wallet on the single likeliest winner.",
  casual_many_v1: "Once a week, 25% of the wallet split over every 80%+ favourite.",
};

/** URL slug for a team/player page: "Man United" -> "man-united", "Sinner J." -> "sinner-j" */
export const slugify = (name: string) =>
  name.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f']/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
