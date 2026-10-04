"""
    python -m hragent.parsing_engine.resume_pipeline                 # drain unseen mail once
    python -m hragent.parsing_engine.resume_pipeline --loop 60       # ...then again every 60 s
    python -m hragent.parsing_engine.resume_pipeline --eml mail.eml  # process a saved email, no IMAP needed
    python -m hragent.parsing_engine.resume_pipeline --reconcile     # only sweep orphan files / report missing ones
"""
import argparse
import logging
import sys
import time
from pathlib import Path

from .config import ORPHAN_GRACE_S, Config
from .files import ResumeFiles
from .gemini import GeminiExtractor
from .mail import Mailbox
from .pipeline import process_message
from .reconcile import reconcile
from .store import build_store

log = logging.getLogger("resume_pipeline")


def drain_mailbox(cfg: Config, extract, store, files) -> None:
    with Mailbox(cfg.imap_host, cfg.imap_user, cfg.imap_password, cfg.imap_folder) as box:
        for uid, raw in box.unseen():
            try:
                if process_message(raw, extract, store, files):
                    box.mark_seen(uid)  # only after record + file are both saved
            except Exception:
                log.exception("failed on uid %s; left unseen, will retry next run", uid.decode())


def main() -> int:
    ap = argparse.ArgumentParser(prog="resume_pipeline")
    ap.add_argument("--loop", type=int, metavar="SECONDS", help="repeat forever with this pause")
    ap.add_argument("--eml", type=Path, help="process one .eml file instead of IMAP")
    ap.add_argument("--reconcile", action="store_true", help="only sync files with records, then exit")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = Config.from_env()
    needed = {}
    if not args.reconcile:
        needed["GEMINI_API_KEY"] = cfg.gemini_api_key
    if not (args.eml or args.reconcile):
        needed |= {"IMAP_HOST": cfg.imap_host, "IMAP_USER": cfg.imap_user, "IMAP_PASSWORD": cfg.imap_password}
    missing = [k for k, v in needed.items() if not v]
    if missing:
        log.error("missing env vars: %s", ", ".join(missing))
        return 2

    files = ResumeFiles(Path(cfg.resume_dir))
    store = build_store(cfg)
    try:
        removed, no_file = reconcile(store, files, ORPHAN_GRACE_S)
        if removed:
            log.warning("removed %d orphan file(s): %s", len(removed), ", ".join(removed))
        if no_file:
            log.warning("%d record(s) have no file: %s", len(no_file), ", ".join(no_file))
        if args.reconcile:
            return 0

        extract = GeminiExtractor(cfg.gemini_api_key, cfg.gemini_model, thinking_level=cfg.gemini_thinking_level)
        if args.eml:
            process_message(args.eml.read_bytes(), extract, store, files)
            return 0

        while True:
            try:
                drain_mailbox(cfg, extract, store, files)
            except Exception:
                log.exception("mailbox cycle failed")  # network drop etc: next cycle reconnects
            if not args.loop:
                return 0
            time.sleep(args.loop)
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
