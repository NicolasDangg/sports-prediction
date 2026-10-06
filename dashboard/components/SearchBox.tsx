"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MagnifyingGlass, TennisBall, User } from "@phosphor-icons/react";
import type { SearchItem } from "@/lib/match";

const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
const MAX = 8;

const whenShort = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });

/** Every query word must appear somewhere in the item ("rune hard", "shanghai sinner"). Matches before players. */
function search(index: SearchItem[], q: string) {
  const words = norm(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  return index.filter((it) => {
    const hay = norm(`${it.label} ${it.terms} ${it.sub}`);
    return words.every((w) => hay.includes(w));
  }).slice(0, MAX);
}

export default function SearchBox({ index, autoFocus = false, onDone }: { index: SearchItem[]; autoFocus?: boolean; onDone?: () => void }) {
  const router = useRouter();
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const results = useMemo(() => search(index, q), [index, q]);

  // "/" focuses search from anywhere (unless already typing somewhere).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key !== "/" || t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (!input.current?.offsetParent) return; // hidden (other breakpoint)
      e.preventDefault();
      input.current.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (it: SearchItem) => {
    setQ("");
    setOpen(false);
    input.current?.blur();
    onDone?.();
    router.push(it.href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); go(results[active]); }
    else if (e.key === "Escape") { setOpen(false); input.current?.blur(); onDone?.(); }
  };

  const showList = open && q.trim().length > 0;

  return (
    <div className="relative">
      <label className="flex min-h-11 items-center gap-2 rounded-xl border border-line/80 bg-surface px-3 text-ink-3 transition-colors focus-within:border-ink-3/50 focus-within:text-ink">
        <MagnifyingGlass size={17} aria-hidden />
        <span className="sr-only">Search matches and players</span>
        <input
          ref={input}
          autoFocus={autoFocus}
          value={q}
          onChange={(e) => { setQ(e.target.value); setActive(0); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={showList && results[active] ? `${listId}-${active}` : undefined}
          placeholder="Search matches, players"
          className="min-w-0 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3 lg:text-[13px]"
        />
        <kbd className="hidden rounded-md border border-line px-1.5 font-mono text-[11px] text-ink-3 lg:inline">/</kbd>
      </label>

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className="absolute inset-x-0 top-full z-30 mt-1.5 max-h-[60vh] overflow-y-auto rounded-xl border border-line/80 bg-surface p-1 shadow-diffuse lg:w-[340px]"
        >
          {results.length === 0 && <li className="px-3 py-3 text-[13px] text-ink-3">No ATP match or player matches “{q}”.</li>}
          {results.map((it, i) => {
            const Icon = it.kind === "match" ? TennisBall : User;
            return (
              <li
                key={it.href}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => { e.preventDefault(); go(it); }}
                onMouseEnter={() => setActive(i)}
                className={`flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 ${i === active ? "bg-sunken" : ""}`}
              >
                <Icon size={18} className={it.kind === "match" ? "shrink-0 text-atp" : "shrink-0 text-ink-3"} aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-ink">{it.label}</span>
                  <span className="block truncate text-[12px] text-ink-3">
                    {it.sub}{it.when ? ` · ${whenShort(it.when)}` : ""}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
