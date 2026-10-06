"""Virtual wallet ("paper trading"): fake money, real rules.

The agent only bets when it thinks the bookmaker's price is wrong in its favour:

    edge = model_probability * decimal_odds - 1

Example: the model says 55%, the odds are 2.00 (bookmaker implies ~50%).
edge = 0.55 * 2.00 - 1 = +0.10, so on average each $1 bet returns $1.10.

How much to bet: the Kelly criterion picks the stake that grows a bankroll fastest
*if your probabilities are right*. They won't be exactly right, so we bet a fraction
of Kelly (quarter-Kelly) and cap any single bet. That keeps a bad model from going
broke quickly while still showing what it would have done.
"""

from dataclasses import dataclass, field


@dataclass
class Wallet:
    bankroll: float = 1000.0
    min_edge: float = 0.03  # skip bets with less than +3% expected value
    kelly_fraction: float = 0.25
    max_stake_pct: float = 0.05  # never risk more than 5% of the bankroll on one bet
    bets: list[dict] = field(default_factory=list)

    def consider(self, options: list[tuple[str, float, float]]) -> tuple[str, float, float, float] | None:
        """options: (outcome label, model probability, decimal odds) for each outcome.
        Returns the single best bet (label, prob, odds, stake), or None if none is good enough."""
        best = None
        for label, p, odds in options:
            if not odds or odds <= 1:
                continue
            edge = p * odds - 1
            if edge >= self.min_edge and (best is None or edge > best[0]):
                best = (edge, label, p, odds)
        if best is None:
            return None
        edge, label, p, odds = best
        kelly = edge / (odds - 1)  # full-Kelly fraction of bankroll
        stake = self.bankroll * min(self.kelly_fraction * kelly, self.max_stake_pct)
        return label, p, odds, round(stake, 2)

    def place_and_settle(self, info: dict, label: str, p: float, odds: float,
                         stake: float, won: bool) -> None:
        """Backtests know the result immediately, so place and settle in one step."""
        pnl = stake * (odds - 1) if won else -stake
        self.bankroll += pnl
        self.bets.append({**info, "pick": label, "model_p": round(p, 4), "odds": odds,
                          "edge": round(p * odds - 1, 4), "stake": stake, "won": won,
                          "pnl": round(pnl, 2), "bankroll": round(self.bankroll, 2)})

    def summary(self, start: float = 1000.0) -> dict:
        staked = sum(b["stake"] for b in self.bets)
        pnl = sum(b["pnl"] for b in self.bets)
        peak, max_dd = start, 0.0
        for b in self.bets:
            peak = max(peak, b["bankroll"])
            max_dd = max(max_dd, 1 - b["bankroll"] / peak)
        return {
            "bets": len(self.bets),
            "win_rate": sum(b["won"] for b in self.bets) / len(self.bets) if self.bets else 0,
            "staked": round(staked, 2),
            "profit": round(pnl, 2),
            "roi": pnl / staked if staked else 0,  # profit per $1 staked
            "final_bankroll": round(self.bankroll, 2),
            "max_drawdown": max_dd,  # worst peak-to-trough drop
        }
