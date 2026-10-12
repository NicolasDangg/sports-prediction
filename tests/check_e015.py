"""Synthetic E015 checks; never load historical outcomes or touch live state."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments import e015_data_coverage as e


def fails(call, error=ValueError):
    try:
        call()
    except error:
        return
    raise AssertionError("Expected refusal")


def fixture():
    return pd.DataFrame({"date": pd.to_datetime(["2009-01-01", "2010-01-01", "2011-01-01", "2017-01-01"]),
                         "Player_1": ["A", "A", "B", "A"], "Player_2": ["B", "B", "A", "B"],
                         "Winner": ["A", "B", "B", "A"], "p1_won": [True, False, True, True],
                         "Surface": ["Hard", "Hard", "Clay", "Hard"], "Tournament": ["One"] * 4,
                         "Odd_1": [2.5] * 4, "Odd_2": [1.8] * 4})


def candidate(threshold, diff=.1):
    return {"threshold": list(threshold), "accepted": 600, "retention": .6,
            "paired_improvement": diff, "accepted_flat_roi": .1, "baseline_flat_roi": 0}


assert e.THRESHOLDS == [(n, s) for n in (10, 20, 40) for s in (5, 10)]
data = fixture()
fails(lambda: e.replay(data.iloc[:0]))
r = e.replay(data)
assert r.min_total_matches.tolist() == [0, 1, 2, 3]
assert r.min_surface_matches.tolist() == [0, 1, 0, 2]
assert r.p1_total.tolist() == [0, 1, 2, 3]
assert r.p1_surface.tolist() == [0, 1, 0, 2]
np.testing.assert_array_equal(r.p, e.bt.tennis_probs(data, **e.ATP_PARAMS)[0])
swapped = data.copy()
swapped[["Player_1", "Player_2"]] = data[["Player_2", "Player_1"]].to_numpy()
swapped["p1_won"] = ~data.p1_won
swap = e.replay(swapped)
np.testing.assert_allclose(r.p, 1-swap.p, rtol=0, atol=1e-12)
np.testing.assert_array_equal(r.min_surface_matches, swap.min_surface_matches)
np.testing.assert_array_equal(r.p1_total, swap.p2_total)
np.testing.assert_array_equal(r.p1_surface, swap.p2_surface)
assert e.coverage_ok(r.iloc[3], 3, 2) == e.coverage_ok(swap.iloc[3], 3, 2)

# Empty scoring periods must report missing metrics and fail their sample rules.
empty = e.opportunities(r).iloc[:0]
for stage in ("diagnostics", "selection", "validation", "test"):
    empty_summary, empty_rows = e.evaluate(empty, (10, 5), stage)
    assert empty_rows.empty and empty_rows.coverage_ok.dtype == bool
    assert empty_summary["matches"] == 0 and empty_summary["accepted"] == 0
    assert empty_summary["actual_date_range"] is None
    assert empty_summary["paired_improvement"] is None
    assert not e.qualifies(empty_summary)
    assert e.select_candidate([empty_summary]) is None
    if stage in ("validation", "test"):
        assert not e.stage_rules(empty_summary, stage)["passed"]
        assert not e.stage_rules(empty_summary, stage)["checks"]["sample"]

# Rejected winners forfeit profit; rejected losers avoid losses on the full baseline denominator.
rows = e.gate_rows(e.opportunities(r), (10, 5), "selection")
assert rows.bet_opportunity.all()
assert rows.iloc[0].r == 1.5 and rows.iloc[0].d == -1.5
assert rows.iloc[1].r == -1 and rows.iloc[1].d == 1
assert rows.g_r.eq(0).all()
all_pass = e.gate_rows(e.opportunities(r), (0, 0), "diagnostics")
assert all_pass.coverage_ok.all() and all_pass.d.eq(0).all()
np.testing.assert_array_equal(all_pass.g_r, all_pass.r)
np.testing.assert_array_equal(rows.r + rows.d, rows.g_r)
assert e.flat_summary(rows)["paired_improvement"] == -rows.r.mean()
assert e.flat_summary(rows)["accepted_flat_roi"] is None
scored = e.forecast_scores(rows)
assert scored["all"]["v0"] == scored["all"]["gated"]
assert scored["all"]["v0"]["n"] == 4
assert scored["accepted"]["v0"] == {"n": 0, "log_loss": None, "brier": None}

invalid = r.copy()
invalid["Odd_1"] = [float("nan"), float("inf"), 1, 2.5]
invalid["Odd_2"] = [2, 2, 2, float("inf")]
assert not e.opportunities(invalid).bet_opportunity.any()
no_bet = r.copy()
no_bet["p"] = .5
no_bet[["Odd_1", "Odd_2"]] = 1.9
assert len(e.opportunities(no_bet)) == 4 and not e.opportunities(no_bet).bet_opportunity.any()

# Gate's second stake must use its own $1,000, not v0's depleted $950.
w = r.iloc[:2].copy()
w["p"] = .6
w["baseline_p"] = .6
w["Odd_1"], w["Odd_2"] = 2., 1.5
w["Winner"], w["p1_won"] = ["B", "A"], [False, True]
w["min_total_matches"], w["min_surface_matches"] = [0, 20], [0, 10]
w = e.gate_rows(e.opportunities(w), (10, 5), "selection")
assert e.wallet_run(w, False)["final_bankroll"] == 997.5
assert e.wallet_run(w, True)["final_bankroll"] == 1050
assert e.wallet_run(w, True)["staked"] == 50
assert len(w[w.bet_opportunity]) == 2

# An exhausted wallet still returns zero-stake picks, but the flat sample remains complete.
losses = pd.concat([w.iloc[:1]] * 300, ignore_index=True)
wallet = e.wallet_run(losses, False)
assert wallet["zero_stake_bets"] > 0 and wallet["bets"] == 300
assert e.flat_summary(losses)["baseline_opportunities"] == 300

# Whole tournament-year clusters: all identical returns give an exact point interval.
c = pd.concat([rows.iloc[:1]] * 6, ignore_index=True)
c["d"] = .25
c["date"] = pd.to_datetime(["2020-01-01"] * 3 + ["2021-01-01"] * 3)
assert e.cluster_ci(c) == [.25, .25]
# One cluster contributes three zeros and the other one unit: pooled point is 1/4.
c = c.iloc[:4].copy()
c["date"] = pd.to_datetime(["2020-01-01"] * 3 + ["2021-01-01"])
c["d"] = [0., 0., 0., 1.]
assert e.flat_summary(c)["paired_improvement"] == .25
assert e.cluster_ci(c) == [0., 1.]
# Seed 15 samples the later-year cluster twice; grouping only by name would return 1/4.
assert e.cluster_ci(c, reps=1) == [1., 1.]
assert e.cluster_ci(c) == e.cluster_ci(c)
assert e.cluster_ci(c.iloc[:0]) is None

candidates = [candidate(t) for t in reversed(e.THRESHOLDS)]
assert e.select_candidate(candidates)["threshold"] == [10, 5]
candidates[0]["paired_improvement"] += 5e-13
assert e.select_candidate(candidates)["threshold"] == [10, 5]
candidates[0]["paired_improvement"] += 2e-12
assert e.select_candidate(candidates)["threshold"] == [40, 10]
assert e.selection_passes(candidate((10, 5)))
assert not e.selection_passes(candidate((10, 5), 0))
assert not e.selection_passes({**candidate((10, 5)), "accepted_flat_roi": -.1})
bad_best = {**candidate((40, 10), .2), "accepted_flat_roi": -.1}
assert not e.selection_passes(e.select_candidate([candidate((10, 5)), bad_best]))
assert e.select_candidate([{**candidate((10, 5)), "accepted": 499}]) is None
assert e.select_candidate([{**candidate((10, 5)), "retention": .49}]) is None

summary = {**candidate((10, 5)), "paired_ci95": [.01, .2],
           "per_year": {str(y): {"paired_improvement": .1 if y < 2022 else -.1} for y in (2020, 2021, 2022)},
           "wallets": {"v0": {"final_bankroll": 900, "max_drawdown": .5},
                       "gated": {"final_bankroll": 1000, "max_drawdown": .4}}}
assert e.stage_rules(summary, "validation")["passed"]
assert not e.stage_rules({**summary, "paired_ci95": [0, .2]}, "validation")["passed"]
assert not e.stage_rules({**summary, "accepted": 499}, "validation")["passed"]
assert e.stage_rules({**summary, "paired_improvement": 0, "accepted_flat_roi": 0}, "test")["passed"]
assert not e.stage_rules({**summary, "paired_improvement": -.01}, "test")["passed"]

with TemporaryDirectory() as directory:
    root = Path(directory)
    out, bets = root / "result.json", root / "bets.csv"
    registry, log = root / "registry.json", root / "LOG.md"
    hashes = {"test_fixture": "synthetic"}
    result = e.reserve_default(out, bets, hashes)
    fails(lambda: e.reserve_default(out, bets, hashes), FileExistsError)
    fails(lambda: e.start_test(out, hashes, registry, log))
    result.update(status="awaiting_test", selected=[10, 5], selection=[candidate(t) for t in e.THRESHOLDS],
                  validation={**summary, "threshold": [10, 5], "passed": True})
    result["frozen_sha256"] = e.frozen_hash(result)
    e.write_json(out, result)
    e.write_json(registry, {"test_looks_used": 5, "experiments": [{"id": "E015", "test_look": False}]})
    log.write_text("**Test-set looks used: 5**\n\n## E015 · Test\n- **Test-set look:** no.\n\n## E014 · Previous\n")
    fails(lambda: e.start_test(out, {"changed": True}, registry, log))
    modified = deepcopy(result)
    modified["selected"] = [40, 10]
    e.write_json(out, modified)
    fails(lambda: e.start_test(out, hashes, registry, log))
    e.write_json(out, result)
    previous_log = log.read_text()
    log.write_text(previous_log.replace("look:** no", "look:** yes"))
    fails(lambda: e.start_test(out, hashes, registry, log))
    log.write_text(previous_log)
    started = e.start_test(out, hashes, registry, log)
    assert started["status"] == "test_started" and started["test_looks_used"] == 1
    assert json.loads(registry.read_text())["test_looks_used"] == 6
    assert "**Test-set looks used: 6**" in log.read_text()
    assert log.read_text().count("E015 test-started") == 1
    fails(lambda: e.start_test(out, hashes, registry, log))
    assert json.loads(registry.read_text())["test_looks_used"] == 6
    # Registry alone blocks reuse, even if someone restores the old result.
    e.write_json(out, result)
    fails(lambda: e.start_test(out, hashes, registry, log))

# Default CLI path filters test years before replay and stops before validation on selection failure.
with TemporaryDirectory() as directory:
    root = Path(directory)
    extra = data.iloc[-1:].copy()
    extra["date"] = pd.Timestamp("2026-10-06")
    synthetic = pd.concat([data, extra], ignore_index=True)
    observed = []
    def replay_checked(frame):
        observed.append(frame.date.max())
        assert frame.date.max() <= pd.Timestamp("2022-12-31")
        return e.replay_original(frame)
    with patch.object(e, "OUT", root / "result.json"), patch.object(e, "BETS", root / "bets.csv"), \
         patch.object(e, "input_hashes", return_value={"synthetic": "1"}), \
         patch.object(e.bt, "load_atp", return_value=synthetic), \
         patch.object(e, "replay_original", e.replay, create=True), patch.object(e, "replay", replay_checked), \
         redirect_stdout(io.StringIO()):
        e.run()
        frozen = json.loads((root / "result.json").read_text())
        assert frozen["validation"] is None and not frozen["selection_passed"]
        assert len(frozen["selection"]) == 6 and len(frozen["diagnostics"]) == 6
        artifact = pd.read_csv(root / "bets.csv")
        assert artifact.shape[0] == 3 and artifact.columns.tolist() == e.CSV_COLUMNS
        one_test = e.gate_rows(e.opportunities(r.iloc[-1:].copy()), (10, 5), "test")
        one_test.reindex(columns=e.CSV_COLUMNS).to_csv(root / "bets.csv", mode="a", header=False, index=False)
        appended = pd.read_csv(root / "bets.csv")
        assert len(appended) == 4 and appended.iloc[-1]["stage"] == "test"
        assert pd.isna(appended.iloc[-1]["coverage_10_5"])
        assert frozen["selection"][0]["actual_date_range"] == ["2017-01-01", "2017-01-01"]
        fails(e.run, FileExistsError if not (root / "bets.csv").exists() else ValueError)
    assert len(observed) == 1

print("E015 synthetic checks passed; no historical outcomes loaded")
