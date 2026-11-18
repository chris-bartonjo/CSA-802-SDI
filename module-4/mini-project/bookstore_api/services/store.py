"""A tiny JSON-file store. Each mock subsystem owns one file, like a separate service owns its database."""
import json
import threading
from pathlib import Path


class JsonStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def read(self) -> dict:
        return json.loads(self.path.read_text())

    def write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)  # atomic swap, so a crash never leaves a half-written file
