"""
Two Mongo collections: one for resumes, one for roles.

Role document shape (stored in ROLE_MONGO_COLLECTION):
{
  "_id":              "senior-python-backend",       # slug, your choice
  "title":            "Senior Python Backend Engineer",
  "required_skills":  [{"name": "python", "weight": 2.0}, ...],
  "min_years":        3.0,
  "seniority":        3,                             # 1 junior 2 mid 3 senior 4 lead
  "w_skills":         0.40,                          # dimension weights (optional)
  "w_years":          0.25,
  "w_seniority":      0.20,
  "w_relevance":      0.15
}

Resume document shape: produced by resume_pipeline; must have a "resume" sub-doc
with the fields the algo reads (skills, experience, projects) and optionally "body".
"""
from __future__ import annotations

from .algo import Role, WeightedSkill


class ResumeDB:
    def __init__(self, col):
        self._col = col

    def get(self, key: str) -> dict | None:
        return self._col.find_one({"_id": key})

    def all_keys(self) -> list[str]:
        return [d["_id"] for d in self._col.find({}, {"_id": 1})]

    def find_unmatched(self, role_id: str) -> list[str]:
        """Keys of resumes that have not yet been matched against this role."""
        return [
            d["_id"]
            for d in self._col.find(
                {f"match.{role_id}": {"$exists": False}}, {"_id": 1}
            )
        ]

    def save_result(self, resume_key: str, role_id: str, result: dict) -> None:
        """Write (or overwrite) the match result into the resume document."""
        self._col.update_one(
            {"_id": resume_key},
            {"$set": {f"match.{role_id}": result}},
        )


class RoleDB:
    def __init__(self, col):
        self._col = col

    # ── read ──────────────────────────────────────────────────────
    def get(self, role_id: str) -> dict | None:
        return self._col.find_one({"_id": role_id})

    def all_ids(self) -> list[str]:
        return [d["_id"] for d in self._col.find({}, {"_id": 1})]

    def to_role(self, doc: dict) -> Role:
        """Convert a stored role document into the algo's Role dataclass."""
        skills = [
            WeightedSkill(s["name"], float(s.get("weight", 1.0)))
            for s in doc.get("required_skills", [])
        ]
        return Role(
            title=doc["title"],
            required_skills=skills,
            min_years=float(doc.get("min_years", 0)),
            seniority=int(doc.get("seniority", 2)),
            w_skills=float(doc.get("w_skills", 0.40)),
            w_years=float(doc.get("w_years", 0.25)),
            w_seniority=float(doc.get("w_seniority", 0.20)),
            w_relevance=float(doc.get("w_relevance", 0.15)),
        )

    # ── write ─────────────────────────────────────────────────────
    def upsert(self, role_id: str, doc: dict) -> None:
        self._col.replace_one({"_id": role_id}, {"_id": role_id, **doc}, upsert=True)

    def delete(self, role_id: str) -> None:
        self._col.delete_one({"_id": role_id})


def connect(cfg) -> tuple[ResumeDB, RoleDB]:
    """Open both connections. Ping-test both before returning."""
    from pymongo import MongoClient

    r_client = MongoClient(cfg.resume_uri, serverSelectionTimeoutMS=5000)
    r_client.admin.command("ping")
    resume_db = ResumeDB(r_client[cfg.resume_db][cfg.resume_col])

    if cfg.role_uri == cfg.resume_uri:
        role_col = r_client[cfg.role_db][cfg.role_col]
    else:
        ro_client = MongoClient(cfg.role_uri, serverSelectionTimeoutMS=5000)
        ro_client.admin.command("ping")
        role_col = ro_client[cfg.role_db][cfg.role_col]

    role_db = RoleDB(role_col)
    return resume_db, role_db
