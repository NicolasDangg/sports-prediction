import BankrollChart, { type Series } from "@/components/BankrollChart";
import { loadDashboard, type Bet } from "@/lib/data";

// Categorical slots in fixed order (validated palette); a wallet keeps its color forever.
const SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

const money = (v: number, sign = false) =>
  `${sign && v > 0 ? "+" : v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
const pct = (v: number, sign = false) => `${sign && v > 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
const walletLabel = (w: string) => {
  const [sport, strategy] = w.split(":");
  return `${sport === "epl" ? "EPL" : "ATP"} · ${strategy}`;
};
const when = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });

export default function Page() {
  const d = loadDashboard();
  // EPL wallets first, then ATP; within a sport, strategies in version order.
  const walletOrder = d.liveCurves.map((c) => c.wallet)
    .sort((a, b) => (a.startsWith("epl") ? 0 : 1) - (b.startsWith("epl") ? 0 : 1) || a.localeCompare(b));
  const colorOf = (w: string) => SERIES_COLORS[walletOrder.indexOf(w) % SERIES_COLORS.length];
  const live: Series[] = d.liveCurves.map((c) => ({ name: walletLabel(c.wallet), color: colorOf(c.wallet), points: c.points }));
  const totalBankroll = d.latest.reduce((s, r) => s + r.bankroll, 0);
  const totalStart = d.latest.length * 1000;

  return (
    <main>
      <header className="top">
        <div>
          <p className="eyebrow">Paper trading · virtual money only</p>
          <h1>Sports prediction</h1>
        </div>
        <p className="updated">Updated {d.latestDate || "—"}</p>
      </header>

      <section className="hero card">
        <div>
          <p className="label">Total virtual bankroll</p>
          <p className="hero-value">{money(totalBankroll)}</p>
          <p className={`delta ${totalBankroll >= totalStart ? "up" : "down"}`}>
            {money(totalBankroll - totalStart, true)} vs {money(totalStart)} start
          </p>
        </div>
        <div className="tiles">
          {d.latest.map((w) => (
            <div key={w.wallet} className="tile">
              <p className="label"><i className="swatch" style={{ background: colorOf(w.wallet) }} />{walletLabel(w.wallet)}</p>
              <p className="tile-value">{money(w.bankroll)}</p>
              <p className="muted">
                {w.bets_settled} settled · {w.bets_open} open
                {w.bets_settled > 0 && <> · ROI {pct(w.roi, true)}</>}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Live bankroll</h2>
        <p className="sub">Each wallet started with $1,000. Bets are placed every morning with odds from before the match.</p>
        <BankrollChart series={live} />
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Open bets <span className="count">{d.openBets.length}</span></h2>
          <BetTable bets={d.openBets} colorOf={colorOf} open />
        </section>
        <section className="card">
          <h2>Settled bets</h2>
          {d.settledBets.length ? <BetTable bets={d.settledBets} colorOf={colorOf} /> : <p className="empty">Nothing settled yet. Results arrive the morning after each match.</p>}
        </section>
      </div>

      <section className="card">
        <h2>Upcoming matches</h2>
        <p className="sub">What Elo thinks vs what the bookmakers think (vig removed). A bet happens only when Elo&apos;s price beats the odds by at least 5%.</p>
        <h3>With a bet <span className="muted">· {d.upcoming.filter((m) => m.hasBet).length}</span></h3>
        <MatchGrid matches={d.upcoming.filter((m) => m.hasBet)} />
        <details className="more">
          <summary>All other priced matches ({d.upcoming.filter((m) => !m.hasBet).length})</summary>
          <MatchGrid matches={d.upcoming.filter((m) => !m.hasBet)} />
        </details>
      </section>

      {d.backtest && (
        <section className="card">
          <h2>Backtest: does Elo beat the bookmaker?</h2>
          <p className="sub">
            Replayed history match by match, using only information available before each match. Log loss measures how good the
            probabilities are: lower is better, and confident wrong predictions are punished hard.
          </p>
          <div className="grid-2 tight">
            {(["epl", "atp"] as const).map((k) => {
              const b = d.backtest![k];
              const rows = [
                { name: b.baseline_label, v: b.log_loss.baseline },
                { name: "Elo", v: b.log_loss.elo },
                { name: "Bookmaker", v: b.log_loss.bookmaker },
              ];
              const best = Math.min(...rows.map((r) => r.v));
              return (
                <div key={k}>
                  <h3>{k === "epl" ? "EPL" : "ATP"} <span className="muted">· {b.test_period}, {b.matches.toLocaleString()} matches</span></h3>
                  <table className="table">
                    <thead><tr><th>Predictor</th><th className="num">Log loss</th></tr></thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.name} className={r.v === best ? "best" : ""}>
                          <td>{r.name}</td><td className="num">{r.v.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="muted small">
                    Wallet: {b.wallet.bets.toLocaleString()} bets, ROI {pct(b.wallet.roi, true)}, ended at {money(b.wallet.final_bankroll)}
                  </p>
                </div>
              );
            })}
          </div>
          <h3 className="mt">Backtest bankroll</h3>
          <BankrollChart series={[
            { name: "EPL · elo_v0", color: SERIES_COLORS[0], points: d.backtestCurves.epl },
            { name: "ATP · elo_v0", color: SERIES_COLORS[1], points: d.backtestCurves.atp },
          ]} />
          <p className="callout">
            The bookmaker wins in both sports, and adding Elo to the market&apos;s probabilities only makes them worse. Elo&apos;s
            &ldquo;edges&rdquo; are its own mistakes. The live wallets run Elo v0 as a control group: every later version must beat it.
          </p>
        </section>
      )}

      <div className="grid-2">
        <section className="card">
          <h2>EPL Elo</h2>
          <table className="table">
            <thead><tr><th>#</th><th>Team</th><th className="num">Elo</th></tr></thead>
            <tbody>
              {d.eplRatings.map((r, i) => (
                <tr key={r.team}><td className="muted">{i + 1}</td><td>{r.team}</td><td className="num">{Math.round(r.elo)}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="card">
          <h2>ATP Elo <span className="muted small">top 20</span></h2>
          <table className="table">
            <thead><tr><th>#</th><th>Player</th><th className="num">Overall</th><th className="num">Hard</th><th className="num">Clay</th><th className="num">Grass</th></tr></thead>
            <tbody>
              {d.atpRatings.map((r, i) => (
                <tr key={r.player}>
                  <td className="muted">{i + 1}</td><td>{r.player}</td><td className="num">{Math.round(r.elo)}</td>
                  <td className="num muted">{Math.round(r.elo_hard)}</td><td className="num muted">{Math.round(r.elo_clay)}</td><td className="num muted">{Math.round(r.elo_grass)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <footer>
        Data: football-data.co.uk, Kaggle ATP daily pull, The Odds API. Updated each morning by a scheduled agent. No real money is wagered.
      </footer>
    </main>
  );
}

type Upcoming = ReturnType<typeof loadDashboard>["upcoming"][number];

function MatchGrid({ matches }: { matches: Upcoming[] }) {
  if (!matches.length) return <p className="empty">None today.</p>;
  return (
    <div className="matches">
      {matches.map((m) => (
        <div key={m.event_id} className={`match ${m.hasBet ? "has-bet" : ""}`}>
          <div className="match-head">
            <span className="muted">{m.competition} · {when(m.commence_time)}</span>
          </div>
          {m.outcomes.map((o) => (
            <div key={o.outcome} className="outcome">
              <span className="outcome-name">{o.outcome}</span>
              <ProbBar label="Elo" value={o.elo_p} />
              <ProbBar label="Market" value={o.market_p} muted />
              <span className={`edge ${o.edge >= 0.05 ? "pos" : ""}`}>{pct(o.edge, true)}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ProbBar({ label, value, muted = false }: { label: string; value: number; muted?: boolean }) {
  return (
    <span className="prob" title={`${label}: ${(value * 100).toFixed(1)}%`}>
      <span className="prob-track"><span className={`prob-fill ${muted ? "muted-fill" : ""}`} style={{ width: `${value * 100}%` }} /></span>
      <span className="prob-num">{label} {Math.round(value * 100)}%</span>
    </span>
  );
}

function BetTable({ bets, colorOf, open = false }: { bets: Bet[]; colorOf: (w: string) => string; open?: boolean }) {
  if (!bets.length) return <p className="empty">No open bets.</p>;
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr><th>Match</th><th>Pick</th><th className="num">Odds</th><th className="num">Stake</th><th className="num">{open ? "Model / mkt" : "P&L"}</th></tr>
        </thead>
        <tbody>
          {bets.map((b) => (
            <tr key={b.bet_id}>
              <td>
                <i className="swatch" style={{ background: colorOf(b.wallet) }} />
                {b.match}
                <div className="muted small">{when(b.commence_time)}</div>
              </td>
              <td>{b.pick}</td>
              <td className="num">{b.odds.toFixed(2)}</td>
              <td className="num">{money(b.stake)}</td>
              <td className={`num ${open ? "" : b.pnl > 0 ? "up" : b.pnl < 0 ? "down" : ""}`}>
                {open ? `${Math.round(b.model_p * 100)}% / ${Math.round(b.market_p * 100)}%` : b.status === "void" ? "void" : money(b.pnl, true)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
