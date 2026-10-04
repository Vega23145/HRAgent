"""
CLI for the standalone matcher module.

Commands
────────
  run-role   <role-id>              score all resumes against one role
  run-all                           score every resume against every role
  run-one    <resume-key> <role-id> score one resume against one role
  roles list                        list all stored roles
  roles add  <json-file>            upsert a role from a JSON file
  roles show <role-id>              print a stored role
  roles rm   <role-id>              delete a role
  top        <role-id> [--n N]      print top N matches for a role

Exit codes: 0 ok, 1 partial errors, 2 bad args / missing env.
"""
import argparse
import json
import logging
import sys

from .config import Config
from .db import connect
from .runner import RunStats, match_all, match_one, match_role

log = logging.getLogger("resume_matcher")


def _print_stats(stats: RunStats, label: str = "") -> int:
    prefix = f"[{label}] " if label else ""
    log.info("%smatched=%d skipped=%d errors=%d", prefix, stats.matched, stats.skipped, stats.errors)
    return 1 if stats.errors else 0


def cmd_run_role(args, resume_db, role_db) -> int:
    stats = match_role(args.role_id, resume_db, role_db, skip_existing=not args.overwrite)
    return _print_stats(stats, args.role_id)


def cmd_run_all(args, resume_db, role_db) -> int:
    all_stats = match_all(resume_db, role_db, skip_existing=not args.overwrite)
    rc = 0
    for role_id, stats in all_stats.items():
        rc |= _print_stats(stats, role_id)
    return rc


def cmd_run_one(args, resume_db, role_db) -> int:
    result = match_one(args.resume_key, args.role_id, resume_db, role_db, overwrite=args.overwrite)
    if result is None:
        return 2
    print(json.dumps(result, indent=2))
    return 0


def cmd_roles_list(args, resume_db, role_db) -> int:
    ids = role_db.all_ids()
    if not ids:
        print("(no roles stored)")
    for i in ids:
        print(i)
    return 0


def cmd_roles_add(args, resume_db, role_db) -> int:
    doc = json.loads(args.json_file.read_text())
    role_id = doc.get("_id") or doc.get("id")
    if not role_id:
        log.error("role JSON must have an '_id' field")
        return 2
    role_db.upsert(role_id, {k: v for k, v in doc.items() if k not in ("_id", "id")})
    log.info("upserted role: %s", role_id)
    return 0


def cmd_roles_show(args, resume_db, role_db) -> int:
    doc = role_db.get(args.role_id)
    if doc is None:
        log.error("not found: %s", args.role_id)
        return 2
    print(json.dumps(doc, indent=2, default=str))
    return 0


def cmd_roles_rm(args, resume_db, role_db) -> int:
    role_db.delete(args.role_id)
    log.info("deleted: %s", args.role_id)
    return 0


def cmd_top(args, resume_db, role_db) -> int:
    role_doc = role_db.get(args.role_id)
    if role_doc is None:
        log.error("role not found: %s", args.role_id)
        return 2

    n = args.n
    # pull only the match sub-doc for this role to avoid loading full resumes
    col = resume_db._col
    pipeline = [
        {"$match": {f"match.{args.role_id}": {"$exists": True}}},
        {"$project": {
            "name":  "$resume.name",
            "score": f"$match.{args.role_id}.score",
            "matched_skills": f"$match.{args.role_id}.matched_skills",
            "missing_skills": f"$match.{args.role_id}.missing_skills",
            "candidate_years": f"$match.{args.role_id}.candidate_years",
        }},
        {"$sort": {"score": -1}},
        {"$limit": n},
    ]
    rows = list(col.aggregate(pipeline))
    if not rows:
        print("(no matches yet — run `run-role` first)")
        return 0

    print(f"\nTop {n} for role: {role_doc['title']}\n")
    print(f"{'#':<4} {'Score':>6}  {'Name':<25}  {'Yrs':>4}  Matched / Missing")
    print("-" * 80)
    for i, r in enumerate(rows, 1):
        matched = ", ".join(r.get("matched_skills") or [])
        missing = ", ".join(r.get("missing_skills") or [])
        miss_str = f"  missing: {missing}" if missing else ""
        print(
            f"{i:<4} {r['score']:>6.1f}  {(r.get('name') or r['_id']):<25}"
            f"  {r.get('candidate_years', 0):>4.1f}  {matched}{miss_str}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="resume_matcher")
    root.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    sub = root.add_subparsers(dest="cmd", required=True)

    # run-role
    p = sub.add_parser("run-role", help="score all resumes against one role")
    p.add_argument("role_id")
    p.add_argument("--overwrite", action="store_true", help="re-score already-matched resumes")

    # run-all
    p = sub.add_parser("run-all", help="score every resume against every role")
    p.add_argument("--overwrite", action="store_true")

    # run-one
    p = sub.add_parser("run-one", help="score one resume against one role")
    p.add_argument("resume_key")
    p.add_argument("role_id")
    p.add_argument("--overwrite", action="store_true")

    # roles
    roles = sub.add_parser("roles", help="manage role definitions")
    rs = roles.add_subparsers(dest="roles_cmd", required=True)
    rs.add_parser("list")
    p2 = rs.add_parser("add");  p2.add_argument("json_file", type=lambda p: __import__("pathlib").Path(p))
    p2 = rs.add_parser("show"); p2.add_argument("role_id")
    p2 = rs.add_parser("rm");   p2.add_argument("role_id")

    # top
    p = sub.add_parser("top", help="print top matches for a role")
    p.add_argument("role_id")
    p.add_argument("--n", type=int, default=10)

    return root


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    cfg = Config.from_env()
    try:
        resume_db, role_db = connect(cfg)
    except Exception as e:
        log.error("cannot connect to MongoDB: %s", e)
        return 2

    dispatch = {
        "run-role": cmd_run_role,
        "run-all":  cmd_run_all,
        "run-one":  cmd_run_one,
        "top":      cmd_top,
        "roles":    lambda a, r, ro: {
            "list": cmd_roles_list,
            "add":  cmd_roles_add,
            "show": cmd_roles_show,
            "rm":   cmd_roles_rm,
        }[a.roles_cmd](a, r, ro),
    }

    try:
        return dispatch[args.cmd](args, resume_db, role_db)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
