"""Virtual wallet money movements: opening balances, deposits and refills.

Every movement is appended to state/deposits.csv, so profit is always measured honestly:

    profit = bankroll - total deposited

A refill therefore never looks like a win, and a wallet's betting history stays intact.

    uv run python accounts.py list
    uv run python accounts.py deposit atp:elo_v0 4000 --reason "raise to $5,000"
    uv run python accounts.py refill  atp:elo_v0 --reason "shipped elo_v1 (E003)"   # top up to $5,000
    uv run python accounts.py refill  atp:elo_v0 --to 2500 --reason "..."
"""

import argparse
import json
from pathlib import Path

import pandas as pd

STATE = Path(__file__).parent / "state"
DEPOSITS, WALLETS, LEDGER = STATE / "deposits.csv", STATE / "wallets.json", STATE / "ledger.csv"
DEFAULT_START = 5000.0
COLS = ["at", "wallet", "amount", "kind", "reason"]


def load_deposits() -> pd.DataFrame:
    return pd.read_csv(DEPOSITS) if DEPOSITS.exists() else pd.DataFrame(columns=COLS)


def deposited(deposits: pd.DataFrame, wallet: str) -> float:
    return float(deposits.loc[deposits.wallet == wallet, "amount"].sum())


def record(deposits: pd.DataFrame, wallets: dict, wallet: str, amount: float, kind: str,
           reason: str, at: str) -> pd.DataFrame:
    """Add money to a wallet's cash and log it. Mutates `wallets`, returns the new deposits table."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    w = wallets.setdefault(wallet, {"cash": 0.0})
    w["cash"] = round(w["cash"] + amount, 2)
    row = pd.DataFrame([{"at": at, "wallet": wallet, "amount": round(amount, 2), "kind": kind, "reason": reason}])
    return pd.concat([deposits, row], ignore_index=True) if len(deposits) else row


def bankroll(wallets: dict, ledger: pd.DataFrame, wallet: str) -> float:
    open_stakes = ledger.loc[(ledger.wallet == wallet) & (ledger.status == "open"), "stake"].sum() if len(ledger) else 0
    return wallets.get(wallet, {"cash": 0.0})["cash"] + float(open_stakes)


def _load() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    wallets = json.loads(WALLETS.read_text()) if WALLETS.exists() else {}
    ledger = pd.read_csv(LEDGER) if LEDGER.exists() else pd.DataFrame(columns=["wallet", "status", "stake"])
    return wallets, ledger, load_deposits()


def _save(wallets: dict, deposits: pd.DataFrame) -> None:
    WALLETS.write_text(json.dumps(wallets, indent=2))
    deposits.to_csv(DEPOSITS, index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    d = sub.add_parser("deposit")
    d.add_argument("wallet"); d.add_argument("amount", type=float); d.add_argument("--reason", required=True)
    r = sub.add_parser("refill", help="top a wallet's bankroll (cash + open bets) back up to a target")
    r.add_argument("wallet"); r.add_argument("--to", type=float, default=DEFAULT_START); r.add_argument("--reason", required=True)
    args = ap.parse_args()

    wallets, ledger, deposits = _load()
    now = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")

    if args.cmd in ("deposit", "refill") and args.wallet not in wallets:
        raise SystemExit(f"unknown wallet {args.wallet!r}; existing: {', '.join(wallets)}")
    if args.cmd == "deposit":
        deposits = record(deposits, wallets, args.wallet, args.amount, "deposit", args.reason, now)
        _save(wallets, deposits)
    elif args.cmd == "refill":
        gap = args.to - bankroll(wallets, ledger, args.wallet)
        if gap <= 0.005:
            raise SystemExit(f"{args.wallet} already holds {bankroll(wallets, ledger, args.wallet):,.2f} >= {args.to:,.2f}")
        deposits = record(deposits, wallets, args.wallet, gap, "refill", args.reason, now)
        _save(wallets, deposits)
        print(f"refilled {args.wallet} with {gap:,.2f}")

    print(f"{'wallet':<16}{'cash':>12}{'bankroll':>12}{'deposited':>12}{'profit':>12}")
    for w in sorted(wallets):
        b, dep = bankroll(wallets, ledger, w), deposited(deposits, w)
        print(f"{w:<16}{wallets[w]['cash']:>12,.2f}{b:>12,.2f}{dep:>12,.2f}{b - dep:>+12,.2f}")


if __name__ == "__main__":
    main()
