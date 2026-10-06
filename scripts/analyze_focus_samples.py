from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Evaluation:
    threshold: float
    true_good: int
    false_good: int
    true_bad: int
    false_bad: int

    @property
    def balanced_accuracy(self) -> float:
        good_total = self.true_good + self.false_bad
        bad_total = self.true_bad + self.false_good
        sensitivity = self.true_good / good_total if good_total else 0.0
        specificity = self.true_bad / bad_total if bad_total else 0.0
        return 0.5 * (sensitivity + specificity)


def best_threshold(rows: list[dict[str, str]], column: str) -> Evaluation:
    values = sorted({float(row[column]) for row in rows})
    if not values:
        raise ValueError(f"No values found for {column}")
    candidates = [values[0] - 1e-9]
    candidates.extend((a + b) / 2 for a, b in zip(values, values[1:]))
    candidates.append(values[-1] + 1e-9)
    evaluations = []
    for threshold in candidates:
        true_good = false_good = true_bad = false_bad = 0
        for row in rows:
            expected_good = row["label"].strip().lower() == "good"
            predicted_good = float(row[column]) >= threshold
            if expected_good and predicted_good:
                true_good += 1
            elif not expected_good and predicted_good:
                false_good += 1
            elif not expected_good and not predicted_good:
                true_bad += 1
            else:
                false_bad += 1
        evaluations.append(Evaluation(threshold, true_good, false_good, true_bad, false_bad))
    # For equal balanced accuracy, prefer fewer false accepts, then the stricter threshold.
    return max(evaluations, key=lambda item: (item.balanced_accuracy, -item.false_good, item.threshold))


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest focus gates from labelled samples")
    parser.add_argument("csv", nargs="?", default="focus_samples.csv")
    args = parser.parse_args()
    path = Path(args.csv)
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or {row["label"].strip().lower() for row in rows} != {"good", "bad"}:
        raise ValueError("CSV must contain both 'good' and 'bad' labelled samples")

    print(f"Samples: {len(rows)}")
    for column in ("laplacian", "tenengrad"):
        result = best_threshold(rows, column)
        print(
            f"{column}: threshold={result.threshold:.3f}, "
            f"balanced_accuracy={result.balanced_accuracy:.3f}, "
            f"false_accept={result.false_good}, false_reject={result.false_bad}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

