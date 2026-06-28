"""确保 backend/ 在 sys.path，使 `app` 与 `evals` 包可被导入（直接 pytest / deepeval test run 均可）。"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
