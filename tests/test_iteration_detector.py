import pytest
from app.analyzers.iteration_detector import analyze_code_iterations

def test_detect_nested_loops():
    code = """
def nested_scan(matrix_a, matrix_b):
    matches = []
    for row in matrix_a:
        for item in row:
            for candidate in matrix_b:
                if item == candidate:
                    matches.append(item)
    return matches
"""
    findings = analyze_code_iterations(code, "nested.py")
    nested_issues = [f for f in findings if "Nested Loop" in f["title"]]
    assert len(nested_issues) >= 1
    assert nested_issues[0]["severity"] == "HIGH"
    assert "O(N^" in nested_issues[0]["title"]

def test_detect_unmemoized_recursion():
    code = """
def compute_fibonacci(n):
    if n <= 1:
        return n
    return compute_fibonacci(n - 1) + compute_fibonacci(n - 2)
"""
    findings = analyze_code_iterations(code, "fib.py")
    rec_issues = [f for f in findings if "Exponential Recursive" in f["title"]]
    assert len(rec_issues) == 1
    assert rec_issues[0]["severity"] == "HIGH"

def test_detect_range_len_antipattern():
    code = """
def process_items(arr):
    for i in range(len(arr)):
        print(arr[i])
"""
    findings = analyze_code_iterations(code, "loop.py")
    range_issues = [f for f in findings if "range(len" in f["title"]]
    assert len(range_issues) == 1

def test_detect_unbounded_while():
    code = """
def poll_queue():
    while True:
        task = get_task()
        process(task)
"""
    findings = analyze_code_iterations(code, "poll.py")
    busy_issues = [f for f in findings if "Busy-Wait" in f["title"]]
    assert len(busy_issues) == 1
    assert busy_issues[0]["severity"] == "CRITICAL"
