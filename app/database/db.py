import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.config import SQLITE_DB_PATH

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        file_count INTEGER DEFAULT 0,
        total_lines INTEGER DEFAULT 0,
        zip_name TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    # Scans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        status TEXT NOT NULL,
        overall_score INTEGER DEFAULT 100,
        total_bugs INTEGER DEFAULT 0,
        total_warnings INTEGER DEFAULT 0,
        iterations_found INTEGER DEFAULT 0,
        security_vulns INTEGER DEFAULT 0,
        estimated_cost_reduction_pct REAL DEFAULT 0.0,
        test_ratio_unit INTEGER DEFAULT 80,
        test_ratio_integration INTEGER DEFAULT 15,
        test_ratio_e2e INTEGER DEFAULT 5,
        summary_text TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )
    """)
    
    # Issues table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        line_number INTEGER,
        issue_type TEXT NOT NULL, -- BUG, WARNING, ITERATION, SECURITY, INVARIANT
        severity TEXT NOT NULL,   -- CRITICAL, HIGH, MEDIUM, LOW
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        code_snippet TEXT,
        rule_id TEXT,
        tool_source TEXT NOT NULL, -- Bandit, Semgrep, COMER, ServerlessProfiler, ASTIteration
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )
    """)
    
    # Optimizations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS optimizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT NOT NULL,
        file_path TEXT NOT NULL,
        title TEXT NOT NULL,
        original_code TEXT NOT NULL,
        optimized_code TEXT NOT NULL,
        speedup_factor REAL DEFAULT 1.0,
        memory_reduction_pct REAL DEFAULT 0.0,
        cost_saving_pct REAL DEFAULT 0.0,
        explanation TEXT NOT NULL,
        diff_text TEXT,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )
    """)
    
    # Metamorphic COMER test results
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS metamorphic_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT NOT NULL,
        test_name TEXT NOT NULL,
        relation_type TEXT NOT NULL, -- Add, Permute, Reverse, Scale, Invert, Include, etc.
        source_input TEXT NOT NULL,
        follow_up_input TEXT NOT NULL,
        source_output TEXT,
        follow_up_output TEXT,
        violated BOOLEAN NOT NULL,
        message TEXT,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )
    """)
    
    # SWE-bench Lite evaluations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS swe_bench_evals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        title TEXT NOT NULL,
        problem_statement TEXT,
        test_patch TEXT,
        status TEXT NOT NULL,
        passed BOOLEAN NOT NULL,
        execution_log TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )
    """)

    conn.commit()
    conn.close()

# Auto-initialize database schema on module load
try:
    init_db()
except Exception:
    pass

# Database helper functions
def insert_project(project_id: str, name: str, description: str, file_count: int, total_lines: int, zip_name: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO projects (id, name, description, file_count, total_lines, zip_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, name, description, file_count, total_lines, zip_name, now)
    )
    conn.commit()
    conn.close()
    return {"id": project_id, "name": name, "file_count": file_count, "created_at": now}

def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_projects() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_scan(scan_data: Dict[str, Any]) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    scan_id = scan_data["id"]
    cursor.execute("""
    INSERT INTO scans (
        id, project_id, status, overall_score, total_bugs, total_warnings, 
        iterations_found, security_vulns, estimated_cost_reduction_pct,
        test_ratio_unit, test_ratio_integration, test_ratio_e2e, summary_text, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        scan_id,
        scan_data["project_id"],
        scan_data.get("status", "COMPLETED"),
        scan_data.get("overall_score", 100),
        scan_data.get("total_bugs", 0),
        scan_data.get("total_warnings", 0),
        scan_data.get("iterations_found", 0),
        scan_data.get("security_vulns", 0),
        scan_data.get("estimated_cost_reduction_pct", 0.0),
        scan_data.get("test_ratio_unit", 80),
        scan_data.get("test_ratio_integration", 15),
        scan_data.get("test_ratio_e2e", 5),
        scan_data.get("summary_text", ""),
        now
    ))
    conn.commit()
    conn.close()
    return scan_id

def insert_issues(issues: List[Dict[str, Any]]):
    if not issues:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    for item in issues:
        cursor.execute("""
        INSERT INTO issues (scan_id, file_path, line_number, issue_type, severity, title, message, code_snippet, rule_id, tool_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["scan_id"],
            item.get("file_path", "unknown"),
            item.get("line_number", 0),
            item.get("issue_type", "BUG"),
            item.get("severity", "MEDIUM"),
            item.get("title", ""),
            item.get("message", ""),
            item.get("code_snippet", ""),
            item.get("rule_id", ""),
            item.get("tool_source", "Analyzer")
        ))
    conn.commit()
    conn.close()

def insert_optimizations(optimizations: List[Dict[str, Any]]):
    if not optimizations:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    for opt in optimizations:
        cursor.execute("""
        INSERT INTO optimizations (scan_id, file_path, title, original_code, optimized_code, speedup_factor, memory_reduction_pct, cost_saving_pct, explanation, diff_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            opt["scan_id"],
            opt.get("file_path", ""),
            opt.get("title", "Optimization"),
            opt.get("original_code", ""),
            opt.get("optimized_code", ""),
            opt.get("speedup_factor", 1.0),
            opt.get("memory_reduction_pct", 0.0),
            opt.get("cost_saving_pct", 0.0),
            opt.get("explanation", ""),
            opt.get("diff_text", "")
        ))
    conn.commit()
    conn.close()

def insert_metamorphic_results(results: List[Dict[str, Any]]):
    if not results:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    for m in results:
        cursor.execute("""
        INSERT INTO metamorphic_results (scan_id, test_name, relation_type, source_input, follow_up_input, source_output, follow_up_output, violated, message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            m["scan_id"],
            m.get("test_name", ""),
            m.get("relation_type", "MR"),
            m.get("source_input", ""),
            m.get("follow_up_input", ""),
            m.get("source_output", ""),
            m.get("follow_up_output", ""),
            m.get("violated", False),
            m.get("message", "")
        ))
    conn.commit()
    conn.close()

def insert_swe_bench_eval(eval_data: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO swe_bench_evals (scan_id, task_id, title, problem_statement, test_patch, status, passed, execution_log, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        eval_data["scan_id"],
        eval_data.get("task_id", "SWE-001"),
        eval_data.get("title", "Task"),
        eval_data.get("problem_statement", ""),
        eval_data.get("test_patch", ""),
        eval_data.get("status", "COMPLETED"),
        eval_data.get("passed", True),
        eval_data.get("execution_log", ""),
        now
    ))
    conn.commit()
    conn.close()

def get_scan_details(scan_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scans WHERE id = ?", (scan_id,))
    scan_row = cursor.fetchone()
    if not scan_row:
        conn.close()
        return None
    scan = dict(scan_row)
    
    cursor.execute("SELECT * FROM issues WHERE scan_id = ? ORDER BY line_number ASC", (scan_id,))
    scan["issues"] = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM optimizations WHERE scan_id = ?", (scan_id,))
    scan["optimizations"] = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM metamorphic_results WHERE scan_id = ?", (scan_id,))
    scan["metamorphic_results"] = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM swe_bench_evals WHERE scan_id = ?", (scan_id,))
    scan["swe_bench_evals"] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return scan
