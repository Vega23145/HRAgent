"""Resume files on disk: <RESUME_DIR>/<key>.pdf|.docx. Stdlib only."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator

# Only files that look like ours are ever touched, so pointing RESUME_DIR at a
# shared folder can't get unrelated files deleted by the orphan sweep.
_OURS = re.compile(r"^[0-9a-f]{16}\.(pdf|docx)(\.tmp)?$")


class ResumeFiles:
    def __init__(self, directory: Path):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def has(self, name: str) -> bool:
        return (self.dir / name).is_file()

    def write(self, name: str, payload: bytes) -> None:
        """Atomic: readers never see a half-written resume."""
        tmp = self.dir / (name + ".tmp")
        try:
            tmp.write_bytes(payload)
            os.replace(tmp, self.dir / name)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def remove(self, name: str) -> None:
        (self.dir / name).unlink(missing_ok=True)

    def managed(self) -> Iterator[tuple[str, float]]:
        """(filename, mtime) of every file this pipeline created."""
        for p in self.dir.iterdir():
            if p.is_file() and _OURS.match(p.name):
                yield p.name, p.stat().st_mtime
