import runpy
from pathlib import Path


MODULE = runpy.run_path(str(Path("scripts") / "analyze_focus_samples.py"))
best_threshold = MODULE["best_threshold"]


def test_focus_threshold_separates_good_and_bad_samples():
    rows = [
        {"label": "bad", "laplacian": "10"},
        {"label": "bad", "laplacian": "20"},
        {"label": "good", "laplacian": "80"},
        {"label": "good", "laplacian": "100"},
    ]
    result = best_threshold(rows, "laplacian")

    assert 20 < result.threshold < 80
    assert result.false_good == 0
    assert result.false_bad == 0

