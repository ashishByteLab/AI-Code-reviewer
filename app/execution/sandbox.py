import subprocess
import tempfile
import time
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

def check_docker_available() -> bool:
    """Checks if docker CLI is present and the docker daemon is responsive."""
    try:
        res = subprocess.run(["docker", "info"], capture_output=True, timeout=2)
        return res.returncode == 0
    except Exception:
        return False

def execute_in_docker(code_str: str, timeout: int = 5, memory_mb: int = 256) -> Dict[str, Any]:
    """Executes python code inside a fresh, isolated Docker container."""
    start_time = time.time()
    try:
        cmd = [
            "docker", "run", "--rm",
            "--network", "none", # Block outbound network access
            f"--memory={memory_mb}m",
            "--cpus=1.0",
            "python:3.9-slim",
            "python", "-c", code_str
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "driver": "Docker Container",
            "stdout": res.stdout,
            "stderr": res.stderr,
            "returncode": res.returncode,
            "duration_ms": duration_ms,
            "timed_out": False,
            "success": res.returncode == 0
        }
    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "driver": "Docker Container",
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "returncode": -1,
            "duration_ms": duration_ms,
            "timed_out": True,
            "success": False
        }
    except Exception as e:
        return {
            "driver": "Docker Container",
            "stdout": "",
            "stderr": f"Docker execution error: {str(e)}",
            "returncode": -1,
            "duration_ms": 0.0,
            "timed_out": False,
            "success": False
        }

def execute_in_local_sandbox(code_str: str, timeout: int = 5) -> Dict[str, Any]:
    """Executes python code in an isolated subprocess sandbox with temp workspace."""
    start_time = time.time()
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = Path(temp_dir) / "run_script.py"
        script_path.write_text(code_str, encoding="utf-8")
        
        # Scrub sensitive environment variables
        clean_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1"
        }
        
        try:
            cmd = ["python3", str(script_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=clean_env, cwd=temp_dir)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "driver": "Subprocess Sandbox (Docker CLI Fallback)",
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode,
                "duration_ms": duration_ms,
                "timed_out": False,
                "success": res.returncode == 0
            }
        except subprocess.TimeoutExpired:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "driver": "Subprocess Sandbox (Docker CLI Fallback)",
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "returncode": -1,
                "duration_ms": duration_ms,
                "timed_out": True,
                "success": False
            }
        except Exception as e:
            return {
                "driver": "Subprocess Sandbox (Docker CLI Fallback)",
                "stdout": "",
                "stderr": f"Sandbox execution failure: {str(e)}",
                "returncode": -1,
                "duration_ms": 0.0,
                "timed_out": False,
                "success": False
            }

def execute_python_code_safe(code_str: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Main entry point: uses Docker if available, otherwise falls back to local subprocess sandbox.
    """
    if check_docker_available():
        return execute_in_docker(code_str, timeout=timeout)
    else:
        return execute_in_local_sandbox(code_str, timeout=timeout)
