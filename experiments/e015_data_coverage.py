"""E015: six predeclared coverage gates, frozen validation, then one guarded test look.

Default: train diagnostics/selection and conditional validation, never test scoring.
--test: consume one previously used historical test window after validation passes.
Outputs are analysis artifacts; no strategy activation or live wallet writes.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest as bt
from elo import TennisElo
from strategies import coverage_ok
from wallet import Wallet

ATP_PARAMS = dict(k_scale=200, surface_weight=0.5)
THRESHOLDS = [(n, s) for n in (10, 20, 40) for s in (5, 10)]
RANGES = {"diagnostics": ["2010-01-01", "2016-12-31"],
          "selection": ["2017-01-01", "2019-12-31"],
          "validation": ["2020-01-01", "2022-12-31"],
          "test": ["2023-01-01", "2026-10-05"]}
PROTOCOL = {"version": 1, "thresholds": [list(t) for t in THRESHOLDS],
            "ranges": RANGES, "elo": ATP_PARAMS, "min_edge": 0.05,
            "start_bankroll": 1000, "min_accepted": 500, "min_retention": 0.5,
            "bootstrap_reps": 2000, "bootstrap_seed": 15, "tie_tolerance": 1e-12}
OUT = ROOT / "results/e015_data_coverage.json"
BETS = ROOT / "results/e015_data_coverage_bets.csv"
CSV_COLUMNS = ["stage", "date", "Tournament", "Player_1", "Player_2", "Surface", "Winner", "p1_won",
               "p1_total", "p2_total", "p1_surface", "p2_surface", "min_total_matches", "min_surface_matches",
               "p", "baseline_p", "Odd_1", "Odd_2", "valid_odds", "bet_opportunity", "pick", "pick_p",
               "pick_odds", "won", "min_total", "min_surface", "coverage_ok", "coverage_reason", "r", "g_r", "d"]
CSV_COLUMNS += [key for n, s in THRESHOLDS for key in (f"coverage_{n}_{s}", f"reason_{n}_{s}")]
CAVEATS = [
    "Stable loader ordering within dates is retrospective; start times are not available.",
    "Counts cover only matches updating v0; they do not establish source completeness or recency.",
    "Historical row odds are execution prices; their timestamp quality is not established.",
    "Wallets settle immediately, so do not reproduce overlapping live cash commitments.",
    "Wallet.consider may return rounded zero stakes; these are retained and counted separately.",
    "Flat opportunities use an undepleted selector; wallet depletion never changes that sample.",
    "Bootstrap is for paired unit profits, not compounded bankrolls.",
    "Historical test years were used by earlier experiments and are not unseen data.",
    "No live identity/staleness feed exists here; rows use the unchanged historical v0 identity rules.",
    "All-match probabilities are unchanged; subset scores do not imply a better model."]


def replay(df):
    """Record features before each update, including all pre-2010 warmup rows."""
    if df.empty:
        raise ValueError("Cannot replay empty rating history")
    elo, rows = TennisElo(**ATP_PARAMS), []
    for g in df.itertuples():
        a, b, s = g.Player_1, g.Player_2, g.Surface
        na, nb = elo.n_overall.get(a, 0), elo.n_overall.get(b, 0)
        sa, sb = elo.n_surface.get((a, s), 0), elo.n_surface.get((b, s), 0)
        rows.append({"p": elo.prob(a, b, s), "p1_total": na, "p2_total": nb,
                     "p1_surface": sa, "p2_surface": sb,
                     "min_total_matches": min(na, nb), "min_surface_matches": min(sa, sb)})
        elo.update(a if g.p1_won else b, b if g.p1_won else a, s)
    result = pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    baseline, _ = bt.tennis_probs(df, **ATP_PARAMS)
    np.testing.assert_allclose(result.p, baseline, rtol=0, atol=1e-12)
    result["baseline_p"] = baseline
    return result


def opportunities(df):
    """One undepleted Wallet selects baseline picks; retain every forecast row."""
    selector = Wallet(min_edge=0.05)
    rows = []
    for g in df.itertuples():
        valid = bool(np.isfinite([g.Odd_1, g.Odd_2]).all() and min(g.Odd_1, g.Odd_2) > 1)
        bet = selector.consider([(g.Player_1, g.p, g.Odd_1),
                                 (g.Player_2, 1 - g.p, g.Odd_2)]) if valid else None
        label, p, odds = bet[:3] if bet else (None, None, None)
        won = bool(label == g.Winner) if bet else None
        rows.append({"valid_odds": valid, "bet_opportunity": bet is not None,
                     "pick": label, "pick_p": p, "pick_odds": odds, "won": won,
                     "r": odds * won - 1 if bet else None})
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def gate_rows(df, threshold, stage):
    result = df.copy()
    n, s = threshold
    result["coverage_ok"] = pd.Series(
        [coverage_ok(r, n, s) for r in result.to_dict("records")], index=result.index, dtype=bool)
    result["coverage_reason"] = np.select(
        [result.coverage_ok, result.min_total_matches < n, result.min_surface_matches < s],
        ["ok", "insufficient_total", "insufficient_surface"], default="missing_counts")
    result["g_r"] = result.coverage_ok.astype(int) * result.r
    result["d"] = (result.coverage_ok.astype(int) - 1) * result.r
    result["stage"], result["min_total"], result["min_surface"] = stage, n, s
    return result


def flat_summary(rows):
    bets = rows[rows.bet_opportunity]
    accepted = bets[bets.coverage_ok]
    rejected = bets[~bets.coverage_ok]
    mean = lambda s: float(s.mean()) if len(s) else None
    return {"matches": len(rows), "baseline_opportunities": len(bets),
            "accepted": len(accepted), "rejected": len(rejected),
            "retention": len(accepted) / len(bets) if len(bets) else None,
            "baseline_flat_roi": mean(bets.r), "accepted_flat_roi": mean(accepted.r),
            "rejected_flat_roi": mean(rejected.r), "paired_improvement": mean(bets.d),
            "baseline_unit_profit": float(bets.r.sum()),
            "gated_unit_profit": float(bets.g_r.sum()),
            "paired_unit_profit": float(bets.d.sum())}


def scores(rows, probability="p"):
    if not len(rows):
        return {"n": 0, "log_loss": None, "brier": None}
    p, y = rows[probability].to_numpy(float), rows.p1_won.to_numpy(bool)
    return {"n": len(rows), "log_loss": float(-np.log(np.clip(np.where(y, p, 1-p), 1e-12, 1)).mean()),
            "brier": float(np.square(p-y).mean())}


def forecast_scores(rows):
    result = {}
    for name, part in (("all", rows), ("accepted", rows[rows.coverage_ok]),
                       ("rejected", rows[~rows.coverage_ok])):
        market = part[part.valid_odds].copy()
        market["market_p"] = (1 / market.Odd_1) / (1 / market.Odd_1 + 1 / market.Odd_2)
        result[name] = {"v0": scores(part, "baseline_p"), "gated": scores(part),
                        "market": scores(market, "market_p"), "v0_with_market_odds": scores(market)}
        if result[name]["v0"] != result[name]["gated"]:
            raise ValueError("Coverage gate changed forecast scores")
    return result


def wallet_run(rows, gated):
    wallet = Wallet(min_edge=0.05)
    for g in rows.itertuples():
        if not g.valid_odds or (gated and not g.coverage_ok):
            continue
        bet = wallet.consider([(g.Player_1, g.p, g.Odd_1), (g.Player_2, 1-g.p, g.Odd_2)])
        if bet is not None:
            label, p, odds, stake = bet
            wallet.place_and_settle({}, label, p, odds, stake, won=label == g.Winner)
    summary = wallet.summary()
    summary["zero_stake_bets"] = sum(b["stake"] == 0 for b in wallet.bets)
    if not wallet.bets:
        summary["win_rate"] = None
    if not summary["staked"]:
        summary["roi"] = None
    return summary


def cluster_ci(rows, reps=2000):
    bets = rows[rows.bet_opportunity]
    if not len(bets):
        return None
    clusters = bets.groupby([bets.date.dt.year, "Tournament"], dropna=False).d.agg(["sum", "count"])
    sums, counts = clusters["sum"].to_numpy(), clusters["count"].to_numpy()
    rng = np.random.default_rng(15)
    means = []
    for _ in range(reps):
        pick = rng.integers(0, len(clusters), len(clusters))
        means.append(float(sums[pick].sum() / counts[pick].sum()))
    return [float(x) for x in np.percentile(means, [2.5, 97.5])]


def evaluate(df, threshold, stage):
    rows = gate_rows(df, threshold, stage)
    summary = {"threshold": list(threshold), **flat_summary(rows),
               "actual_date_range": [str(rows.date.min().date()), str(rows.date.max().date())] if len(rows) else None,
               "scores": forecast_scores(rows),
               "wallets": {"v0": wallet_run(rows, False), "gated": wallet_run(rows, True)},
               "per_year": {str(year): flat_summary(part) for year, part in rows.groupby(rows.date.dt.year)},
               "by_surface": {str(s): flat_summary(part) for s, part in rows.groupby("Surface", dropna=False)}}
    if stage == "validation":
        summary["paired_ci95"] = cluster_ci(rows)
        summary["bootstrap_clusters"] = len(rows[rows.bet_opportunity].groupby(
            [rows[rows.bet_opportunity].date.dt.year, "Tournament"], dropna=False))
    return summary, rows


def qualifies(summary):
    return summary["accepted"] >= 500 and (summary["retention"] or 0) >= 0.5


def select_candidate(candidates):
    eligible = [c for c in candidates if qualifies(c)]
    if not eligible:
        return None
    best = max(c["paired_improvement"] for c in eligible)
    return min((c for c in eligible if best-c["paired_improvement"] <= 1e-12),
               key=lambda c: tuple(c["threshold"]))


def selection_passes(candidate):
    return bool(candidate and candidate["paired_improvement"] > 0 and
                candidate["accepted_flat_roi"] >= candidate["baseline_flat_roi"])


def stage_rules(summary, stage):
    w = summary["wallets"]
    checks = {"sample": qualifies(summary),
              "wallet_final": w["gated"]["final_bankroll"] >= w["v0"]["final_bankroll"],
              "wallet_drawdown": w["gated"]["max_drawdown"] <= w["v0"]["max_drawdown"]}
    roi, baseline = summary["accepted_flat_roi"], summary["baseline_flat_roi"]
    if stage == "validation":
        ci = summary["paired_ci95"]
        checks.update({"positive_ci": ci is not None and ci[0] > 0,
                       "flat_roi": roi is not None and baseline is not None and roi > baseline,
                       "positive_years": sum((summary["per_year"].get(str(y), {}).get(
                           "paired_improvement") or 0) > 0 for y in (2020, 2021, 2022)) >= 2})
    else:
        improvement = summary["paired_improvement"]
        checks.update({"paired_improvement": improvement is not None and improvement >= 0,
                       "flat_roi": roi is not None and baseline is not None and roi >= baseline})
    return {"checks": checks, "passed": all(checks.values())}


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def input_hashes(root=ROOT):
    files = ["data/tennis/atp_tennis.csv", "backtest.py", "elo.py", "wallet.py", "strategies.py",
             "experiments/e015_data_coverage.py", "docs/superpowers/plans/2026-10-08-e015-data-coverage.md"]
    return {**{p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files},
            "protocol": sha(PROTOCOL)}


def frozen_hash(result):
    return sha({k: result[k] for k in ("inputs", "protocol", "selected", "selection", "validation")})


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def reserve_default(out, bets, hashes):
    if bets.exists():
        raise ValueError("Existing E015 diagnostics are frozen; refusing overwrite")
    result = {"experiment": "E015", "status": "started", "inputs": hashes, "protocol": PROTOCOL,
              "ranges": RANGES, "caveats": CAVEATS, "test_looks_used": 0, "test": None}
    # Exclusive creation preserves interrupted runs instead of silently evaluating them again.
    with out.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
    return result


def start_test(out, hashes, registry_path, log_path):
    """Fail closed; persist the consumed look before load_atp or any test evaluation."""
    result = json.loads(out.read_text())
    if (result.get("status") != "awaiting_test" or not result.get("validation", {}).get("passed")
            or result.get("test") is not None or result.get("test_started") or result.get("test_looks_used") != 0):
        raise ValueError("Test requires frozen successful validation and zero prior E015 test looks")
    if result.get("inputs") != hashes or result.get("protocol") != PROTOCOL:
        raise ValueError("Frozen E015 inputs/protocol changed")
    if (tuple(result.get("selected", [])) not in THRESHOLDS or
            result.get("frozen_sha256") != frozen_hash(result) or
            result["selected"] != result["validation"]["threshold"] or
            result["selected"] != select_candidate(result["selection"])["threshold"]):
        raise ValueError("Frozen E015 threshold/result mismatch")
    registry = json.loads(registry_path.read_text())
    entries = [entry for entry in registry["experiments"] if entry["id"] == "E015"]
    if len(entries) != 1:
        raise ValueError("Exactly one E015 registry entry required before test")
    entry = entries[0]
    if entry.get("test_look") or entry.get("test_started") or entry.get("test_looks_used", 0):
        raise ValueError("Registry already records an E015 test look")
    log = log_path.read_text()
    section = re.search(r"^## E015\b[^\n]*\n.*?(?=^## |\Z)", log, flags=re.M | re.S)
    counter = re.search(r"\*\*Test-set looks used: (\d+)\*\*", log)
    if not section or not counter or int(counter[1]) != registry["test_looks_used"]:
        raise ValueError("E015 log entry and matching global test counters required")
    if re.search(r"test[-_ ]started|test(?:[-_ ]set)?[-_ ]look[^\n]*(?:\byes\b|\btrue\b|\bconsumed\b)", section[0], re.I):
        raise ValueError("Log already records an E015 test look")
    started = datetime.now(timezone.utc).isoformat()
    result.update(test_started=started, test_looks_used=1, status="test_started")
    write_json(out, result)
    entry.update(test_look=True, test_started=started, test_looks_used=1)
    registry["test_looks_used"] += 1
    write_json(registry_path, registry)
    log = log[:section.end()] + f"\n- **E015 test-started:** {started}; one look consumed before outcomes were loaded.\n" + log[section.end():]
    log = re.sub(r"\*\*Test-set looks used: \d+\*\*",
                 f"**Test-set looks used: {registry['test_looks_used']}**", log, count=1)
    temp = log_path.with_suffix(".md.tmp")
    temp.write_text(log)
    temp.replace(log_path)
    return result


def run(test=False):
    OUT.parent.mkdir(exist_ok=True)
    # Advisory lock covers the result/counter read-write sequence for concurrent invocations.
    lock_dir = OUT.parent / "__pycache__"
    lock_dir.mkdir(exist_ok=True)
    with (lock_dir / "e015.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        hashes = input_hashes()
        result = start_test(OUT, hashes, ROOT / "experiments/registry.json", ROOT / "experiments/LOG.md") if test else reserve_default(OUT, BETS, hashes)
        data = bt.load_atp()
        cutoff = RANGES["test"][1] if test else RANGES["validation"][1]
        data = data[data.date <= cutoff].reset_index(drop=True)
        forecasts = opportunities(replay(data))
        result["replay"] = {"warmup_from": str(data.date.min().date()), "through": cutoff,
                            "rows": len(data), "probability_max_abs_difference": float(
                                np.max(np.abs(forecasts.p-forecasts.baseline_p)))}
        period = lambda stage: forecasts[forecasts.date.between(*RANGES[stage])].reset_index(drop=True)
        if test:
            summary, rows = evaluate(period("test"), result["selected"], "test")
            summary.update(stage_rules(summary, "test"))
            summary["both_wallets_lose"] = all(w["final_bankroll"] < 1000 for w in summary["wallets"].values())
            result["test"] = summary
            result["status"] = "complete"
            result["verdict"] = "eligible_for_separately_authorized_paper_comparison" if summary["passed"] else "not_shipped"
            rows.reindex(columns=CSV_COLUMNS).to_csv(BETS, index=False, mode="a", header=not BETS.exists())
        else:
            diagnostics, candidates, csv = [], [], []
            for threshold in THRESHOLDS:
                for stage, target in (("diagnostics", diagnostics), ("selection", candidates)):
                    summary, rows = evaluate(period(stage), threshold, stage)
                    target.append(summary)
            result.update(diagnostics=diagnostics, selection=candidates, variants_evaluated=6,
                          selected=None, validation=None, verdict="not_shipped", status="complete")
            selected = select_candidate(candidates)
            result["selection_passed"] = selection_passes(selected)
            if selected:
                result["selected"] = selected["threshold"]
            reference = result["selected"] or list(THRESHOLDS[0])
            result["csv_reference_threshold"] = reference
            result["csv_reference_is_selected"] = selected is not None
            for stage in ("diagnostics", "selection"):
                rows = gate_rows(period(stage), reference, stage)
                for n, s in THRESHOLDS:
                    mask = gate_rows(period(stage), (n, s), stage)
                    rows[f"coverage_{n}_{s}"] = mask.coverage_ok
                    rows[f"reason_{n}_{s}"] = mask.coverage_reason
                csv.append(rows)
            if result["selection_passed"]:
                validation, rows = evaluate(period("validation"), result["selected"], "validation")
                validation.update(stage_rules(validation, "validation"))
                csv.append(rows)
                result["validation"] = validation
                if validation["passed"]:
                    result.update(status="awaiting_test", verdict="validation_passed_test_pending")
            pd.concat(csv, ignore_index=True).reindex(columns=CSV_COLUMNS).to_csv(BETS, index=False)
            result["frozen_sha256"] = frozen_hash(result)
        if input_hashes() != hashes:
            raise ValueError("Input files changed during replay; the started record is preserved")
        write_json(OUT, result)
        print(json.dumps({"status": result["status"], "selected": result["selected"],
                          "verdict": result["verdict"], "result": str(OUT)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Consume the single frozen-candidate historical test look")
    args = parser.parse_args()
    run(args.test)
