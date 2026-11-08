import ast
from pathlib import Path
from typing import List, Dict, Any, Set

class IterationDetector(ast.NodeVisitor):
    """
    AST-based static analyzer to detect unnecessary iterations, redundant loops,
    quadratic complexity anti-patterns, and computational cost inefficiencies.
    """
    def __init__(self, filename: str, code_lines: List[str]):
        self.filename = filename
        self.code_lines = code_lines
        self.findings: List[Dict[str, Any]] = []
        self.loop_stack: List[ast.AST] = []
        self.current_function: Optional[str] = None
        self.loop_variables: Set[str] = set()

    def get_line_code(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.code_lines):
            return self.code_lines[lineno - 1].strip()
        return ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_func = self.current_function
        self.current_function = node.name
        
        # Check for unmemoized recursive call
        recursive_calls = 0
        has_lru_cache = any(
            (isinstance(d, ast.Name) and "cache" in d.id.lower()) or
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and "cache" in d.func.id.lower())
            for d in node.decorator_list
        )
        
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call) and isinstance(subnode.func, ast.Name) and subnode.func.id == node.name:
                recursive_calls += 1
                
        if recursive_calls >= 2 and not has_lru_cache:
            self.findings.append({
                "file_path": self.filename,
                "line_number": node.lineno,
                "issue_type": "ITERATION",
                "severity": "HIGH",
                "title": f"Exponential Recursive Iterations: '{node.name}' (O(2^N))",
                "message": (
                    f"Function '{node.name}' has multiple recursive self-calls ({recursive_calls}) without memoization, "
                    "causing exponential iteration overhead and redundant subproblem computations. Use @functools.lru_cache."
                ),
                "code_snippet": self.get_line_code(node.lineno),
                "rule_id": "ITER-001-RECURSION",
                "tool_source": "ASTIteration"
            })
            
        self.generic_visit(node)
        self.current_function = prev_func

    def visit_For(self, node: ast.For):
        # Track loop variable names
        var_names = set()
        if isinstance(node.target, ast.Name):
            var_names.add(node.target.id)
        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    var_names.add(elt.id)
                    
        # Check for range(len(...)) anti-pattern
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
            if node.iter.args and isinstance(node.iter.args[0], ast.Call):
                inner_call = node.iter.args[0]
                if isinstance(inner_call.func, ast.Name) and inner_call.func.id == "len":
                    self.findings.append({
                        "file_path": self.filename,
                        "line_number": node.lineno,
                        "issue_type": "ITERATION",
                        "severity": "LOW",
                        "title": "Unnecessary Index-Based Iteration: 'range(len(...))'",
                        "message": (
                            "Iterating via 'range(len(collection))' causes needless indexing overhead. "
                            "Iterate directly over items or use 'enumerate()' for cleaner, faster execution."
                        ),
                        "code_snippet": self.get_line_code(node.lineno),
                        "rule_id": "ITER-002-RANGE-LEN",
                        "tool_source": "ASTIteration"
                    })

        # Check for nested loops (O(N^2) or worse)
        if len(self.loop_stack) >= 1:
            outer_loop = self.loop_stack[-1]
            self.findings.append({
                "file_path": self.filename,
                "line_number": node.lineno,
                "issue_type": "ITERATION",
                "severity": "HIGH",
                "title": f"Nested Loop Iteration Bottleneck: O(N^{len(self.loop_stack) + 1}) Complexity",
                "message": (
                    f"Nested loop at line {node.lineno} inside outer loop at line {outer_loop.lineno} "
                    "multiplies computational iterations exponentially. Check if inner lookups can be replaced with hash sets or vectorized."
                ),
                "code_snippet": self.get_line_code(node.lineno),
                "rule_id": "ITER-003-NESTED-LOOP",
                "tool_source": "ASTIteration"
            })

        # Check for linear search / membership check inside loop (x in list_b)
        for child in ast.walk(node):
            if isinstance(child, ast.Compare):
                for op in child.ops:
                    if isinstance(op, (ast.In, ast.NotIn)):
                        # If searching in a Name or Call that is likely a list
                        self.findings.append({
                            "file_path": self.filename,
                            "line_number": child.lineno,
                            "issue_type": "ITERATION",
                            "severity": "MEDIUM",
                            "title": "Linear Membership Search Inside Loop (O(N*M))",
                            "message": (
                                f"Evaluating 'in' membership check inside loop at line {child.lineno}. "
                                "If the container is a list/tuple, this incurs an O(M) linear scan on every iteration. Pre-converting to a set() provides O(1) lookups."
                            ),
                            "code_snippet": self.get_line_code(child.lineno),
                            "rule_id": "ITER-004-MEMBERSHIP-SCAN",
                            "tool_source": "ASTIteration"
                        })
                        break # Only report once per compare

        # Check for string concatenation in loop (s += chunk)
        for child in ast.walk(node):
            if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                # String concatenation anti-pattern
                line_text = self.get_line_code(child.lineno)
                if "+=" in line_text and ("str" in line_text or "text" in line_text or "msg" in line_text or '"' in line_text or "'" in line_text):
                    self.findings.append({
                        "file_path": self.filename,
                        "line_number": child.lineno,
                        "issue_type": "ITERATION",
                        "severity": "MEDIUM",
                        "title": "Repeated String Concatenation in Loop (O(N^2) Allocations)",
                        "message": (
                            "Using '+=' on strings inside a loop forces Python to allocate and copy a new string on every iteration. "
                            "Accumulate chunks in a list and use ''.join() for O(N) performance."
                        ),
                        "code_snippet": line_text,
                        "rule_id": "ITER-005-STRING-CONCAT",
                        "tool_source": "ASTIteration"
                    })

        self.loop_stack.append(node)
        self.generic_visit(node)
        self.loop_stack.pop()

    def visit_While(self, node: ast.While):
        # Check for while True without backoff or break
        is_infinite = (isinstance(node.test, ast.Constant) and node.test.value is True) or \
                      (isinstance(node.test, ast.Name) and node.test.id == "True")
        
        has_sleep_or_break = False
        for child in ast.walk(node):
            if isinstance(child, ast.Break):
                has_sleep_or_break = True
            elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "sleep":
                has_sleep_or_break = True

        if is_infinite and not has_sleep_or_break:
            self.findings.append({
                "file_path": self.filename,
                "line_number": node.lineno,
                "issue_type": "ITERATION",
                "severity": "CRITICAL",
                "title": "Unbounded Busy-Wait Loop (Risk of CPU Spike & Timeout)",
                "message": (
                    "Unbounded 'while True' loop detected without explicit break or sleep backoff. "
                    "In serverless environments (AWS Lambda / Cloud Functions), this will peg CPU to 100% until function timeout, causing max billing penalties (IEEE Access 2024)."
                ),
                "code_snippet": self.get_line_code(node.lineno),
                "rule_id": "ITER-006-BUSY-WAIT",
                "tool_source": "ASTIteration"
            })
            
        self.loop_stack.append(node)
        self.generic_visit(node)
        self.loop_stack.pop()


def analyze_code_iterations(code_text: str, filename: str = "source.py") -> List[Dict[str, Any]]:
    lines = code_text.splitlines()
    try:
        tree = ast.parse(code_text)
        detector = IterationDetector(filename, lines)
        detector.visit(tree)
        return detector.findings
    except SyntaxError:
        return []
    except Exception:
        return []

def scan_directory_iterations(target_dir: Path) -> List[Dict[str, Any]]:
    all_findings = []
    py_files = list(target_dir.glob("**/*.py")) if target_dir.is_dir() else ([target_dir] if target_dir.suffix == ".py" else [])
    for pfile in py_files:
        try:
            content = pfile.read_text(encoding="utf-8", errors="ignore")
            findings = analyze_code_iterations(content, pfile.name)
            all_findings.extend(findings)
        except Exception:
            continue
    return all_findings
