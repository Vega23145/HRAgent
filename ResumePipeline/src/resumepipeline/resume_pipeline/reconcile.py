"""Keeps files and records in sync. Stdlib only."""
from __future__ import annotations

import time

from .files import ResumeFiles
from .store import Store


def reconcile(
    store: Store, files: ResumeFiles, grace_s: int = 600, now: float | None = None
) -> tuple[list[str], list[str]]:
    """Returns (orphan files removed, record keys whose file is missing).

    Orphan = a pipeline-made file with no record, left by a crash between "file
    written" and "record saved". The grace period keeps a second running
    instance from sweeping a file that is about to get its record.
    """
    now = time.time() if now is None else now
    stored = store.keys()
    present: set[str] = set()
    removed: list[str] = []

    for name, mtime in files.managed():
        stem = name.split(".")[0]
        if stem in stored and not name.endswith(".tmp"):
            present.add(stem)
        elif now - mtime >= grace_s:
            files.remove(name)
            removed.append(name)

    return removed, sorted(stored - present)
