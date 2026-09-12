import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent
_SUMMARIZATION_DIR = _REPO_ROOT / "AI pipeline" / "summarization-deadline"

for _path in (_REPO_ROOT, _SUMMARIZATION_DIR, _BACKEND_DIR):
    _str = str(_path)
    if _str not in sys.path:
        sys.path.insert(0, _str)