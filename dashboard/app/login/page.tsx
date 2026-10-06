import { safeNext } from "@/lib/auth";
import LoginForm from "./LoginForm";

export const metadata = { title: "Sign in · Closing Line" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main id="main" className="grid min-h-[100dvh] grid-cols-1 lg:grid-cols-[1.1fr_1fr]">
      {/* Left: quiet brand panel with a drawn bankroll line */}
      <section className="relative hidden overflow-hidden border-r border-line/80 bg-surface lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-xl bg-ink text-surface">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
              <path d="M3 17l5-6 4 3 6-8 3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="text-[14px] font-semibold tracking-tight">Closing Line</span>
        </div>

        <svg viewBox="0 0 600 260" className="w-full max-w-[560px]" aria-hidden>
          {[40, 100, 160, 220].map((y) => <line key={y} x1="0" x2="600" y1={y} y2={y} stroke="var(--color-line-soft)" />)}
          <line x1="0" x2="600" y1="130" y2="130" stroke="#c7ccd4" />
          <polyline fill="none" stroke="var(--color-epl)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            points="0,130 40,124 80,138 120,121 160,128 200,112 240,119 280,104 320,116 360,98 400,107 440,92 480,101 520,86 560,94 600,80" />
          <polyline fill="none" stroke="var(--color-atp)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            points="0,130 40,137 80,129 120,146 160,139 200,152 240,141 280,158 320,149 360,163 400,151 440,168 480,159 520,171 560,162 600,174" />
          <circle cx="600" cy="80" r="5" fill="var(--color-epl)" stroke="white" strokeWidth="2" />
          <circle cx="600" cy="174" r="5" fill="var(--color-atp)" stroke="white" strokeWidth="2" />
        </svg>

        <div className="max-w-[46ch]">
          <h1 className="text-[32px] font-semibold leading-[1.05] tracking-tighter text-ink">Measured against the bookmaker, every morning.</h1>
          <p className="mt-4 text-[15px] leading-relaxed text-ink-2">
            Elo models for the Premier League and the ATP Tour, placing paper bets with virtual money and keeping score honestly.
          </p>
        </div>
      </section>

      {/* Right: the form */}
      <section className="flex items-center justify-center px-4 py-12 md:px-8">
        <div className="w-full max-w-[380px]">
          <div className="mb-8 lg:hidden">
            <span className="text-[14px] font-semibold tracking-tight">Closing Line</span>
          </div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-3">Private dashboard</p>
          <h2 className="mt-2 text-[26px] font-semibold leading-tight tracking-tighter text-ink">Sign in</h2>
          <p className="mb-8 mt-2 text-[14px] leading-relaxed text-ink-3">Enter the password to see the wallets, bets and model.</p>
          <LoginForm next={safeNext(next)} />
        </div>
      </section>
    </main>
  );
}
