from __future__ import annotations

from pathlib import Path

from evaluate.runners.loaders import load_golden_cases


def test_load_core():
    cases = load_golden_cases(Path("evaluate/golden_sets/vn_business_core.yaml"))
    assert len(cases) >= 10


def test_load_edge():
    cases = load_golden_cases(Path("evaluate/golden_sets/vn_business_edge.yaml"))
    assert len(cases) >= 10


def test_load_stress():
    cases = load_golden_cases(Path("evaluate/golden_sets/vn_business_stress.yaml"))
    assert len(cases) >= 1
