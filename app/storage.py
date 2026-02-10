import tempfile, shutil
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def temp_workspace(prefix: str = "kaspi_bot_"):
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
