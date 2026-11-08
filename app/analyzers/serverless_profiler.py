import ast
from pathlib import Path
from typing import List, Dict, Any

class ServerlessProfiler:
    """
    Implements principles from 'The Impact of Software Testing on Serverless Applications'
    (IEEE Access 2024, De Silva & Hewawasam):
    
    1. Identifies serverless FaaS endpoints and event-driven patterns.
    2. Detects Cold Start latency hotspots (e.g., in-handler imports, un-reused DB/API clients).
    3. Calculates execution duration impact on cloud billing (GB-seconds / pay-per-use).
    4. Advises on the optimal Shift-Left Testing Ratio (Unit vs Integration vs E2E).
    """
    def __init__(self):
        pass

    def analyze_serverless_file(self, code_text: str, filename: str) -> Dict[str, Any]:
        findings = []
        is_serverless = False
        cold_start_score = 100 # 100 is best, decreases with bad patterns
        
        try:
            tree = ast.parse(code_text)
        except Exception:
            return {"is_serverless": False, "findings": [], "cold_start_score": 100, "test_ratio": {"unit": 80, "integration": 15, "e2e": 5}}

        handler_names = set()
        for node in ast.walk(tree):
            # Check for Lambda handler or cloud function signature
            if isinstance(node, ast.FunctionDef):
                params = [a.arg for a in node.args.args]
                if ("event" in params and "context" in params) or "handler" in node.name.lower() or "lambda" in node.name.lower():
                    is_serverless = True
                    handler_names.add(node.name)
            
            # Check for FastAPI / Flask serverless route decorators
            if isinstance(node, ast.FunctionDef) and node.decorator_list:
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if dec.func.attr in ("get", "post", "put", "delete", "patch"):
                            is_serverless = True

        # Check for heavy imports or client initialization inside function bodies
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in node.body:
                    # In-handler import: causes repeated import parsing on cold starts
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        cold_start_score -= 20
                        imported = [alias.name for alias in child.names]
                        findings.append({
                            "file_path": filename,
                            "line_number": child.lineno,
                            "issue_type": "WARNING",
                            "severity": "HIGH",
                            "title": "Serverless Cold-Start: Heavy In-Handler Import",
                            "message": (
                                f"Importing '{', '.join(imported)}' inside function '{node.name}' slows container initialization. "
                                "Move imports to global scope so container warming caches them across invocations (IEEE Access 2024)."
                            ),
                            "code_snippet": f"import {', '.join(imported)}",
                            "rule_id": "SRV-001-COLD-START-IMPORT",
                            "tool_source": "ServerlessProfiler"
                        })
                    
                    # Repeated client initialization inside handler (e.g. boto3.client, sqlite3.connect)
                    if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
                        call_func = child.value.func
                        call_name = ""
                        if isinstance(call_func, ast.Name):
                            call_name = call_func.id
                        elif isinstance(call_func, ast.Attribute):
                            call_name = call_func.attr
                            
                        if call_name in ("client", "resource", "connect", "Session"):
                            cold_start_score -= 15
                            findings.append({
                                "file_path": filename,
                                "line_number": child.lineno,
                                "issue_type": "WARNING",
                                "severity": "MEDIUM",
                                "title": "Serverless Connection Overhead Inside Handler",
                                "message": (
                                    f"Instantiating database or cloud client '{call_name}()' inside '{node.name}' incurs connection handshake delays on every execution. "
                                    "Initialize clients in global scope to reuse HTTP connection pools across warm invocations."
                                ),
                                "code_snippet": f"client = ...{call_name}(...)",
                                "rule_id": "SRV-002-CONNECTION-POOLING",
                                "tool_source": "ServerlessProfiler"
                            })

        # Calculate recommended testing ratio (De Silva & Hewawasam 2024 findings)
        if is_serverless:
            # Emphasize shift-left: heavy unit tests on business logic, limited slow E2E
            test_ratio = {"unit": 75, "integration": 20, "e2e": 5}
        else:
            test_ratio = {"unit": 70, "integration": 20, "e2e": 10}

        return {
            "is_serverless": is_serverless,
            "cold_start_score": max(20, cold_start_score),
            "findings": findings,
            "test_ratio": test_ratio
        }

    def estimate_billing_reduction(self, speedup_factor: float, iterations_reduced: int) -> Dict[str, Any]:
        """
        Estimates monthly serverless cost reduction on 1,000,000 invocations 
        with 512MB RAM and $0.0000166667 per GB-second.
        """
        baseline_duration_ms = 450.0 # Average function duration
        optimized_duration_ms = max(50.0, baseline_duration_ms / max(1.1, speedup_factor))
        saved_ms = baseline_duration_ms - optimized_duration_ms
        
        # 1M invocations
        invocations = 1_000_000
        gb = 0.512 # 512MB
        gb_seconds_saved = (saved_ms / 1000.0) * gb * invocations
        usd_saved = gb_seconds_saved * 0.0000166667
        
        cost_reduction_pct = round(((baseline_duration_ms - optimized_duration_ms) / baseline_duration_ms) * 100, 1)

        return {
            "baseline_duration_ms": round(baseline_duration_ms, 1),
            "optimized_duration_ms": round(optimized_duration_ms, 1),
            "duration_reduction_pct": cost_reduction_pct,
            "estimated_monthly_savings_usd": round(usd_saved, 2),
            "gb_seconds_saved": round(gb_seconds_saved, 1)
        }
