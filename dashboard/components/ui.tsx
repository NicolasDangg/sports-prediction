import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "@phosphor-icons/react/ssr";
import { SPORT_COLOR, SPORT_SHORT, type Sport } from "@/lib/format";

export function Card({ children, className = "", as: Tag = "section" }: {
  children: ReactNode; className?: string; as?: "section" | "div" | "article";
}) {
  return (
    <Tag className={`rounded-[1.75rem] border border-line/80 bg-surface p-6 shadow-diffuse md:p-7 ${className}`}>
      {children}
    </Tag>
  );
}

export function CardHeader({ title, hint, action }: { title: string; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
        {hint && <p className="mt-1 max-w-[62ch] text-[13px] leading-relaxed text-ink-3">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-4 md:mb-8 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">{eyebrow}</p>
        <h1 className="mt-1.5 text-[28px] font-semibold leading-none tracking-tighter text-ink md:text-[34px]">{title}</h1>
      </div>
      {children}
    </header>
  );
}

export function SportDot({ sport, size = 8 }: { sport: Sport; size?: number }) {
  return <span aria-hidden className="inline-block shrink-0 rounded-full" style={{ width: size, height: size, background: SPORT_COLOR[sport] }} />;
}

export function SportTag({ sport }: { sport: Sport }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide ${sport === "epl" ? "bg-epl-soft text-[#1c5cab]" : "bg-atp-soft text-[#a8461d]"}`}>
      <SportDot sport={sport} size={6} />
      {SPORT_SHORT[sport]}
    </span>
  );
}

/** Signed value with an arrow icon, so direction never depends on color alone. */
export function Delta({ value, children, className = "" }: { value: number; children: ReactNode; className?: string }) {
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus;
  const tone = value > 0 ? "text-up" : value < 0 ? "text-down" : "text-ink-3";
  return (
    <span className={`inline-flex items-center gap-1 font-medium tabular ${tone} ${className}`}>
      <Icon size={14} weight="bold" aria-hidden />
      {children}
    </span>
  );
}

export function EmptyState({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border border-dashed border-line bg-sunken/50 px-5 py-8">
      <span className="grid size-10 place-items-center rounded-xl bg-surface text-ink-2 shadow-sm ring-1 ring-line">{icon}</span>
      <div>
        <p className="text-sm font-semibold text-ink">{title}</p>
        <p className="mt-1 max-w-[52ch] text-[13px] leading-relaxed text-ink-3">{children}</p>
      </div>
    </div>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[12px] font-medium text-ink-3">{label}</p>
      <p className="mt-1 truncate text-xl font-semibold tracking-tight text-ink tabular">{value}</p>
      {sub && <div className="mt-0.5 text-[12px] text-ink-3">{sub}</div>}
    </div>
  );
}
