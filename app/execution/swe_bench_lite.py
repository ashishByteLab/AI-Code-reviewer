import time
from typing import Dict, Any, List
from app.execution.sandbox import execute_python_code_safe

SWE_BENCH_LITE_INSTANCES = [
    {
        "task_id": "SWE-LITE-001-LOOP-OPT",
        "title": "Quadratic Substring Deduplication Inefficiency",
        "problem_statement": (
            "Function 'find_duplicates' exhibits O(N*M) nested loop latency when scanning "
            "large lists of transaction identifiers, resulting in severe response delays in serverless functions. "
            "Refactor to O(N + M) using hash set lookups while maintaining identical duplicate discovery."
        ),
        "test_suite": """
def test_evaluation():
    list_a = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100] * 50
    list_b = [20, 40, 60, 80, 100, 120, 140] * 50
    
    result = find_duplicates(list_a, list_b)
    # Check expected duplicates exist
    expected = {20, 40, 60, 80, 100}
    assert set(result) == expected, f"Expected {expected}, got {set(result)}"
    print("ALL SWE-BENCH ASSERTIONS PASSED!")

test_evaluation()
"""
    },
    {
        "task_id": "SWE-LITE-002-METAMORPHIC-SYMMETRY",
        "title": "Order-Dependent Checksum Bug (COMER Violation)",
        "problem_statement": (
            "The function 'compute_feature_signature' violates the Metamorphic Relation of Permutation & Reverse. "
            "Inputs with identical multiset contents produce different checksums due to index-coupled multiplication. "
            "Fix the calculation so multiset equivalence produces symmetric output."
        ),
        "test_suite": """
def test_evaluation():
    data1 = [5, 12, 19, 23, 42]
    data2 = [42, 23, 19, 12, 5] # Reversal
    data3 = [19, 5, 42, 12, 23] # Permutation
    
    sig1 = compute_feature_signature(data1)
    sig2 = compute_feature_signature(data2)
    sig3 = compute_feature_signature(data3)
    
    assert sig1 == sig2, f"Reverse invariance failed: {sig1} != {sig2}"
    assert sig1 == sig3, f"Permutation invariance failed: {sig1} != {sig3}"
    print("ALL SWE-BENCH ASSERTIONS PASSED!")

test_evaluation()
"""
    },
    {
        "task_id": "SWE-LITE-003-SERVERLESS-HANDLER",
        "title": "Cold-Start Handler Optimization (IEEE Access 2024)",
        "problem_statement": (
            "The serverless handler re-computes an expensive cumulative frequency table on every event invocation. "
            "Refactor the code to pre-compute or cache table data, ensuring handler latency is under 10ms."
        ),
        "test_suite": """
def test_evaluation():
    event = {"items": [1, 2, 3, 4, 5, 2, 3, 1, 4]}
    response = process_event(event)
    assert response["status"] == "SUCCESS"
    assert response["total"] == 9
    assert response["most_frequent"] in (1, 2, 3, 4)
    print("ALL SWE-BENCH ASSERTIONS PASSED!")

test_evaluation()
"""
    }
]

class SweBenchLiteEvaluator:
    """
    Harness for evaluating code patches against SWE-bench Lite problem instances.
    """
    def __init__(self):
        self.instances = {item["task_id"]: item for item in SWE_BENCH_LITE_INSTANCES}

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        return list(self.instances.values())

    def evaluate_patch(self, task_id: str, candidate_code: str) -> Dict[str, Any]:
        task = self.instances.get(task_id)
        if not task:
            # Fallback for dynamic user-defined task
            task = SWE_BENCH_LITE_INSTANCES[0]

        combined_script = f"""
# CANDIDATE CODE UNDER EVALUATION
{candidate_code}

# SWE-BENCH LITE REGRESSION TEST SUITE
{task['test_suite']}
"""
        start = time.time()
        exec_res = execute_python_code_safe(combined_script, timeout=6)
        elapsed_ms = round((time.time() - start) * 1000, 2)
        
        passed = (
            exec_res.get("returncode") == 0 and 
            "ALL SWE-BENCH ASSERTIONS PASSED!" in exec_res.get("stdout", "")
        )
        
        status = "PASSED" if passed else "FAILED"
        log = exec_res.get("stdout", "")
        if not passed:
            log += "\n" + exec_res.get("stderr", "")

        return {
            "task_id": task_id,
            "title": task["title"],
            "status": status,
            "passed": passed,
            "execution_driver": exec_res.get("driver", "Sandbox"),
            "duration_ms": elapsed_ms,
            "execution_log": log.strip()
        }
