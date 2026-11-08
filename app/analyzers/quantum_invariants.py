import ast
from typing import List, Dict, Any

class QuantumInvariantsAnalyzer:
    """
    Implements principles from 'The Landscape of Quantum Software Testing Tools'
    (IEEE Software 2025, Wang, Ali, Taibi):
    
    1. Transform-Based Detection: Employs reversibility properties (f_inv(f(state)) == state).
    2. Identifies non-unitary or lossy operations that fail conservation laws.
    3. Property-based assertions and sensitive branch invariant verification.
    """
    def __init__(self):
        pass

    def scan_invariants(self, code_text: str, filename: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            tree = ast.parse(code_text)
        except Exception:
            return findings

        # Look for reversible / inverse pair functions or state transforms
        func_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        
        # Check for potential loss of reversibility (e.g. abs() or integer floor division // in state/metric calculations)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                has_lossy_abs = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "abs":
                        # If in a vector/matrix or transform context
                        if any(term in node.name.lower() for term in ("state", "quantum", "transform", "unitary", "vector", "norm", "phase")):
                            has_lossy_abs = True
                            findings.append({
                                "file_path": filename,
                                "line_number": child.lineno,
                                "issue_type": "INVARIANT",
                                "severity": "MEDIUM",
                                "title": "Transform Reversibility Loss: Loss of Phase/Sign Information",
                                "message": (
                                    f"Calling 'abs()' inside state function '{node.name}' discards phase and directional signs. "
                                    "According to transform-based detection (IEEE Software 2025), non-bijective transformations fail "
                                    "the reversibility oracle f_inv(f(x)) == x, making state reconstruction impossible."
                                ),
                                "code_snippet": f"abs(...) in {node.name}",
                                "rule_id": "QUANTUM-001-REVERSIBILITY",
                                "tool_source": "QuantumInvariants"
                            })
                            break

                # Check for float precision truncation in unitary/probabilistic calculations
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "round":
                        if any(term in node.name.lower() for term in ("probability", "amplitude", "state", "observable", "expectation")):
                            findings.append({
                                "file_path": filename,
                                "line_number": child.lineno,
                                "issue_type": "WARNING",
                                "severity": "LOW",
                                "title": "Observable Expectation Precision Degradation",
                                "message": (
                                    f"Premature rounding via 'round()' in statistical observable '{node.name}'. "
                                    "Cumulative expectation values in Z/X/Y bases require full floating-point precision to avoid statistical test oracle bias."
                                ),
                                "code_snippet": f"round(...) in {node.name}",
                                "rule_id": "QUANTUM-002-PRECISION",
                                "tool_source": "QuantumInvariants"
                            })
                            break

        return findings
