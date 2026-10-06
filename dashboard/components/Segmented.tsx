"use client";

import { motion } from "motion/react";
import { useId } from "react";

export type Option<T extends string> = { value: T; label: string; count?: number };

/** Segmented control; the selected pill slides between options (shared layout animation). */
export default function Segmented<T extends string>({ options, value, onChange, label }: {
  options: Option<T>[]; value: T; onChange: (v: T) => void; label: string;
}) {
  const id = useId();
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-full bg-sunken p-1 ring-1 ring-line/70">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={`relative min-h-9 cursor-pointer rounded-full px-3.5 text-[13px] font-medium transition-colors duration-200 active:scale-[0.98] ${active ? "text-ink" : "text-ink-3 hover:text-ink-2"}`}
          >
            {active && (
              <motion.span
                layoutId={`seg-${id}`}
                className="absolute inset-0 rounded-full bg-surface shadow-[0_1px_2px_rgb(17_20_26/0.08),0_0_0_1px_rgb(17_20_26/0.04)]"
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            )}
            <span className="relative inline-flex items-center gap-1.5">
              {o.label}
              {o.count !== undefined && <span className="text-[11px] text-ink-3 tabular">{o.count}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}
