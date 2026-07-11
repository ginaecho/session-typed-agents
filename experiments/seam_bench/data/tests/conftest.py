import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = DATA_DIR.parents[1] / "scripts"
REPO_ROOT = DATA_DIR.parents[2]
for p in (DATA_DIR, SCRIPTS_DIR, REPO_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
