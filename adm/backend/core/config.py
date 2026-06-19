"""ADM configuration — environment variables and paths."""

import os

PORT = int(os.environ.get("ADM_PORT", "5002"))
DB_PATH = os.environ.get("ADM_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "adm.db"))
REPO_ROOT = os.environ.get("ADM_REPO_ROOT", os.path.join(os.path.dirname(__file__), "..", "..", ".."))
JWT_SECRET_PATH = os.environ.get("ADM_JWT_SECRET_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "jwt_secret"))

# Resolve to absolute paths
DB_PATH = os.path.abspath(DB_PATH)
REPO_ROOT = os.path.abspath(REPO_ROOT)
JWT_SECRET_PATH = os.path.abspath(JWT_SECRET_PATH)

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(JWT_SECRET_PATH), exist_ok=True)
