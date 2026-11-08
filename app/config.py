import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROJECTS_DIR = DATA_DIR / "projects"
CHROMA_DIR = DATA_DIR / "chroma_db"
SAMPLE_DIR = BASE_DIR / "sample_projects"

# Ensure directories exist
for directory in [DATA_DIR, UPLOAD_DIR, PROJECTS_DIR, CHROMA_DIR, SAMPLE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/codesentinel.db")
SQLITE_DB_PATH = DATA_DIR / "codesentinel.db"

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "builtin") # "builtin", "gemini", "openai"

# Sandbox Execution
SANDBOX_TIMEOUT_SECONDS = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "10"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
DOCKER_IMAGE = os.getenv("DOCKER_IMAGE", "python:3.9-slim")

# App info
APP_NAME = "CodeSentinel AI"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Seminar-Powered Automated Bug Detection, Metamorphic Testing & Computational Cost Optimization Platform"
