"""Deterministic role matching adapted from ResumeHUB's role matcher."""
from __future__ import annotations

import logging
import re
import string
from dataclasses import dataclass
from datetime import date, datetime

log = logging.getLogger(__name__)

_ALIASES = {
    "js": "javascript",
    "nodejs": "node.js",
    "node": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "ts": "typescript",
    "py": "python",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mssql": "sql server",
    "redis cache": "redis",
    "aws": "amazon web services",
    "gcp": "google cloud",
    "azure": "microsoft azure",
    "k8s": "kubernetes",
    "cf": "cloudflare",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "tensorflow",
    "golang": "go",
    "c sharp": "c#",
    "dotnet": ".net",
    "net": ".net",
    "springboot": "spring boot",
    "spring": "spring boot",
}
_SENIORITY = [
    (4, ["lead", "principal", "staff", "architect", "head", "director", "vp", "chief"]),
    (3, ["senior", "sr", "iii", "3"]),
    (2, ["mid", "ii", "2", "intermediate"]),
    (1, ["junior", "jr", "entry", "associate", "i", "intern", "trainee", "graduate"]),
]
_PUNCT = str.maketrans("", "", string.punctuation.replace(".", "").replace("-", "").replace("+", "").replace("#", ""))


@dataclass
class WeightedSkill:
    name: str
    weight: float = 1.0


@dataclass
class Role:
    title: str
    required_skills: list[WeightedSkill]
    min_years: float = 0.0
    seniority: int = 2
    w_skills: float = 0.40
    w_years: float = 0.25
    w_seniority: float = 0.20
    w_relevance: float = 0.15


@dataclass
class MatchResult:
    score: float
    skill_score: float
    years_score: float
    seniority_score: float
    relevance_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    candidate_years: float
    candidate_seniority: int
    breakdown: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "skill_score": self.skill_score,
            "years_score": self.years_score,
            "seniority_score": self.seniority_score,
            "relevance_score": self.relevance_score,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "candidate_years": round(self.candidate_years, 1),
            "candidate_seniority": self.candidate_seniority,
            "breakdown": self.breakdown,
        }


def _norm(value: str) -> str:
    normalized = value.lower().translate(_PUNCT).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return _ALIASES.get(normalized, normalized)


def _candidate_skills(resume: dict) -> set[str]:
    raw = [item for group in resume.get("skills", []) for item in group.get("items", [])]
    for experience in resume.get("experience", []):
        for highlight in experience.get("highlights", []):
            raw.extend(re.findall(r"[A-Za-z][A-Za-z0-9.#+_-]{1,}", highlight))
    for project in resume.get("projects", []):
        raw.extend(project.get("tech", []))
    return {_norm(skill) for skill in raw}


def _score_skills(required: list[WeightedSkill], candidate_skills: set[str]) -> tuple[float, list[str], list[str]]:
    total_weight = sum(skill.weight for skill in required) or 1.0
    matched_weight = 0.0
    matched, missing = [], []
    for skill in required:
        if set(_norm(skill.name).split()) <= candidate_skills:
            matched_weight += skill.weight
            matched.append(skill.name)
        else:
            missing.append(skill.name)
    return matched_weight / total_weight, matched, missing


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip().lower()
    if value in ("present", "current", "now", "ongoing"):
        return date.today()
    for fmt in ("%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _total_years(experience: list[dict]) -> float:
    intervals = []
    for item in experience:
        start, end = _parse_date(item.get("start")), _parse_date(item.get("end"))
        if start and end and end >= start:
            intervals.append((start, end))
    if not intervals:
        return 0.0
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return sum((end - start).days for start, end in merged) / 365.25


def _max_seniority(titles: list[str]) -> int:
    level = 0
    for title in titles:
        words = set(title.lower().split())
        for seniority, keywords in _SENIORITY:
            if words & set(keywords):
                level = max(level, seniority)
    return level


def _title_tokens(title: str) -> set[str]:
    stop = {"engineer", "developer", "the", "of", "a", "an", "and", "or"}
    return {_norm(word) for word in re.split(r"[\s/,|]+", title)} - stop


def _score_relevance(role_title: str, experience_titles: list[str]) -> float:
    role_tokens = _title_tokens(role_title)
    if not role_tokens or not experience_titles:
        return 0.0
    return max(
        (len(role_tokens & _title_tokens(title)) / len(role_tokens) for title in experience_titles),
        default=0.0,
    )


def role_from_document(document: dict) -> Role:
    """Convert a ResumeHUB role document to the matcher model."""
    return Role(
        title=document["title"],
        required_skills=[
            WeightedSkill(skill["name"], float(skill.get("weight", 1.0)))
            for skill in document.get("required_skills", [])
        ],
        min_years=float(document.get("min_years", 0)),
        seniority=int(document.get("seniority", 2)),
        w_skills=float(document.get("w_skills", 0.40)),
        w_years=float(document.get("w_years", 0.25)),
        w_seniority=float(document.get("w_seniority", 0.20)),
        w_relevance=float(document.get("w_relevance", 0.15)),
    )


def match(role: Role, record: dict) -> MatchResult:
    """Score a pipeline record against a ResumeHUB role."""
    resume = record.get("resume", {})
    experiences = resume.get("experience", [])
    titles = [item["title"] for item in experiences if item.get("title")]
    candidate_skills = _candidate_skills(resume)
    candidate_skills.update(
        _norm(word)
        for word in re.findall(r"[A-Za-z][A-Za-z0-9.#+_-]{1,}", record.get("body", ""))
    )
    years = _total_years(experiences)
    seniority = _max_seniority(titles + ([resume["name"]] if resume.get("name") else []))
    skill_score, matched, missing = _score_skills(role.required_skills, candidate_skills)
    years_score = 1.0 if role.min_years <= 0 else min(years / role.min_years, 1.0)
    if role.seniority <= 0:
        seniority_score = 1.0
    elif seniority <= 0:
        seniority_score = 0.5
    else:
        seniority_score = 1.0 if seniority >= role.seniority else max(1.0 - (role.seniority - seniority) * 0.35, 0.0)
    relevance_score = _score_relevance(role.title, titles)
    total_weight = role.w_skills + role.w_years + role.w_seniority + role.w_relevance
    if total_weight <= 0:
        raise ValueError("role dimension weights must sum to more than zero")
    weighted = {
        "skills": role.w_skills / total_weight * skill_score * 100,
        "years": role.w_years / total_weight * years_score * 100,
        "seniority": role.w_seniority / total_weight * seniority_score * 100,
        "relevance": role.w_relevance / total_weight * relevance_score * 100,
    }
    return MatchResult(
        score=round(sum(weighted.values()), 1),
        skill_score=round(skill_score * 100, 1),
        years_score=round(years_score * 100, 1),
        seniority_score=round(seniority_score * 100, 1),
        relevance_score=round(relevance_score * 100, 1),
        matched_skills=matched,
        missing_skills=missing,
        candidate_years=years,
        candidate_seniority=seniority,
        breakdown={dimension: round(value, 2) for dimension, value in weighted.items()},
    )


class RoleMatcher:
    """Scores records against the current documents in ResumeHUB's roles collection."""

    def __init__(self, role_collection):
        self._role_collection = role_collection

    def __call__(self, record: dict) -> dict[str, dict]:
        results = {}
        for document in self._role_collection.find({}):
            role_id = document.get("_id")
            try:
                results[role_id] = match(role_from_document(document), record).to_dict()
            except Exception:
                log.exception("could not match resume against role %s", role_id)
        return results

    @classmethod
    def connect(cls, uri: str, database: str, collection: str) -> "RoleMatcher":
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        matcher = cls(client[database][collection])
        matcher._client = client
        return matcher

    def close(self) -> None:
        client = getattr(self, "_client", None)
        if client is not None:
            client.close()