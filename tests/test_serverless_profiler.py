import pytest
from app.analyzers.serverless_profiler import ServerlessProfiler

def test_serverless_handler_detection():
    profiler = ServerlessProfiler()
    code = """
def lambda_handler(event, context):
    import json
    return {'statusCode': 200}
"""
    result = profiler.analyze_serverless_file(code, "handler.py")
    assert result["is_serverless"] is True
    assert result["cold_start_score"] < 100
    assert any("In-Handler Import" in f["title"] for f in result["findings"])
    assert result["test_ratio"]["unit"] >= 70

def test_serverless_billing_reduction():
    profiler = ServerlessProfiler()
    savings = profiler.estimate_billing_reduction(speedup_factor=5.0, iterations_reduced=1000)
    assert savings["duration_reduction_pct"] > 0
    assert savings["estimated_monthly_savings_usd"] > 0
    assert savings["optimized_duration_ms"] < savings["baseline_duration_ms"]
