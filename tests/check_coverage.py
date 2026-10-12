"""Run with: uv run python tests/check_coverage.py (no network or live state)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategies import coverage_ok

assert coverage_ok({"min_total_matches": 20, "min_surface_matches": 10}, 20, 10)
assert coverage_ok({"min_total_matches": "20", "min_surface_matches": 10.0}, 20, 10)
assert not coverage_ok({"min_total_matches": 19, "min_surface_matches": 10}, 20, 10)
assert not coverage_ok({"min_total_matches": 20, "min_surface_matches": 9}, 20, 10)
assert not coverage_ok({}, 20, 10)
for bad in (None, "bad", float("nan"), float("inf"), float("-inf"), -1, 2.5):
    assert not coverage_ok({"min_total_matches": bad, "min_surface_matches": 10}, 20, 10)
    assert not coverage_ok({"min_total_matches": 20, "min_surface_matches": bad}, 20, 10)
print("coverage checks passed")
