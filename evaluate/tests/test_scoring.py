from __future__ import annotations

from evaluate.runners.scoring import score_answer


def test_scoring_must_not_fail():
    expected = {
        "behavior": {"should_answer": True, "should_ask_clarifying": False, "should_refuse_hallucination": True},
        "must_not_include": [r"Điều\s+9999"],
    }
    r = score_answer("Theo Điều 9999 của luật X...", expected)
    assert r.passed is False
    assert r.score == 0.0


def test_scoring_basis():
    expected = {"behavior": {"should_answer": True, "should_ask_clarifying": False, "should_refuse_hallucination": True}}
    r = score_answer("Theo Điều 5 Khoản 1 Luật Doanh nghiệp, ...", expected)
    assert r.score >= 7.0


def test_scoring_should_ask():
    expected = {"behavior": {"should_answer": True, "should_ask_clarifying": True, "should_refuse_hallucination": True}}
    r = score_answer("Bạn cho mình biết loại hình doanh nghiệp là gì?", expected)
    assert r.score >= 7.0
