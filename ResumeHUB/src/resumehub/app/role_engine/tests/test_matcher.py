"""
Offline, stdlib only — no real MongoDB.
"""
import copy
import unittest

from resumehub.app.role_engine.resume_matcher.algo import Role, WeightedSkill, match
from resumehub.app.role_engine.resume_matcher.db import ResumeDB, RoleDB
from resumehub.app.role_engine.resume_matcher.runner import match_all, match_one, match_role


# ── fake Mongo collection ─────────────────────────────────────────
def _has_path(d, dotpath):
    parts = dotpath.split(".", 1)
    if not isinstance(d, dict) or parts[0] not in d:
        return False
    return True if len(parts) == 1 else _has_path(d[parts[0]], parts[1])


def _set_nested(d, dotpath, val):
    parts = dotpath.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = val


class FakeCol:
    def __init__(self, docs=None):
        self.docs = dict(docs or {})

    def find_one(self, flt, proj=None):
        return self.docs.get(flt["_id"])

    def find(self, flt, proj=None):
        # find_unmatched: {"match.<role>": {"$exists": False}}
        if "$exists" in str(flt):
            dotpath = next(iter(flt))
            want_exists = flt[dotpath]["$exists"]  # True or False
            return [
                {"_id": k}
                for k, d in self.docs.items()
                if _has_path(d, dotpath) == want_exists
            ]
        return [{"_id": k} for k in self.docs]

    def update_one(self, flt, update, upsert=False):
        doc = self.docs.setdefault(flt["_id"], {})
        for dotpath, val in update.get("$set", {}).items():
            _set_nested(doc, dotpath, val)

    def replace_one(self, flt, doc, upsert=False):
        self.docs[flt["_id"]] = doc

    def delete_one(self, flt):
        self.docs.pop(flt["_id"], None)

    def aggregate(self, pipeline):
        role_id = None
        for stage in pipeline:
            if "$match" in stage:
                role_id = next(iter(stage["$match"])).split(".", 1)[1]
        rows = []
        for k, d in self.docs.items():
            m = (d.get("match") or {}).get(role_id)
            if m:
                rows.append({
                    "_id": k,
                    "name": d.get("resume", {}).get("name"),
                    "score": m["score"],
                    "matched_skills": m.get("matched_skills"),
                    "missing_skills": m.get("missing_skills"),
                    "candidate_years": m.get("candidate_years"),
                })
        rows.sort(key=lambda r: r["score"], reverse=True)
        return rows


# ── fixtures ──────────────────────────────────────────────────────
ROLE_DOC = {
    "_id": "junior-python-backend",
    "title": "Junior Python Backend Engineer",
    "required_skills": [
        {"name": "python", "weight": 2.0},
        {"name": "fastapi", "weight": 1.5},
        {"name": "docker",  "weight": 1.0},
    ],
    "min_years": 0.5,
    "seniority": 1,
}

RESUME_DOC = {
    "_id": "abc123",
    "body": "I want job",
    "resume": {
        "name": "Vansh Sharma",
        "skills": [
            {"category": "Languages",    "items": ["Python", "JavaScript"]},
            {"category": "Technologies", "items": ["FastAPI", "Docker", "Postgres"]},
        ],
        "experience": [
            {"company": "Freelance", "title": "Intern",
             "start": "2025-06", "end": "present", "highlights": []},
        ],
        "projects": [],
    },
}


def make_dbs(role_docs=None, resume_docs=None):
    r  = ResumeDB(FakeCol(copy.deepcopy(resume_docs or {"abc123": RESUME_DOC})))
    ro = RoleDB(FakeCol(copy.deepcopy(role_docs or {"junior-python-backend": ROLE_DOC})))
    return r, ro


# ── RoleDB ────────────────────────────────────────────────────────
class RoleDBTests(unittest.TestCase):
    def test_to_role_maps_fields(self):
        _, role_db = make_dbs()
        role = role_db.to_role(ROLE_DOC)
        self.assertEqual(role.title, "Junior Python Backend Engineer")
        self.assertEqual(len(role.required_skills), 3)
        self.assertEqual(role.required_skills[0].name, "python")
        self.assertEqual(role.required_skills[0].weight, 2.0)
        self.assertEqual(role.seniority, 1)
        self.assertEqual(role.min_years, 0.5)

    def test_defaults_when_fields_missing(self):
        doc = {"_id": "x", "title": "Dev", "required_skills": []}
        _, role_db = make_dbs()
        role = role_db.to_role(doc)
        self.assertEqual(role.seniority, 2)
        self.assertEqual(role.min_years, 0.0)

    def test_upsert_and_delete(self):
        _, role_db = make_dbs(role_docs={})
        role_db.upsert("r1", {"title": "Dev", "required_skills": []})
        self.assertIsNotNone(role_db.get("r1"))
        role_db.delete("r1")
        self.assertIsNone(role_db.get("r1"))

    def test_all_ids(self):
        _, role_db = make_dbs()
        self.assertIn("junior-python-backend", role_db.all_ids())


# ── ResumeDB ──────────────────────────────────────────────────────
class ResumeDBTests(unittest.TestCase):
    def test_save_result_written_nested(self):
        resume_db, _ = make_dbs()
        resume_db.save_result("abc123", "junior-python-backend", {"score": 88.5})
        doc = resume_db._col.docs["abc123"]
        self.assertEqual(doc["match"]["junior-python-backend"]["score"], 88.5)

    def test_find_unmatched_excludes_already_matched(self):
        already = {
            "abc123": {**RESUME_DOC, "match": {"junior-python-backend": {"score": 70}}},
            "def456": dict(RESUME_DOC),
        }
        resume_db, _ = make_dbs(resume_docs=already)
        unmatched = resume_db.find_unmatched("junior-python-backend")
        self.assertEqual(unmatched, ["def456"])

    def test_find_unmatched_returns_all_when_none_matched(self):
        resume_db, _ = make_dbs()
        unmatched = resume_db.find_unmatched("junior-python-backend")
        self.assertEqual(unmatched, ["abc123"])


# ── runner ────────────────────────────────────────────────────────
class RunnerTests(unittest.TestCase):
    def test_match_one_returns_result_and_persists(self):
        resume_db, role_db = make_dbs()
        result = match_one("abc123", "junior-python-backend", resume_db, role_db)
        self.assertIsNotNone(result)
        self.assertGreater(result["score"], 0)
        doc = resume_db._col.docs["abc123"]
        self.assertIn("junior-python-backend", doc.get("match", {}))

    def test_match_one_missing_role_returns_none(self):
        resume_db, role_db = make_dbs(role_docs={})
        self.assertIsNone(match_one("abc123", "ghost", resume_db, role_db))

    def test_match_one_missing_resume_returns_none(self):
        resume_db, role_db = make_dbs(resume_docs={})
        self.assertIsNone(match_one("ghost", "junior-python-backend", resume_db, role_db))

    def test_match_role_processes_unmatched(self):
        resume_docs = {"a": dict(RESUME_DOC), "b": dict(RESUME_DOC)}
        resume_db, role_db = make_dbs(resume_docs=resume_docs)
        # skip_existing=False: process everyone regardless
        stats = match_role("junior-python-backend", resume_db, role_db, skip_existing=False)
        self.assertEqual(stats.matched, 2)
        self.assertEqual(stats.errors, 0)

    def test_match_role_skips_already_matched(self):
        already = {"abc123": {**RESUME_DOC, "match": {"junior-python-backend": {"score": 50}}}}
        resume_db, role_db = make_dbs(resume_docs=already)
        stats = match_role("junior-python-backend", resume_db, role_db, skip_existing=True)
        self.assertEqual(stats.matched, 0)  # nothing unmatched → nothing processed

    def test_match_all_covers_every_role(self):
        role_docs = {
            "r1": {**ROLE_DOC, "_id": "r1"},
            "r2": {**ROLE_DOC, "_id": "r2"},
        }
        resume_db, role_db = make_dbs(role_docs=role_docs)
        all_stats = match_all(resume_db, role_db, skip_existing=False)
        self.assertEqual(set(all_stats.keys()), {"r1", "r2"})
        self.assertEqual(all_stats["r1"].matched, 1)
        self.assertEqual(all_stats["r2"].matched, 1)

    def test_match_all_bad_role_does_not_stop_good_ones(self):
        bad = {"_id": "bad", "title": "Bad", "required_skills": "not-a-list"}
        role_docs = {"good": ROLE_DOC, "bad": bad}
        resume_db, role_db = make_dbs(role_docs=role_docs)
        stats = match_all(resume_db, role_db, skip_existing=False)
        self.assertEqual(stats["good"].matched, 1)
        self.assertGreater(stats["bad"].errors, 0)


# ── full algo integration ─────────────────────────────────────────
class AlgoIntegrationTests(unittest.TestCase):
    def test_score_range(self):
        resume_db, role_db = make_dbs()
        result = match_one("abc123", "junior-python-backend", resume_db, role_db)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_breakdown_sums_to_score(self):
        resume_db, role_db = make_dbs()
        result = match_one("abc123", "junior-python-backend", resume_db, role_db)
        self.assertAlmostEqual(sum(result["breakdown"].values()), result["score"], delta=0.5)

    def test_no_meta_in_result(self):
        resume_db, role_db = make_dbs()
        result = match_one("abc123", "junior-python-backend", resume_db, role_db)
        self.assertNotIn("meta", result)

    def test_vansh_matches_python_role_well(self):
        resume_db, role_db = make_dbs()
        result = match_one("abc123", "junior-python-backend", resume_db, role_db)
        self.assertGreater(result["score"], 60)
        self.assertIn("python", result["matched_skills"])
        self.assertIn("fastapi", result["matched_skills"])


if __name__ == "__main__":
    unittest.main()
