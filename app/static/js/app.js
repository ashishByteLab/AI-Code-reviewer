// CodeSentinel AI - Interactive Frontend Controller
let currentScanData = null;
let currentProjectId = null;

document.addEventListener("DOMContentLoaded", () => {
    initDropzone();
    initDirectCodeEditor();
    initSettingsModal();
    initSweBenchTasks();
    initExperienceMemory();
    checkHealth();
});

async function checkHealth() {
    try {
        const res = await fetch("/api/health");
        const data = await res.json();
        const badge = document.getElementById("dockerStatusBadge");
        if (badge) {
            if (data.docker_available) {
                badge.className = "badge bg-success";
                badge.innerHTML = '<i class="bi bi-box-seam me-1"></i> Docker Sandbox: Active';
            } else {
                badge.className = "badge bg-warning text-dark";
                badge.innerHTML = '<i class="bi bi-shield-check me-1"></i> Subprocess Sandbox (Safe Fallback)';
            }
        }
    } catch (e) {
        console.error("Health check error:", e);
    }
}

// -------------------------------------------------------------
// Dropzone and File Upload
// -------------------------------------------------------------
function initDropzone() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("zipFileInput");

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("click", () => fileInput.click());

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    showLoading(true, `Uploading & extracting '${file.name}'...`);
    const formData = new FormData();
    formData.append("file", file);

    try {
        const uploadRes = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        if (!uploadRes.ok) {
            const err = await uploadRes.json();
            throw new Error(err.detail || "Upload failed");
        }

        const project = await uploadRes.json();
        currentProjectId = project.project_id;
        
        showLoading(true, `Running Multi-Paper Analysis Pipeline on ${project.file_count} file(s)...`);
        await triggerScan(project.project_id);
    } catch (err) {
        showLoading(false);
        showToast("Error", err.message, "danger");
    }
}

// -------------------------------------------------------------
// Direct Code Editor Scan
// -------------------------------------------------------------
function initDirectCodeEditor() {
    const directScanBtn = document.getElementById("directScanBtn");
    const directCodeInput = document.getElementById("directCodeInput");

    if (directScanBtn && directCodeInput) {
        directScanBtn.addEventListener("click", async () => {
            const code = directCodeInput.value.trim();
            if (!code) {
                showToast("Empty Code", "Please enter or paste Python source code.", "warning");
                return;
            }

            showLoading(true, "Scanning code with Bandit, Semgrep, COMER & Iteration Analyzer...");
            try {
                const res = await fetch("/api/scan-direct", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        code_text: code,
                        filename: "direct_snippet.py"
                    })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Scan failed");
                }

                const scanData = await res.json();
                renderScanResults(scanData);
                showLoading(false);
            } catch (e) {
                showLoading(false);
                showToast("Scan Error", e.message, "danger");
            }
        });
    }
}

// -------------------------------------------------------------
// Pre-built Demo Project Loader
// -------------------------------------------------------------
async function loadDemo(demoName) {
    showLoading(true, `Loading Seminar Demo: ${demoName}...`);
    try {
        const res = await fetch(`/api/demo/${demoName}`);
        if (!res.ok) throw new Error("Could not load demo package.");
        const proj = await res.json();
        currentProjectId = proj.project_id;
        
        showLoading(true, `Analyzing ${proj.name}...`);
        await triggerScan(proj.project_id);
    } catch (e) {
        showLoading(false);
        showToast("Error", e.message, "danger");
    }
}

async function triggerScan(projectId) {
    try {
        const res = await fetch(`/api/scan/${projectId}`, { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Scan execution failed");
        }
        const data = await res.json();
        renderScanResults(data);
        showLoading(false);
    } catch (e) {
        showLoading(false);
        showToast("Scan Failed", e.message, "danger");
    }
}

// -------------------------------------------------------------
// Render Results Dashboard
// -------------------------------------------------------------
function renderScanResults(data) {
    currentScanData = data;
    document.getElementById("resultsDashboard").style.display = "block";
    document.getElementById("resultsDashboard").scrollIntoView({ behavior: "smooth" });

    // 1. Health Score Gauge
    const scoreVal = document.getElementById("scoreValue");
    const scoreCircle = document.getElementById("scoreCircle");
    if (scoreVal && scoreCircle) {
        scoreVal.textContent = data.overall_score;
        if (data.overall_score >= 80) {
            scoreCircle.style.borderColor = "var(--accent-emerald)";
            scoreCircle.style.boxShadow = "0 0 25px rgba(16, 185, 129, 0.4)";
            scoreVal.style.color = "var(--accent-emerald)";
        } else if (data.overall_score >= 50) {
            scoreCircle.style.borderColor = "var(--accent-amber)";
            scoreCircle.style.boxShadow = "0 0 25px rgba(245, 158, 11, 0.4)";
            scoreVal.style.color = "var(--accent-amber)";
        } else {
            scoreCircle.style.borderColor = "var(--accent-rose)";
            scoreCircle.style.boxShadow = "0 0 25px rgba(244, 63, 94, 0.4)";
            scoreVal.style.color = "var(--accent-rose)";
        }
    }

    // 2. Stat Counts
    document.getElementById("statBugs").textContent = data.total_bugs;
    document.getElementById("statIterations").textContent = data.iterations_found;
    document.getElementById("statSecurity").textContent = data.security_vulns;
    document.getElementById("statCostSavings").textContent = `${data.estimated_cost_reduction_pct}%`;

    // 3. Shift-Left Test Ratio Bar (IEEE Access 2024)
    const unitBar = document.getElementById("testRatioUnit");
    const intBar = document.getElementById("testRatioIntegration");
    const e2eBar = document.getElementById("testRatioE2E");
    if (unitBar && intBar && e2eBar) {
        unitBar.style.width = `${data.test_ratio_unit}%`;
        unitBar.textContent = `Unit: ${data.test_ratio_unit}%`;
        intBar.style.width = `${data.test_ratio_integration}%`;
        intBar.textContent = `Integration: ${data.test_ratio_integration}%`;
        e2eBar.style.width = `${data.test_ratio_e2e}%`;
        e2eBar.textContent = `E2E: ${data.test_ratio_e2e}%`;
    }

    // 4. Executive Summary
    const summaryElem = document.getElementById("executiveSummaryText");
    if (summaryElem) {
        summaryElem.textContent = data.summary_text || (data.llm_analysis ? data.llm_analysis.executive_summary : "Scan completed.");
    }

    // 5. Render Issues
    renderIssuesList(data.issues || []);

    // 6. Render Optimizations
    renderOptimizations(data.optimizations || []);

    // 7. Render COMER Metamorphic Results
    renderMetamorphicResults(data.metamorphic_results || []);

    // 8. Render Retrieved Experience Memory
    renderRetrievedExperiences(data.retrieved_memory || []);

    // Fill Sandbox with original code for testing
    if (data.optimizations && data.optimizations.length > 0) {
        document.getElementById("sandboxCodeInput").value = data.optimizations[0].original_code;
    }
}

// -------------------------------------------------------------
// Issues List & Filtering
// -------------------------------------------------------------
function renderIssuesList(issues) {
    const container = document.getElementById("issuesContainer");
    if (!container) return;

    if (issues.length === 0) {
        container.innerHTML = `
            <div class="p-4 text-center text-success">
                <i class="bi bi-check-circle-fill fs-2"></i>
                <h5 class="mt-2">No Errors or Bottlenecks Found!</h5>
                <p class="text-muted">The codebase adheres to clean architecture, proper loop structures, and robust security practices.</p>
            </div>
        `;
        return;
    }

    let html = "";
    issues.forEach((issue, idx) => {
        let badgeClass = "medium";
        if (issue.severity === "CRITICAL") badgeClass = "critical";
        else if (issue.severity === "HIGH") badgeClass = "high";
        else if (issue.severity === "LOW") badgeClass = "success";

        let typeIcon = "bi-bug";
        if (issue.issue_type === "ITERATION") typeIcon = "bi-arrow-repeat text-warning";
        else if (issue.issue_type === "SECURITY") typeIcon = "bi-shield-exclamation text-danger";
        else if (issue.issue_type === "INVARIANT") typeIcon = "bi-sliders text-info";

        html += `
            <div class="glass-card p-3 mb-3 issue-card" data-type="${issue.issue_type}">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <i class="bi ${typeIcon} fs-5"></i>
                        <h6 class="mb-0 fw-bold">${escapeHtml(issue.title)}</h6>
                    </div>
                    <div class="d-flex gap-2">
                        <span class="badge bg-secondary">${issue.tool_source}</span>
                        <span class="metric-pill ${badgeClass}">${issue.severity}</span>
                    </div>
                </div>
                <div class="text-muted small mb-2">
                    <i class="bi bi-file-earmark-code me-1"></i><strong>${escapeHtml(issue.file_path)}</strong> : Line ${issue.line_number}
                    ${issue.rule_id ? `| Rule: <code>${issue.rule_id}</code>` : ""}
                </div>
                <p class="mb-2 text-light" style="font-size: 0.95rem;">${escapeHtml(issue.message)}</p>
                ${issue.code_snippet ? `
                    <div class="code-container p-2 small mb-0"><code>${escapeHtml(issue.code_snippet)}</code></div>
                ` : ""}
            </div>
        `;
    });
    container.innerHTML = html;
}

function filterIssues(type) {
    document.querySelectorAll(".issue-filter-btn").forEach(btn => btn.classList.remove("active"));
    event.target.classList.add("active");

    const cards = document.querySelectorAll(".issue-card");
    cards.forEach(card => {
        if (type === "ALL" || card.getAttribute("data-type") === type) {
            card.style.display = "block";
        } else {
            card.style.display = "none";
        }
    });
}

// -------------------------------------------------------------
// Render Optimizations & Alternatives
// -------------------------------------------------------------
function renderOptimizations(optimizations) {
    const container = document.getElementById("optimizationsContainer");
    if (!container) return;

    if (optimizations.length === 0) {
        container.innerHTML = `
            <div class="p-4 text-center text-muted">
                <i class="bi bi-lightbulb fs-2"></i>
                <p class="mt-2">No algorithmic optimization candidates generated. The code runs at optimal complexity.</p>
            </div>
        `;
        return;
    }

    let html = "";
    optimizations.forEach((opt, idx) => {
        html += `
            <div class="glass-card p-4 mb-4">
                <div class="d-flex justify-content-between align-items-start mb-3 flex-wrap gap-2">
                    <div>
                        <h5 class="fw-bold mb-1"><i class="bi bi-lightning-charge-fill text-warning me-2"></i>${escapeHtml(opt.title)}</h5>
                        <span class="text-muted small"><i class="bi bi-file-earmark-code me-1"></i>${escapeHtml(opt.file_path)}</span>
                    </div>
                    <div class="d-flex gap-2">
                        <span class="badge bg-success p-2"><i class="bi bi-speedometer2 me-1"></i>${opt.speedup_factor}x Faster</span>
                        <span class="badge bg-info text-dark p-2"><i class="bi bi-memory me-1"></i>${opt.memory_reduction_pct}% Memory Saved</span>
                        <span class="badge bg-warning text-dark p-2"><i class="bi bi-cash-stack me-1"></i>${opt.cost_saving_pct}% Cost Cut</span>
                    </div>
                </div>
                
                <p class="text-light mb-3">${escapeHtml(opt.explanation)}</p>

                <!-- Diff Viewer -->
                <div class="row g-3">
                    <div class="col-md-6">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="small text-danger fw-bold"><i class="bi bi-x-circle me-1"></i>Original Code (Inefficient / Buggy)</span>
                            <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="loadToSandbox(${idx}, 'orig')">Test in Sandbox</button>
                        </div>
                        <pre class="code-container" style="max-height: 280px;"><code>${escapeHtml(opt.original_code)}</code></pre>
                    </div>
                    <div class="col-md-6">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="small text-success fw-bold"><i class="bi bi-check-circle me-1"></i>Optimized Alternative (High Performance)</span>
                            <button class="btn btn-sm btn-outline-success py-0 px-2" onclick="loadToSandbox(${idx}, 'opt')">Test in Sandbox</button>
                        </div>
                        <pre class="code-container" style="max-height: 280px;"><code>${escapeHtml(opt.optimized_code)}</code></pre>
                    </div>
                </div>

                ${opt.diff_text ? `
                    <div class="mt-3">
                        <button class="btn btn-sm btn-outline-info" type="button" data-bs-toggle="collapse" data-bs-target="#diffCollapse${idx}">
                            <i class="bi bi-file-diff me-1"></i> View Line-by-Line Unified Diff
                        </button>
                        <div class="collapse mt-2" id="diffCollapse${idx}">
                            <pre class="code-container">${formatUnifiedDiff(opt.diff_text)}</pre>
                        </div>
                    </div>
                ` : ""}
            </div>
        `;
    });
    container.innerHTML = html;
}

function formatUnifiedDiff(diffText) {
    return diffText.split("\n").map(line => {
        if (line.startsWith("+") && !line.startsWith("+++")) {
            return `<span class="diff-line-add">${escapeHtml(line)}</span>`;
        } else if (line.startsWith("-") && !line.startsWith("---")) {
            return `<span class="diff-line-del">${escapeHtml(line)}</span>`;
        }
        return escapeHtml(line);
    }).join("\n");
}

function loadToSandbox(optIdx, type) {
    if (!currentScanData || !currentScanData.optimizations) return;
    const opt = currentScanData.optimizations[optIdx];
    const code = type === "orig" ? opt.original_code : opt.optimized_code;
    document.getElementById("sandboxCodeInput").value = code;
    document.getElementById("sandboxTabBtn").click();
    showToast("Loaded to Sandbox", `Loaded ${type === 'orig' ? 'original' : 'optimized'} code into execution sandbox.`, "info");
}

// -------------------------------------------------------------
// Render COMER Metamorphic Testing Results
// -------------------------------------------------------------
function renderMetamorphicResults(results) {
    const tbody = document.getElementById("metamorphicTableBody");
    if (!tbody) return;

    if (results.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No analytical functions eligible for automated metamorphic group generation.</td></tr>`;
        return;
    }

    let html = "";
    results.forEach(res => {
        const badge = res.violated 
            ? `<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>VIOLATION DETECTED</span>`
            : `<span class="badge bg-success"><i class="bi bi-check2-circle me-1"></i>SATISFIED</span>`;
            
        html += `
            <tr>
                <td class="fw-bold">${escapeHtml(res.test_name)}</td>
                <td><span class="badge bg-secondary">MR_${res.relation_type}</span></td>
                <td><div class="small">Src: <code>${escapeHtml(res.source_input)}</code></div><div class="small text-info">Fol: <code>${escapeHtml(res.follow_up_input)}</code></div></td>
                <td><div class="small">Src: ${escapeHtml(res.source_output || 'null')}</div><div class="small">Fol: ${escapeHtml(res.follow_up_output || 'null')}</div></td>
                <td>${badge}</td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

// -------------------------------------------------------------
// Render Retrieved Experience Memory
// -------------------------------------------------------------
function renderRetrievedExperiences(experiences) {
    const container = document.getElementById("experienceMemoryContainer");
    if (!container) return;

    if (experiences.length === 0) {
        container.innerHTML = `<p class="text-muted small">No past experience match above semantic distance threshold in ChromaDB.</p>`;
        return;
    }

    let html = "";
    experiences.forEach(exp => {
        html += `
            <div class="p-3 border rounded mb-2" style="background: rgba(255,255,255,0.03); border-color: #30363d !important;">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="fw-bold text-info"><i class="bi bi-journal-bookmark me-1"></i>${escapeHtml(exp.title)}</span>
                    <span class="badge bg-primary">${exp.similarity_pct}% Similarity</span>
                </div>
                <p class="small text-muted mb-2">${escapeHtml(exp.explanation)}</p>
                <div class="small"><strong>Proven Fix:</strong></div>
                <pre class="code-container p-2 small mb-0" style="max-height: 120px;"><code>${escapeHtml(exp.fix_snippet)}</code></pre>
            </div>
        `;
    });
    container.innerHTML = html;
}

// -------------------------------------------------------------
// Live Sandbox Execution
// -------------------------------------------------------------
async function runSandboxCode() {
    const code = document.getElementById("sandboxCodeInput").value.trim();
    if (!code) {
        showToast("Empty Code", "Please enter code to execute.", "warning");
        return;
    }

    const consoleElem = document.getElementById("sandboxOutputConsole");
    const runBtn = document.getElementById("runSandboxBtn");
    consoleElem.innerHTML = `<span class="text-warning"><i class="bi bi-hourglass-split"></i> Executing in Sandbox container...</span>`;
    runBtn.disabled = true;

    try {
        const res = await fetch("/api/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code_text: code, timeout: 6 })
        });
        const out = await res.json();
        
        let outputText = `Execution Driver: ${out.driver}\nExecution Duration: ${out.duration_ms} ms\nStatus: ${out.success ? 'SUCCESS (Exit 0)' : 'FAILED (Exit ' + out.returncode + ')'}\n`;
        outputText += "--------------------------------------------------\n";
        if (out.stdout) outputText += `[STDOUT]\n${out.stdout}\n`;
        if (out.stderr) outputText += `[STDERR]\n${out.stderr}\n`;

        consoleElem.textContent = outputText;
    } catch (e) {
        consoleElem.textContent = `Error launching sandbox: ${e.message}`;
    } finally {
        runBtn.disabled = false;
    }
}

// -------------------------------------------------------------
// SWE-bench Lite Evaluator
// -------------------------------------------------------------
async function initSweBenchTasks() {
    const select = document.getElementById("sweTaskSelect");
    if (!select) return;

    try {
        const res = await fetch("/api/swe-bench/tasks");
        const tasks = await res.json();
        select.innerHTML = tasks.map(t => `<option value="${t.task_id}">${t.task_id}: ${t.title}</option>`).join("");
        updateSweTaskDescription(tasks);

        select.addEventListener("change", () => updateSweTaskDescription(tasks));
    } catch (e) {
        console.error("SWE tasks load error:", e);
    }
}

function updateSweTaskDescription(tasks) {
    const select = document.getElementById("sweTaskSelect");
    const descElem = document.getElementById("sweTaskDesc");
    const selectedTask = tasks.find(t => t.task_id === select.value);
    if (selectedTask && descElem) {
        descElem.textContent = selectedTask.problem_statement;
    }
}

async function runSweEvaluation() {
    const select = document.getElementById("sweTaskSelect");
    const code = document.getElementById("swePatchCodeInput").value.trim();
    if (!code) {
        showToast("Empty Patch", "Please enter the candidate function code.", "warning");
        return;
    }

    const resElem = document.getElementById("sweEvalResult");
    resElem.innerHTML = `<span class="text-warning"><i class="bi bi-hourglass-split"></i> Executing SWE-bench Lite regression tests...</span>`;

    try {
        const res = await fetch("/api/swe-bench/evaluate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task_id: select.value, candidate_code: code })
        });
        const data = await res.json();
        
        let statusBadge = data.passed 
            ? `<div class="alert alert-success mt-2"><i class="bi bi-check-circle-fill me-2"></i>SWE-BENCH LITE EVALUATION PASSED! (${data.duration_ms} ms)</div>`
            : `<div class="alert alert-danger mt-2"><i class="bi bi-x-circle-fill me-2"></i>SWE-BENCH LITE EVALUATION FAILED (${data.duration_ms} ms)</div>`;
            
        resElem.innerHTML = `
            ${statusBadge}
            <pre class="code-container p-3">${escapeHtml(data.execution_log)}</pre>
        `;
    } catch (e) {
        resElem.innerHTML = `<div class="alert alert-danger">Evaluation failed: ${e.message}</div>`;
    }
}

// -------------------------------------------------------------
// ChromaDB Experience Memory Tab
// -------------------------------------------------------------
async function initExperienceMemory() {
    const container = document.getElementById("allExperiencesList");
    if (!container) return;

    try {
        const res = await fetch("/api/memory/experiences");
        const list = await res.json();
        if (list.length === 0) {
            container.innerHTML = `<p class="text-muted">No stored experiences found.</p>`;
            return;
        }

        let html = "";
        list.forEach(exp => {
            html += `
                <div class="glass-card p-3 mb-3">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <h6 class="fw-bold mb-0 text-info"><i class="bi bi-brain me-2"></i>${escapeHtml(exp.title)}</h6>
                        <span class="badge bg-secondary">${escapeHtml(exp.category)}</span>
                    </div>
                    <p class="small text-muted mb-2">${escapeHtml(exp.explanation)}</p>
                    <div class="row g-2">
                        <div class="col-6">
                            <span class="small text-danger">Bug / Antipattern:</span>
                            <pre class="code-container p-2 small mb-0" style="max-height: 100px;"><code>${escapeHtml(exp.bug_snippet)}</code></pre>
                        </div>
                        <div class="col-6">
                            <span class="small text-success">Optimized Pattern:</span>
                            <pre class="code-container p-2 small mb-0" style="max-height: 100px;"><code>${escapeHtml(exp.fix_snippet)}</code></pre>
                        </div>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (e) {
        console.error("Memory load error:", e);
    }
}

async function submitNewExperience() {
    const title = document.getElementById("expTitle").value.trim();
    const category = document.getElementById("expCategory").value;
    const bug = document.getElementById("expBug").value.trim();
    const fix = document.getElementById("expFix").value.trim();
    const expl = document.getElementById("expExplanation").value.trim();

    if (!title || !bug || !fix || !expl) {
        showToast("Missing fields", "Please fill in all experience memory fields.", "warning");
        return;
    }

    try {
        const res = await fetch("/api/memory/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                title, category, bug_snippet: bug, fix_snippet: fix, explanation: expl
            })
        });
        if (res.ok) {
            showToast("Saved", "Experience stored permanently into ChromaDB vector memory!", "success");
            initExperienceMemory();
            // Clear inputs
            document.getElementById("expTitle").value = "";
            document.getElementById("expBug").value = "";
            document.getElementById("expFix").value = "";
            document.getElementById("expExplanation").value = "";
        }
    } catch (e) {
        showToast("Error", e.message, "danger");
    }
}

// -------------------------------------------------------------
// Settings Modal
// -------------------------------------------------------------
function initSettingsModal() {
    const saveBtn = document.getElementById("saveSettingsBtn");
    if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
            const geminiKey = document.getElementById("geminiKeyInput").value.trim();
            const openaiKey = document.getElementById("openaiKeyInput").value.trim();

            const res = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ gemini_key: geminiKey, openai_key: openaiKey })
            });
            if (res.ok) {
                showToast("Settings Updated", "LLM API keys saved for session.", "success");
                const modal = bootstrap.Modal.getInstance(document.getElementById("settingsModal"));
                if (modal) modal.hide();
            }
        });
    }
}

// -------------------------------------------------------------
// Export Audit Report
// -------------------------------------------------------------
function downloadReport() {
    if (!currentScanData) {
        showToast("No Scan", "Please run a scan before downloading the report.", "warning");
        return;
    }

    let md = `# CodeSentinel AI Audit Report\n\n`;
    md += `**Date:** ${new Date().toISOString()}\n`;
    md += `**Overall Code Health Score:** ${currentScanData.overall_score}/100\n`;
    md += `**Estimated Computational Cost Reduction:** ${currentScanData.estimated_cost_reduction_pct}%\n`;
    md += `**Recommended Shift-Left Testing Ratio:** Unit: ${currentScanData.test_ratio_unit}%, Integration: ${currentScanData.test_ratio_integration}%, E2E: ${currentScanData.test_ratio_e2e}%\n\n`;
    md += `## Executive Summary\n${currentScanData.summary_text}\n\n`;
    md += `## Detected Bugs, Security Vulnerabilities & Unnecessary Iterations (${currentScanData.issues.length})\n\n`;

    currentScanData.issues.forEach((i, idx) => {
        md += `### ${idx + 1}. [${i.severity}] ${i.title}\n`;
        md += `- **File:** ${i.file_path} (Line ${i.line_number})\n`;
        md += `- **Type:** ${i.issue_type} | **Source:** ${i.tool_source}\n`;
        md += `- **Details:** ${i.message}\n\n`;
    });

    md += `## Efficient Alternative Codes & Optimizations (${currentScanData.optimizations.length})\n\n`;
    currentScanData.optimizations.forEach((opt, idx) => {
        md += `### Optimization ${idx + 1}: ${opt.title}\n`;
        md += `- **Speedup Factor:** ${opt.speedup_factor}x\n`;
        md += `- **Memory Reduction:** ${opt.memory_reduction_pct}%\n`;
        md += `- **Explanation:** ${opt.explanation}\n\n`;
        md += `\`\`\`python\n${opt.optimized_code}\n\`\`\`\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `CodeSentinel_Audit_Report_${currentScanData.id}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

// -------------------------------------------------------------
// Helpers & UI Utilities
// -------------------------------------------------------------
function showLoading(show, message = "Analyzing code...") {
    const overlay = document.getElementById("loadingOverlay");
    const msg = document.getElementById("loadingMessage");
    if (overlay) overlay.style.display = show ? "flex" : "none";
    if (msg) msg.textContent = message;
}

function showToast(title, message, type = "info") {
    const toastElem = document.getElementById("liveToast");
    if (!toastElem) return;

    document.getElementById("toastTitle").textContent = title;
    document.getElementById("toastBody").textContent = message;
    
    toastElem.className = `toast align-items-center text-bg-${type} border-0`;
    const toast = new bootstrap.Toast(toastElem);
    toast.show();
}

function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
