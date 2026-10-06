"use client";

import { memo, useEffect, useState } from "react";

const RUN_HOUR_UTC = 23; // 06:00 Asia/Ho_Chi_Minh

function nextRun(now: Date) {
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), RUN_HOUR_UTC));
  if (next <= now) next.setUTCDate(next.getUTCDate() + 1);
  return next;
}

/** Breathing dot + countdown to the next morning run. Isolated so its timer never re-renders the page. */
function AgentStatus({ updated }: { updated: string }) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const mins = now ? Math.max(0, Math.round((nextRun(now).getTime() - now.getTime()) / 60000)) : null;
  const countdown = mins === null ? "—" : `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;

  return (
    <div className="rounded-2xl bg-sunken/70 p-3.5 ring-1 ring-line/70">
      <div className="flex items-center gap-2 text-[12px] font-medium text-ink-2">
        <span className="breathe relative inline-block size-2 rounded-full text-up" style={{ background: "currentColor" }} />
        Agent active
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-ink-3">
        Last update <span className="text-ink-2 tabular">{updated || "—"}</span>
        <br />
        Next run in <span className="text-ink-2 tabular">{countdown}</span> · 06:00
      </p>
    </div>
  );
}

export default memo(AgentStatus);
