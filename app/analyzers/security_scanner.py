import os
import json
import subprocess
import ast
from pathlib import Path
from typing import List, Dict, Any
from app.config import BASE_DIR

class SecurityScanner:
    """
    Combines Bandit (Python AST security linter) and Semgrep (Semantic grep security engine).
    """
    def __init__(self, venv_bin_dir: Path = None):
        if venv_bin_dir is None:
            self.venv_bin = BASE_DIR / ".venv" / "bin"
        else:
            self.venv_bin = venv_bin_dir
            
        self.bandit_cmd = str(self.venv_bin / "bandit") if (self.venv_bin / "bandit").exists() else "bandit"
        self.semgrep_cmd = str(self.venv_bin / "semgrep") if (self.venv_bin / "semgrep").exists() else "semgrep"

    def run_bandit(self, target_path: Path) -> List[Dict[str, Any]]:
        issues = []
        try:
            cmd = [self.bandit_cmd, "-r", str(target_path), "-f", "json", "-q"]
            env = os.environ.copy()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            
            raw_output = result.stdout.strip()
            if raw_output:
                data = json.loads(raw_output)
                for item in data.get("results", []):
                    sev = item.get("issue_severity", "MEDIUM").upper()
                    issues.append({
                        "file_path": str(Path(item.get("filename", "")).name),
                        "line_number": item.get("line_number", 1),
                        "issue_type": "SECURITY",
                        "severity": sev, # CRITICAL/HIGH/MEDIUM/LOW
                        "title": f"Bandit Security: {item.get('test_name', 'Vulnerability')} ({item.get('test_id')})",
                        "message": item.get("issue_text", ""),
                        "code_snippet": item.get("code", "").strip(),
                        "rule_id": item.get("test_id", "B000"),
                        "tool_source": "Bandit"
                    })
        except Exception as e:
            # Fallback AST security check if bandit process fails
            issues.extend(self._ast_security_fallback(target_path))
        return issues

    def run_semgrep(self, target_path: Path) -> List[Dict[str, Any]]:
        issues = []
        try:
            # Run with lightweight security checks or local ruleset
            cmd = [
                self.semgrep_cmd,
                "scan",
                "--json",
                "--quiet",
                "--disable-version-check",
                "--config", "p/default",
                str(target_path)
            ]
            env = os.environ.copy()
            # Disable telemetry and prompt
            env["SEMGREP_SEND_METRICS"] = "off"
            env["SEMGREP_USER_AGENT_TAGS"] = "disabled"
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=40, env=env)
            raw_output = result.stdout.strip()
            if raw_output:
                try:
                    data = json.loads(raw_output)
                    for item in data.get("results", []):
                        extra = item.get("extra", {})
                        sev_map = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
                        sev = sev_map.get(extra.get("severity", "WARNING").upper(), "MEDIUM")
                        
                        rule_id = item.get("check_id", "semgrep.rule")
                        cwe = extra.get("metadata", {}).get("cwe", [])
                        cwe_str = f" [{cwe[0]}]" if cwe else ""
                        
                        issues.append({
                            "file_path": str(Path(item.get("path", "")).name),
                            "line_number": item.get("start", {}).get("line", 1),
                            "issue_type": "SECURITY",
                            "severity": sev,
                            "title": f"Semgrep: {rule_id.split('.')[-1]}{cwe_str}",
                            "message": extra.get("message", "Semgrep security finding"),
                            "code_snippet": extra.get("lines", "").strip(),
                            "rule_id": rule_id,
                            "tool_source": "Semgrep"
                        })
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass
        return issues

    def _ast_security_fallback(self, target_path: Path) -> List[Dict[str, Any]]:
        """AST-based security pattern scanner if external CLI encounters environment constraints."""
        findings = []
        py_files = list(target_path.glob("**/*.py")) if target_path.is_dir() else ([target_path] if target_path.suffix == ".py" else [])
        
        for pfile in py_files:
            try:
                content = pfile.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    # Check for eval / exec
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in ("eval", "exec"):
                            findings.append({
                                "file_path": pfile.name,
                                "line_number": node.lineno,
                                "issue_type": "SECURITY",
                                "severity": "CRITICAL",
                                "title": f"Dangerous Dynamic Code Execution: {node.func.id}()",
                                "message": f"Calling {node.func.id}() with untrusted input can lead to arbitrary code execution (CWE-95).",
                                "code_snippet": f"{node.func.id}(...)",
                                "rule_id": "SEC-AST-001",
                                "tool_source": "Bandit-Fallback"
                            })
                    # Check for subprocess shell=True
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("run", "Popen", "call", "check_output"):
                            for kw in node.keywords:
                                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    findings.append({
                                        "file_path": pfile.name,
                                        "line_number": node.lineno,
                                        "issue_type": "SECURITY",
                                        "severity": "HIGH",
                                        "title": "Subprocess with shell=True",
                                        "message": "Invoking system commands with shell=True allows shell injection attacks (Bandit B602).",
                                        "code_snippet": "subprocess...shell=True",
                                        "rule_id": "B602",
                                        "tool_source": "Bandit-Fallback"
                                    })
            except Exception:
                continue
        return findings

    def scan_path(self, target_path: Path) -> List[Dict[str, Any]]:
        bandit_issues = self.run_bandit(target_path)
        semgrep_issues = self.run_semgrep(target_path)
        
        # Deduplicate issues by file, line and rule
        all_issues = []
        seen = set()
        for issue in bandit_issues + semgrep_issues:
            key = (issue["file_path"], issue["line_number"], issue["title"])
            if key not in seen:
                seen.add(key)
                all_issues.append(issue)
        return all_issues
