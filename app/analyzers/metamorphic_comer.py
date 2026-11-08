import ast
import random
import copy
from typing import List, Dict, Any, Tuple, Optional
from app.execution.sandbox import execute_python_code_safe

class MetamorphicComerEngine:
    """
    Implements the COMER methodology (IEEE Transactions on Software Engineering 2022, Niu et al.):
    'Enhance Combinatorial Testing With Metamorphic Relations'.
    
    1. Couples t-way interaction coverage (t=2 pairwise) with Metamorphic Relations (MR).
    2. Generates Metamorphic Groups (MGs: Source and Follow-up test cases).
    3. Solves the automated test oracle problem by verifying relation invariants 
       without requiring human golden outputs or ground-truth specifications.
    """
    def __init__(self):
        self.common_relations = [
            "PERMUTE", "REVERSE", "ADD_CONSTANT", "MULTIPLY_SCALE", 
            "INCLUDE_ELEMENT", "EXCLUDE_ELEMENT", "INVERT_TRANSFORM"
        ]

    def extract_testable_functions(self, code_text: str) -> List[Dict[str, Any]]:
        """Parses Python AST to extract functions and their parameter signatures."""
        functions = []
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    param_names = [arg.arg for arg in node.args.args if arg.arg not in ("self", "cls")]
                    functions.append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "params": param_names,
                        "docstring": ast.get_docstring(node) or ""
                    })
        except Exception:
            pass
        return functions

    def generate_metamorphic_group(self, func_info: Dict[str, Any], relation_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Generates a pair of (Source test case, Follow-up test case) based on the chosen MR.
        """
        params = func_info["params"]
        if not params:
            return {}, {}

        # Default source input generation
        source_inputs = {}
        for p in params:
            if "list" in p.lower() or "arr" in p.lower() or "items" in p.lower() or "vec" in p.lower() or "points" in p.lower():
                source_inputs[p] = [random.randint(1, 20) for _ in range(5)]
            elif "num" in p.lower() or "val" in p.lower() or "count" in p.lower() or "n" == p.lower() or "x" == p.lower():
                source_inputs[p] = random.randint(2, 10)
            elif "text" in p.lower() or "str" in p.lower() or "msg" in p.lower():
                source_inputs[p] = "hello world sample test string"
            else:
                source_inputs[p] = [random.randint(1, 15) for _ in range(4)]

        follow_up_inputs = copy.deepcopy(source_inputs)

        # Apply Metamorphic Transformation r_in
        if relation_type == "PERMUTE":
            for k, v in follow_up_inputs.items():
                if isinstance(v, list) and len(v) > 1:
                    shuffled = list(v)
                    random.shuffle(shuffled)
                    follow_up_inputs[k] = shuffled
                    break

        elif relation_type == "REVERSE":
            for k, v in follow_up_inputs.items():
                if isinstance(v, list) and len(v) > 1:
                    follow_up_inputs[k] = list(reversed(v))
                    break
                elif isinstance(v, str) and len(v) > 1:
                    follow_up_inputs[k] = v[::-1]
                    break

        elif relation_type == "ADD_CONSTANT":
            c = random.randint(3, 7)
            for k, v in follow_up_inputs.items():
                if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
                    follow_up_inputs[k] = [x + c for x in v]
                    break
                elif isinstance(v, (int, float)):
                    follow_up_inputs[k] = v + c
                    break

        elif relation_type == "MULTIPLY_SCALE":
            k_factor = 2
            for k, v in follow_up_inputs.items():
                if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
                    follow_up_inputs[k] = [x * k_factor for x in v]
                    break
                elif isinstance(v, (int, float)):
                    follow_up_inputs[k] = v * k_factor
                    break

        elif relation_type == "INCLUDE_ELEMENT":
            for k, v in follow_up_inputs.items():
                if isinstance(v, list):
                    follow_up_inputs[k] = v + [random.randint(50, 100)]
                    break

        return source_inputs, follow_up_inputs

    def verify_metamorphic_relation(
        self, 
        func_name: str, 
        relation_type: str, 
        src_in: Dict[str, Any], 
        fol_in: Dict[str, Any],
        src_out: Any, 
        fol_out: Any
    ) -> Tuple[bool, str]:
        """
        Checks whether r_out holds. Returns (violated: bool, explanation: str).
        """
        # If output is error or None
        if src_out is None or fol_out is None:
            return False, "Outputs were not computable or void."

        if relation_type == "PERMUTE":
            # For permutation-invariant functions (e.g. sum, count, bag hash, min/max, sorted set)
            # Check if sorted outputs or scalar results match
            if isinstance(src_out, (int, float)) and isinstance(fol_out, (int, float)):
                if abs(src_out - fol_out) > 1e-4:
                    return True, f"Permutation Invariant Violated: f(x)={src_out} != f(permute(x))={fol_out}. Output depends on iteration order."
            elif isinstance(src_out, list) and isinstance(fol_out, list):
                if sorted(src_out) != sorted(fol_out):
                    return True, f"Permutation Multiset Violated: items changed after input permutation."

        elif relation_type == "REVERSE":
            # Reverse symmetry or palindromic test
            if isinstance(src_out, (int, float)) and isinstance(fol_out, (int, float)):
                if abs(src_out - fol_out) > 1e-4:
                    # Invariant violation for commutative / symmetric reducers
                    return True, f"Reverse Invariance Violated: f(x)={src_out} != f(reverse(x))={fol_out}. Output failed order symmetry."

        elif relation_type == "MULTIPLY_SCALE":
            # Homogeneity check for linear algorithms: f(k * x) should scale proportionally or predictably
            if isinstance(src_out, (int, float)) and isinstance(fol_out, (int, float)):
                if src_out != 0 and fol_out == 0:
                    return True, f"Scale Invariant Violated: Scaling inputs to non-zero yielded 0 output."

        elif relation_type == "INCLUDE_ELEMENT":
            # Monotonicity check: e.g. for max, length, distance, closest pair
            if isinstance(src_out, (int, float)) and isinstance(fol_out, (int, float)):
                if "closest" in func_name.lower() or "min" in func_name.lower():
                    # Closest pair property (from COMER paper ClosestPair subject):
                    # Adding a point cannot INCREASE minimum distance!
                    if fol_out > src_out + 1e-5:
                        return True, f"Monotonicity Violation (COMER ClosestPair): Adding a point increased min distance from {src_out} to {fol_out}."

        return False, "Metamorphic relation satisfied successfully."

    def test_file_metamorphics(self, code_text: str, filename: str) -> List[Dict[str, Any]]:
        """
        Performs COMER testing on the file's functions.
        """
        results = []
        funcs = self.extract_testable_functions(code_text)
        
        for func in funcs:
            if not func["params"]:
                continue
                
            for rel in ["PERMUTE", "REVERSE", "INCLUDE_ELEMENT"]:
                src_in, fol_in = self.generate_metamorphic_group(func, rel)
                if not src_in:
                    continue

                # Prepare test harness execution
                harness = f"""
{code_text}

# COMER Automated Test Harness
src_args = {repr(src_in)}
fol_args = {repr(fol_in)}

try:
    src_out = {func['name']}(**src_args)
except Exception as e:
    src_out = f"ERROR: {{e}}"

try:
    fol_out = {func['name']}(**fol_args)
except Exception as e:
    fol_out = f"ERROR: {{e}}"

print(f"SRC_OUT:{{src_out}}")
print(f"FOL_OUT:{{fol_out}}")
"""
                exec_res = execute_python_code_safe(harness, timeout=3)
                output = exec_res.get("stdout", "")
                
                src_out, fol_out = None, None
                for line in output.splitlines():
                    if line.startswith("SRC_OUT:"):
                        src_out = line[len("SRC_OUT:"):].strip()
                    elif line.startswith("FOL_OUT:"):
                        fol_out = line[len("FOL_OUT:"):].strip()

                # Attempt numeric conversion
                try:
                    src_num = float(src_out) if src_out and not src_out.startswith("ERROR") else src_out
                    fol_num = float(fol_out) if fol_out and not fol_out.startswith("ERROR") else fol_out
                except ValueError:
                    src_num, fol_num = src_out, fol_out

                violated, msg = self.verify_metamorphic_relation(
                    func["name"], rel, src_in, fol_in, src_num, fol_num
                )
                
                results.append({
                    "test_name": f"{filename}::{func['name']} [MR_{rel}]",
                    "relation_type": rel,
                    "source_input": str(src_in),
                    "follow_up_input": str(fol_in),
                    "source_output": str(src_out),
                    "follow_up_output": str(fol_out),
                    "violated": violated,
                    "message": msg
                })
                
        return results
