"use client";

import Link from "next/link";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Flask, House, MagnifyingGlass, Ranking, Receipt, Scales, SignOut, Target, TestTube, X } from "@phosphor-icons/react";
import type { SearchItem } from "@/lib/match";
import AgentStatus from "./AgentStatus";
import SearchBox from "./SearchBox";

const ITEMS = [
  { href: "/", label: "Overview", short: "Home", icon: House },
  { href: "/strategies", label: "Strategies", short: "Versions", icon: Scales },
  { href: "/bets", label: "Bets", short: "Bets", icon: Receipt },
  { href: "/markets", label: "Markets", short: "Markets", icon: Target },
  { href: "/model", label: "Model", short: "Model", icon: Flask },
  { href: "/experiments", label: "Experiments", short: "Tests", icon: TestTube },
  { href: "/ratings", label: "Ratings", short: "Ratings", icon: Ranking },
] as const;

const isActive = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-xl bg-ink text-surface">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
          <path d="M3 17l5-6 4 3 6-8 3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <div className="leading-tight">
        <p className="text-[14px] font-semibold tracking-tight text-ink">Closing Line</p>
        <p className="text-[11px] text-ink-3">Paper trading desk</p>
      </div>
    </div>
  );
}

function SignOutButton({ compact = false }: { compact?: boolean }) {
  return (
    <form action="/api/logout" method="post">
      <button
        type="submit"
        aria-label="Sign out"
        className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-xl text-[13px] font-medium text-ink-3 transition-colors hover:bg-sunken hover:text-ink active:scale-[0.98] ${compact ? "px-3" : "w-full px-3"}`}
      >
        <SignOut size={18} weight="regular" aria-hidden />
        {!compact && "Sign out"}
      </button>
    </form>
  );
}

export default function Nav({ updated, searchIndex }: { updated: string; searchIndex: SearchItem[] }) {
  const path = usePathname();
  const [searching, setSearching] = useState(false);
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col border-r border-line/80 bg-surface/70 px-4 py-6 backdrop-blur-xl lg:flex">
        <div className="px-2"><Logo /></div>
        <div className="mt-7"><SearchBox index={searchIndex} /></div>
        <nav aria-label="Main" className="mt-5 flex flex-col gap-1">
          {ITEMS.map(({ href, label, icon: Icon }) => {
            const active = isActive(path, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-[14px] font-medium transition-colors duration-200 ${active ? "text-ink" : "text-ink-3 hover:text-ink-2"}`}
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-xl bg-sunken ring-1 ring-line/80"
                    transition={{ type: "spring", stiffness: 380, damping: 34 }}
                  />
                )}
                <Icon size={19} weight={active ? "fill" : "regular"} className="relative" aria-hidden />
                <span className="relative">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto flex flex-col gap-3">
          <AgentStatus updated={updated} />
          <div className="border-t border-line/80 pt-3"><SignOutButton /></div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-20 border-b border-line/70 bg-canvas/85 px-4 py-3 backdrop-blur-xl lg:hidden">
        <div className="flex items-center justify-between">
          <Logo />
          <div className="flex items-center">
            <button
              type="button"
              aria-label={searching ? "Close search" : "Search matches and players"}
              aria-expanded={searching}
              onClick={() => setSearching((s) => !s)}
              className="grid min-h-11 min-w-11 cursor-pointer place-items-center rounded-xl text-ink-3 transition-colors hover:bg-sunken hover:text-ink"
            >
              {searching ? <X size={19} aria-hidden /> : <MagnifyingGlass size={19} aria-hidden />}
            </button>
            <SignOutButton compact />
          </div>
        </div>
        {searching && <div className="mt-3"><SearchBox index={searchIndex} autoFocus onDone={() => setSearching(false)} /></div>}
      </header>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-7 border-t border-line/80 bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
      >
        {ITEMS.map(({ href, short, icon: Icon }) => {
          const active = isActive(path, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-14 min-w-0 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors ${active ? "text-ink" : "text-ink-3"}`}
            >
              <Icon size={20} weight={active ? "fill" : "regular"} aria-hidden />
              <span className="max-w-full truncate px-0.5">{short}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
