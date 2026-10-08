"use client";

import { useState } from "react";
import { Check, Copy } from "@phosphor-icons/react";

/** Copies a search term to the clipboard (for pasting into SofaScore's own search box). */
export default function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard blocked: the term is visible next to the button */
        }
      }}
      className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-xl border border-line px-3 text-[13px] font-medium text-ink transition-colors hover:bg-sunken"
    >
      {done ? <Check size={14} weight="bold" className="text-up" aria-hidden /> : <Copy size={14} aria-hidden />}
      <span aria-live="polite">{done ? "Copied" : label}</span>
    </button>
  );
}
