import pytest
from app.execution.swe_bench_lite import SweBenchLiteEvaluator
from app.analyzers.quantum_invariants import QuantumInvariantsAnalyzer

def test_swe_bench_runner_passing():
    evaluator = SweBenchLiteEvaluator()
    correct_patch = """
def find_duplicates(list_a, list_b):
    set_b = set(list_b)
    return [x for x in list_a if x in set_b]
"""
    result = evaluator.evaluate_patch("SWE-LITE-001-LOOP-OPT", correct_patch)
    assert result["passed"] is True
    assert result["status"] == "PASSED"

def test_swe_bench_runner_failing():
    evaluator = SweBenchLiteEvaluator()
    buggy_patch = """
def find_duplicates(list_a, list_b):
    return [] # Incorrect logic
"""
    result = evaluator.evaluate_patch("SWE-LITE-001-LOOP-OPT", buggy_patch)
    assert result["passed"] is False
    assert result["status"] == "FAILED"

def test_quantum_reversibility_loss_detection():
    analyzer = QuantumInvariantsAnalyzer()
    code = """
def update_quantum_state(state_vector):
    # Using abs() causes loss of phase/signs, breaking transform reversibility
    return [abs(val) for val in state_vector]
"""
    findings = analyzer.scan_invariants(code, "quantum_state.py")
    assert len(findings) >= 1
    assert any("Reversibility" in f["title"] for f in findings)
