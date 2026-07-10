"""Re-baseline the golden regression cases.

Usage: python engine/tests/update_goldens.py
Run only after an intentional engine or reference-data change; review the
diff of golden_expected.json before committing.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from besscalc.economics import run_simulation  # noqa: E402

from golden_cases import GOLDEN_CASES, result_fingerprint  # noqa: E402


def main() -> None:
    expected = {}
    for name, factory in GOLDEN_CASES.items():
        result = run_simulation(factory())
        expected[name] = result_fingerprint(result)
        print(f"{name}: total y1 (B, headline) = "
              f"{result.strategies['price_optimized'].year1.savings_total_dkk:.0f} DKK")
    out = Path(__file__).parent / "golden_expected.json"
    out.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
