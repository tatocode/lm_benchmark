import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="llmbench-test-")
os.environ.setdefault("LMB_DATA_DIR", _tmp)
os.environ.setdefault("LMB_STATIC_DIR", str(Path(_tmp) / "static"))
