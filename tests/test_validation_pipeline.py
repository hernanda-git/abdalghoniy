from decimal import Decimal

from abdalghoniy.validation import evaluate_replay


def test_validation_pipeline_fails_honestly_on_zero_trades():
    result = evaluate_replay([], sample_count=20)
    assert result["status"] == "insufficient_evidence"
    assert result["trade_count"] == 0
    assert result["purged_cv"]["status"] == "not_passed"
    assert result["random_control"]["status"] == "not_passed"


def test_validation_pipeline_reports_positive_lower_bound_only_with_evidence():
    result = evaluate_replay([Decimal("1"), Decimal("2"), Decimal("-0.5"), Decimal("1")], sample_count=20)
    assert result["trade_count"] == 4
    assert "walk_forward" in result
    assert result["status"] in {"insufficient_evidence", "research_only"}
