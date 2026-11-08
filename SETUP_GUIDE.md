# 🛡️ CodeSentinel AI — Setup Guide

> **One-command setup for any system (Mac, Windows, Linux)**

---

## ⚡ Quickest Way (One Command)

### Mac / Linux
```bash
cd CodeSentinel-AI
chmod +x start.sh
./start.sh
```
This automatically creates a virtual environment, installs everything, and starts the server.

### Windows (PowerShell)
```powershell
cd CodeSentinel-AI
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000** in your browser. Done! 🎉

---

## 📋 Prerequisites

| Requirement | Version | Check Command |
|---|---|---|
| **Python** | 3.9 or higher | `python3 --version` |
| **pip** | Latest | `pip --version` |
| **Docker** (Optional) | Any | `docker --version` |

> **Note:** Docker is optional. The app works perfectly without it using a local subprocess sandbox.

---

## 🐳 Docker Method (Alternative — Zero Setup)

If your friend has Docker installed, this is the easiest:

```bash
cd CodeSentinel-AI
docker-compose up --build
```

That's it. Open **http://localhost:8000**.

---

## 🔧 Manual Step-by-Step Setup

### 1. Extract the ZIP
```bash
unzip CodeSentinel-AI-Shareable.zip
cd CodeSentinel-AI
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
```

### 3. Activate It
```bash
# Mac / Linux
source .venv/bin/activate

# Windows CMD
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run the Server
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 6. Open in Browser
Navigate to: **http://127.0.0.1:8000**

---

## 🧪 Run Tests (Optional)
```bash
# Mac / Linux
.venv/bin/pytest

# Windows
.venv\Scripts\pytest
```
All 21 tests should pass.

---

## 🔑 API Keys (Optional)

The app works without API keys using its built-in analysis engine. To enable LLM-powered insights:

1. Open the Settings panel in the web UI
2. Enter your **Google Gemini API Key** or **OpenAI API Key**
3. Click Save

Or set them as environment variables:
```bash
export GEMINI_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
```

---

## 📁 What's Included

```
CodeSentinel-AI/
├── app/                    # Main application code
│   ├── main.py             # FastAPI server & API routes
│   ├── analyzers/          # Security, COMER, Iteration, Quantum analyzers
│   ├── ai/                 # LLM agent integration
│   ├── memory/             # ChromaDB experience memory
│   ├── execution/          # Docker/Subprocess sandbox
│   ├── database/           # SQLite database
│   ├── static/             # CSS & JS (Bootstrap 5 dark theme)
│   └── templates/          # HTML dashboard
├── tests/                  # 21 pytest test cases
├── sample_projects/        # 3 demo ZIP files for testing
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker Compose config
└── start.sh                # One-click launcher (Mac/Linux)
```

---

## ❓ Troubleshooting

| Problem | Solution |
|---|---|
| `python3 not found` | Install Python 3.9+ from [python.org](https://python.org) |
| `pip install fails` | Run `pip install --upgrade pip` first |
| Port 8000 already in use | Change port: `uvicorn app.main:app --port 9000` |
| `semgrep` install error on Windows | Skip semgrep: `pip install -r requirements.txt --no-deps semgrep` or use Docker |
| Permission denied on `start.sh` | Run `chmod +x start.sh` first |
