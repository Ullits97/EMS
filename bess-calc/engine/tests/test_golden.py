"""Golden regression: 3 canonical cases with committed expected outputs
(±0.5%, SPEC §11). Re-baseline with `python engine/tests/update_goldens.py`
after intentional engine or reference-data changes (SPEC §12 M3).
"""

import json
from pathlib import Path

import pytest

from besscalc.economics import run_simulation

from golden_cases import GOLDEN_CASES, result_fingerprint

GOLDEN_PATH = Path(__file__).parent / "golden_expected.json"
RTOL = 0.005


@pytest.fixture(scope="module")
def expected() -> dict:
    if not GOLDEN_PATH.exists():
        pytest.fail("golden_expected.json missing — run engine/tests/update_goldens.py")
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_name", list(GOLDEN_CASES))
def test_golden_case(case_name, expected):
    request = GOLDEN_CASES[case_name]()
    result = run_simulation(request)
    actual = result_fingerprint(result)
    assert case_name in expected, f"no committed baseline for {case_name}"
    for key, expected_value in expected[case_name].items():
        actual_value = actual[key]
        if expected_value == 0:
            assert abs(actual_value) < 1.0, f"{case_name}.{key}"
        else:
            assert actual_value == pytest.approx(expected_value, rel=RTOL), f"{case_name}.{key}"
