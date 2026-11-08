import pytest
from fastapi.testclient import TestClient
import zipfile
import io
from app.main import app
from app.database.db import init_db

init_db()
client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "CodeSentinel" in data["app"]
    assert "chromadb_experience_count" in data

def test_direct_scan_api():
    code = """
def find_duplicates(list_a, list_b):
    duplicates = []
    for a in list_a:
        for b in list_b:
            if a == b:
                duplicates.append(a)
    return duplicates
"""
    response = client.post(
        "/api/scan-direct",
        json={"code_text": code, "filename": "test_direct.py"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["iterations_found"] >= 1
    assert len(data["optimizations"]) >= 1
    assert data["estimated_cost_reduction_pct"] > 0

def test_zip_upload_api():
    # Create in-memory zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("test_lambda.py", """
def lambda_handler(event, context):
    import math
    orders = event.get('orders', [])
    return {'count': len(orders)}
""")
    zip_buffer.seek(0)

    response = client.post(
        "/api/upload",
        files={"file": ("test_pkg.zip", zip_buffer, "application/zip")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "project_id" in data
    assert data["file_count"] >= 1

    # Scan uploaded project
    scan_resp = client.post(f"/api/scan/{data['project_id']}")
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    assert scan_data["status"] == "COMPLETED"
    assert any("Cold-Start" in i["title"] for i in scan_data["issues"])

def test_execute_code_sandbox():
    code = "print('HELLO_SANDBOX_12345')"
    response = client.post("/api/execute", json={"code_text": code, "timeout": 5})
    assert response.status_code == 200
    data = response.json()
    assert "HELLO_SANDBOX_12345" in data["stdout"]
    assert data["success"] is True
    assert data["duration_ms"] >= 0

def test_swe_bench_tasks_api():
    response = client.get("/api/swe-bench/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) >= 3
    assert any("SWE-LITE-001" in t["task_id"] for t in tasks)

def test_swe_bench_evaluation():
    passing_patch = """
def find_duplicates(list_a, list_b):
    set_b = set(list_b)
    return [x for x in list_a if x in set_b]
"""
    response = client.post(
        "/api/swe-bench/evaluate",
        json={"task_id": "SWE-LITE-001-LOOP-OPT", "candidate_code": passing_patch}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert data["status"] == "PASSED"
