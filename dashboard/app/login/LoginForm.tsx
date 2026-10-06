"use client";

import { useRef, useState } from "react";
import { ArrowRight, Eye, EyeSlash, LockSimple } from "@phosphor-icons/react";

export default function LoginForm({ next }: { next: string }) {
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const password = input.current?.value ?? "";
    if (!password) {
      setError("Enter the dashboard password.");
      input.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password, next }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error ?? "Something went wrong. Try again.");
      window.location.assign(data.next ?? "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
      setBusy(false);
      input.current?.select();
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <label htmlFor="password" className="text-[13px] font-medium text-ink">Password</label>
        <div className="relative">
          <LockSimple size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            ref={input}
            id="password"
            name="password"
            type={show ? "text" : "password"}
            autoComplete="current-password"
            autoFocus
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "password-error" : "password-help"}
            className={`h-12 w-full rounded-xl border bg-surface pl-10 pr-12 text-base text-ink outline-none transition-[border-color,box-shadow] duration-200 placeholder:text-ink-3 focus:border-ink focus:ring-4 focus:ring-ink/5 ${error ? "border-down" : "border-line"}`}
          />
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            aria-label={show ? "Hide password" : "Show password"}
            aria-pressed={show}
            className="absolute right-1.5 top-1/2 grid size-9 -translate-y-1/2 cursor-pointer place-items-center rounded-lg text-ink-3 transition-colors hover:bg-sunken hover:text-ink"
          >
            {show ? <EyeSlash size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
          </button>
        </div>
        {error ? (
          <p id="password-error" role="alert" className="text-[13px] text-down">{error}</p>
        ) : (
          <p id="password-help" className="text-[13px] text-ink-3">You stay signed in on this device for 30 days.</p>
        )}
      </div>

      <button
        type="submit"
        disabled={busy}
        className="group inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-xl bg-ink text-[14px] font-semibold text-surface transition-[transform,opacity] duration-200 hover:opacity-90 active:scale-[0.98] disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? (
          <>
            <span className="size-4 animate-spin rounded-full border-2 border-surface/30 border-t-surface" aria-hidden />
            Checking
          </>
        ) : (
          <>
            Unlock dashboard
            <ArrowRight size={16} weight="bold" className="transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
          </>
        )}
      </button>
    </form>
  );
}
