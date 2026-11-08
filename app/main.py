import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

from app.config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    PROJECTS_DIR, UPLOAD_DIR, SAMPLE_DIR,
    GEMINI_API_KEY, OPENAI_API_KEY
)
from app.database.db import (
    init_db, insert_project, list_projects, get_project,
    insert_scan, insert_issues, insert_optimizations,
    insert_metamorphic_results, insert_swe_bench_eval, get_scan_details
)
from app.memory.experience_store import get_experience_store
from app.analyzers.security_scanner import SecurityScanner
from app.analyzers.iteration_detector import scan_directory_iterations, analyze_code_iterations
from app.analyzers.metamorphic_comer import MetamorphicComerEngine
from app.analyzers.serverless_profiler import ServerlessProfiler
from app.analyzers.quantum_invariants import QuantumInvariantsAnalyzer
from app.analyzers.code_optimizer import CodeOptimizer
from app.ai.llm_agent import CodeLLMAgent
from app.execution.sandbox import execute_python_code_safe, check_docker_available
from app.execution.swe_bench_lite import SweBenchLiteEvaluator

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_experience_store()
    yield

# Initialize FastAPI App
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan
)

# Static and Templates
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# Initialize modules
security_scanner = SecurityScanner()
comer_engine = MetamorphicComerEngine()
serverless_profiler = ServerlessProfiler()
quantum_analyzer = QuantumInvariantsAnalyzer()
code_optimizer = CodeOptimizer()
llm_agent = CodeLLMAgent()
swe_evaluator = SweBenchLiteEvaluator()

# Pydantic Request Models
class DirectScanRequest(BaseModel):
    code_text: str
    filename: Optional[str] = "custom_module.py"
    preferred_provider: Optional[str] = "auto"

class ExecuteCodeRequest(BaseModel):
    code_text: str
    timeout: Optional[int] = 5

class SweEvaluateRequest(BaseModel):
    task_id: str
    candidate_code: str

class ExperienceRequest(BaseModel):
    title: str
    category: str
    bug_snippet: str
    fix_snippet: str
    explanation: str
    tags: Optional[str] = ""

class SettingsRequest(BaseModel):
    gemini_key: Optional[str] = ""
    openai_key: Optional[str] = ""

# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "docker_available": check_docker_available()
    })

@app.get("/api/health")
async def health_check():
    store = get_experience_store()
    return {
        "status": "UP",
        "app": APP_NAME,
        "version": APP_VERSION,
        "docker_available": check_docker_available(),
        "chromadb_experience_count": store.collection.count(),
        "database": "SQLite (Connected)"
    }

@app.post("/api/upload")
async def upload_source_code(file: UploadFile = File(...)):
    """Accepts a .zip archive or single .py file, unpacks, and registers a project."""
    project_id = str(uuid.uuid4())[:8]
    project_path = PROJECTS_DIR / project_id
    project_path.mkdir(parents=True, exist_ok=True)
    
    filename = file.filename or "upload.zip"
    dest_file = project_path / filename
    
    with open(dest_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    extracted_files = []
    total_lines = 0
    
    if filename.endswith(".zip"):
        try:
            with zipfile.ZipFile(dest_file, "r") as zip_ref:
                # Security check against path traversal (Zip Slip)
                for member in zip_ref.namelist():
                    if member.startswith("/") or ".." in member:
                        raise HTTPException(status_code=400, detail="Invalid zip path traversal detected.")
                zip_ref.extractall(project_path)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file.")
    elif filename.endswith(".py"):
        extracted_files.append(dest_file.name)
        total_lines += len(dest_file.read_text(errors="ignore").splitlines())

    # Count all python files
    py_files = list(project_path.glob("**/*.py"))
    for pf in py_files:
        if pf.name not in extracted_files:
            extracted_files.append(str(pf.relative_to(project_path)))
        try:
            total_lines += len(pf.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            pass

    project_name = filename.rsplit(".", 1)[0].replace("_", " ").title()
    insert_project(
        project_id=project_id,
        name=project_name,
        description=f"Source project uploaded via {filename}",
        file_count=len(py_files) or 1,
        total_lines=total_lines,
        zip_name=filename
    )

    return {
        "project_id": project_id,
        "project_name": project_name,
        "file_count": len(py_files) or 1,
        "total_lines": total_lines,
        "files": extracted_files
    }

@app.post("/api/scan/{project_id}")
async def scan_project(project_id: str):
    """Executes the comprehensive multi-paper analysis pipeline on an uploaded project."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    project_path = PROJECTS_DIR / project_id
    scan_id = str(uuid.uuid4())[:8]

    # 1. Security Analysis (Bandit + Semgrep)
    security_issues = security_scanner.scan_path(project_path)
    for issue in security_issues:
        issue["scan_id"] = scan_id

    # 2. Unnecessary Iteration Analysis (AST Loop Detector)
    iteration_issues = scan_directory_iterations(project_path)
    for issue in iteration_issues:
        issue["scan_id"] = scan_id

    # 3. Metamorphic Testing (COMER IEEE TSE 2022) & Serverless Profiling
    py_files = list(project_path.glob("**/*.py"))
    metamorphic_results = []
    serverless_findings = []
    quantum_findings = []
    all_optimizations = []
    all_code_contexts = []
    
    test_ratio = {"unit": 80, "integration": 15, "e2e": 5}

    for pf in py_files:
        try:
            code_text = pf.read_text(encoding="utf-8", errors="ignore")
            all_code_contexts.append((pf.name, code_text))
            
            # COMER Testing
            comer_res = comer_engine.test_file_metamorphics(code_text, pf.name)
            for cr in comer_res:
                cr["scan_id"] = scan_id
                metamorphic_results.append(cr)
                if cr["violated"]:
                    # Create issue for invariant violation
                    security_issues.append({
                        "scan_id": scan_id,
                        "file_path": pf.name,
                        "line_number": 1,
                        "issue_type": "INVARIANT",
                        "severity": "HIGH",
                        "title": f"COMER Metamorphic Invariant Violated ({cr['relation_type']})",
                        "message": cr["message"],
                        "code_snippet": f"Source: {cr['source_input']} -> {cr['source_output']}\nFollow-up: {cr['follow_up_input']} -> {cr['follow_up_output']}",
                        "rule_id": f"COMER-MR-{cr['relation_type']}",
                        "tool_source": "COMER"
                    })

            # Serverless Profiler
            srv_res = serverless_profiler.analyze_serverless_file(code_text, pf.name)
            for sf in srv_res["findings"]:
                sf["scan_id"] = scan_id
                serverless_findings.append(sf)
            if srv_res["is_serverless"]:
                test_ratio = srv_res["test_ratio"]

            # Quantum Invariants
            q_res = quantum_analyzer.scan_invariants(code_text, pf.name)
            for qf in q_res:
                qf["scan_id"] = scan_id
                quantum_findings.append(qf)

            # Code Optimization & Alternative Exploration
            combined_file_issues = [
                i for i in (security_issues + iteration_issues + serverless_findings + quantum_findings)
                if i["file_path"] == pf.name
            ]
            file_opts = code_optimizer.optimize_code_snippet(code_text, combined_file_issues, pf.name)
            for fo in file_opts:
                fo["scan_id"] = scan_id
                all_optimizations.append(fo)

        except Exception as e:
            continue

    all_issues = security_issues + iteration_issues + serverless_findings + quantum_findings

    # 4. ChromaDB Memory Integration (Search similar experiences)
    store = get_experience_store()
    retrieved_memory = []
    if all_code_contexts:
        # Search ChromaDB with first code snippet
        sample_code = all_code_contexts[0][1]
        retrieved_memory = store.query_similar_experiences(sample_code, n_results=3)

    # 5. AI Code LLM Agent Synthesis
    primary_code = all_code_contexts[0][1] if all_code_contexts else ""
    primary_name = all_code_contexts[0][0] if all_code_contexts else "code.py"
    llm_analysis = await llm_agent.analyze_code(primary_code, all_issues, primary_name)

    # Score calculation (100 base, deductions per severity)
    score = 100
    for issue in all_issues:
        sev = issue.get("severity", "MEDIUM")
        if sev == "CRITICAL":
            score -= 20
        elif sev == "HIGH":
            score -= 10
        elif sev == "MEDIUM":
            score -= 5
        else:
            score -= 2
    score = max(10, min(100, score))

    # Calculate overall estimated computational cost reduction %
    cost_reduction = 0.0
    if all_optimizations:
        cost_reduction = round(sum(o["cost_saving_pct"] for o in all_optimizations) / len(all_optimizations), 1)
    elif any(i["issue_type"] == "ITERATION" for i in all_issues):
        cost_reduction = 65.0

    # Persist in SQLite
    scan_record = {
        "id": scan_id,
        "project_id": project_id,
        "status": "COMPLETED",
        "overall_score": score,
        "total_bugs": sum(1 for i in all_issues if i["issue_type"] in ("BUG", "INVARIANT")),
        "total_warnings": sum(1 for i in all_issues if i["issue_type"] == "WARNING"),
        "iterations_found": sum(1 for i in all_issues if i["issue_type"] == "ITERATION"),
        "security_vulns": sum(1 for i in all_issues if i["issue_type"] == "SECURITY"),
        "estimated_cost_reduction_pct": cost_reduction,
        "test_ratio_unit": test_ratio["unit"],
        "test_ratio_integration": test_ratio["integration"],
        "test_ratio_e2e": test_ratio["e2e"],
        "summary_text": llm_analysis.get("executive_summary", "Scan completed.")
    }
    
    insert_scan(scan_record)
    insert_issues(all_issues)
    insert_optimizations(all_optimizations)
    insert_metamorphic_results(metamorphic_results)

    # Automatically store new bug & optimization experience into ChromaDB
    for opt in all_optimizations:
        try:
            store.add_experience(
                title=opt["title"],
                category="LEARNED_OPTIMIZATION",
                bug_snippet=opt["original_code"][:500],
                fix_snippet=opt["optimized_code"][:500],
                explanation=opt["explanation"],
                tags=f"{opt['file_path']}, speedup_{opt['speedup_factor']}x"
            )
        except Exception:
            pass

    full_details = get_scan_details(scan_id)
    full_details["llm_analysis"] = llm_analysis
    full_details["retrieved_memory"] = retrieved_memory
    return full_details

@app.post("/api/scan-direct")
async def scan_direct_code(req: DirectScanRequest):
    """Directly scans a pasted or typed code snippet without requiring a zip upload."""
    project_id = "direct_" + str(uuid.uuid4())[:6]
    project_path = PROJECTS_DIR / project_id
    project_path.mkdir(parents=True, exist_ok=True)
    
    file_path = project_path / req.filename
    file_path.write_text(req.code_text, encoding="utf-8")
    
    insert_project(
        project_id=project_id,
        name=f"Direct: {req.filename}",
        description="Direct code snippet scan",
        file_count=1,
        total_lines=len(req.code_text.splitlines()),
        zip_name=req.filename
    )
    
    return await scan_project(project_id)

@app.get("/api/scans/{scan_id}")
async def get_scan(scan_id: str):
    scan = get_scan_details(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan

@app.get("/api/projects")
async def get_all_projects():
    return list_projects()

@app.post("/api/execute")
async def execute_code(req: ExecuteCodeRequest):
    """Executes code inside Docker or isolated sandbox."""
    res = execute_python_code_safe(req.code_text, timeout=req.timeout)
    return res

@app.get("/api/swe-bench/tasks")
async def get_swe_tasks():
    return swe_evaluator.get_all_tasks()

@app.post("/api/swe-bench/evaluate")
async def evaluate_swe_patch(req: SweEvaluateRequest):
    res = swe_evaluator.evaluate_patch(req.task_id, req.candidate_code)
    return res

@app.get("/api/memory/experiences")
async def get_experiences():
    store = get_experience_store()
    return store.get_all_experiences()

@app.post("/api/memory/add")
async def add_experience(req: ExperienceRequest):
    store = get_experience_store()
    doc_id = store.add_experience(
        title=req.title,
        category=req.category,
        bug_snippet=req.bug_snippet,
        fix_snippet=req.fix_snippet,
        explanation=req.explanation,
        tags=req.tags or ""
    )
    return {"status": "SUCCESS", "id": doc_id, "message": "Experience stored into ChromaDB memory."}

@app.post("/api/settings")
async def update_settings(req: SettingsRequest):
    llm_agent.set_keys(req.gemini_key, req.openai_key)
    return {"status": "SUCCESS", "message": "API keys updated successfully."}

@app.get("/api/demo/{demo_name}")
async def load_demo_project(demo_name: str):
    """Loads a pre-built seminar demo ZIP archive into projects for immediate scanning."""
    zip_path = SAMPLE_DIR / f"{demo_name}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Demo package not found.")
        
    project_id = f"demo_{demo_name}"
    project_path = PROJECTS_DIR / project_id
    project_path.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(project_path)
        
    py_files = list(project_path.glob("**/*.py"))
    total_lines = sum(len(pf.read_text(errors="ignore").splitlines()) for pf in py_files)
    
    titles = {
        "serverless_app": "Serverless AWS Lambda Microservice (IEEE Access 2024 Demo)",
        "math_algorithms": "Metamorphic & Combinatorial Testing (COMER IEEE TSE 2022 Demo)",
        "quantum_algo": "Quantum Reversibility & Security (IEEE Software 2025 Demo)"
    }
    
    insert_project(
        project_id=project_id,
        name=titles.get(demo_name, demo_name.replace("_", " ").title()),
        description="Official seminar base paper demonstration project",
        file_count=len(py_files),
        total_lines=total_lines,
        zip_name=f"{demo_name}.zip"
    )
    
    return {
        "project_id": project_id,
        "name": titles.get(demo_name, demo_name),
        "file_count": len(py_files),
        "total_lines": total_lines
    }
