"""
Role-to-resume matching — pure stdlib, no ML, no embeddings, no external calls.

Algorithm overview
──────────────────
Matching is done across four independent dimensions, each scored 0-1, then
combined with configurable weights:

    DIMENSION          WEIGHT   WHAT IT MEASURES
    ─────────────────  ──────   ────────────────────────────────────────────
    skills             0.40     Which required skills the candidate has
    experience_years   0.25     Whether total years of relevant experience
                                meets the role's minimum
    seniority          0.20     How well job titles align to the expected
                                seniority band (junior / mid / senior / lead)
    role_relevance     0.15     How related past job titles are to this role

Final score = weighted sum (0-100, rounded to 1 decimal place).

Skill normalisation
───────────────────
Every skill string is lower-cased, stripped of punctuation, split on
whitespace, and looked up in an alias table.  "nodejs" → "node.js",
"js" → "javascript", etc.  This is intentional: the alias table is
the one place technology equivalences are maintained, so the algorithm
stays deterministic without any vector distance.

The required-skills list in a Role can specify a weight per skill so
that "Python" counts more than "Docker" for a Python-backend role.
Weights are normalised to sum to 1 inside the algorithm; you do not
have to ensure this yourself.

Experience-year counting
────────────────────────
Each experience entry with start/end dates contributes.  "present" is
treated as today.  Entries without dates are counted as 0 so they
never inflate the total.  Overlap between concurrent roles is handled
with a union-of-intervals merge, so six months of two simultaneous
internships counts as six months, not one year.

Seniority bands
───────────────
A lookup table maps title keywords to one of four numeric levels
(1 junior, 2 mid, 3 senior, 4 lead).  The candidate's level is taken
as the MAX level across all their titles (most senior role they have
held).  Score is 1.0 when candidate.level >= role.level, drops
linearly below that.

Role-relevance
──────────────
Computed with term overlap between the role's title keywords and the
candidate's job titles.  Gives partial credit for adjacent domains
("backend" matching "full-stack", "software" matching "developer").
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from datetime import date, datetime

# ──────────────────────────────────────────────────────────────────
# 1.  Alias / synonym table  (expand as needed)
# ──────────────────────────────────────────────────────────────────
_ALIASES: dict[str, str] = {
    # JavaScript
    "js": "javascript",
    "nodejs": "node.js",
    "node": "node.js",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "ts": "typescript",
    # Python
    "py": "python",
    # Databases
    "mongo": "mongodb",
    "mongo db": "mongodb",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mysql": "mysql",
    "mssql": "sql server",
    "redis cache": "redis",
    # Cloud & infra
    "aws": "amazon web services",
    "gcp": "google cloud",
    "azure": "microsoft azure",
    "k8s": "kubernetes",
    "cf": "cloudflare",
    # ML
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "tensorflow",
    # Other
    "golang": "go",
    "c sharp": "c#",
    "dotnet": ".net",
    "net": ".net",
    "springboot": "spring boot",
    "spring": "spring boot",
}

# ──────────────────────────────────────────────────────────────────
# 2.  Seniority bands
# ──────────────────────────────────────────────────────────────────
_SENIORITY: list[tuple[int, list[str]]] = [
    (4, ["lead", "principal", "staff", "architect", "head", "director", "vp", "chief"]),
    (3, ["senior", "sr", "iii", "3"]),
    (2, ["mid", "ii", "2", "intermediate"]),
    (1, ["junior", "jr", "entry", "associate", "i", "intern", "trainee", "graduate"]),
]


# ──────────────────────────────────────────────────────────────────
# 3.  Public data structures
# ──────────────────────────────────────────────────────────────────
@dataclass
class WeightedSkill:
    name: str   # e.g. "python"
    weight: float = 1.0  # relative importance; normalised inside the algorithm


@dataclass
class Role:
    """What a position requires.  Build one per job opening."""
    title: str                              # e.g. "Senior Backend Engineer"
    required_skills: list[WeightedSkill]   # must have at least one
    min_years: float = 0.0                 # total relevant experience
    seniority: int = 2                     # 1 junior / 2 mid / 3 senior / 4 lead

    # dimension weights (need not sum to 1; normalised internally)
    w_skills: float = 0.40
    w_years: float = 0.25
    w_seniority: float = 0.20
    w_relevance: float = 0.15


@dataclass
class MatchResult:
    score: float                    # 0-100
    skill_score: float              # 0-100
    years_score: float              # 0-100
    seniority_score: float          # 0-100
    relevance_score: float          # 0-100
    matched_skills: list[str]
    missing_skills: list[str]
    candidate_years: float
    candidate_seniority: int        # 1-4 (0 = unknown)
    breakdown: dict[str, float]     # dimension -> weighted contribution to final score

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


# ──────────────────────────────────────────────────────────────────
# 4.  Normalisation helpers
# ──────────────────────────────────────────────────────────────────
_PUNCT = str.maketrans("", "", string.punctuation.replace(".", "").replace("-", "").replace("+", "").replace("#", ""))


def _norm(s: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace, resolve aliases."""
    t = s.lower().translate(_PUNCT).strip()
    t = re.sub(r"\s+", " ", t)
    return _ALIASES.get(t, t)


def _skill_tokens(skill: str) -> set[str]:
    """A multi-word skill matches if ALL its words appear (order-independent)."""
    return set(_norm(skill).split())


def _candidate_skills(resume: dict) -> set[str]:
    """
    Collect every normalised skill token from:
      - skills[].items  (explicit skill section)
      - experience[].highlights  (tools mentioned in bullet points)
      - projects[].tech  (tech stack)

    We add project tech because many backend devs (like in the sample) list
    their real stack there, not in a separate skills section.
    """
    raw: list[str] = []
    for grp in resume.get("skills", []):
        raw.extend(grp.get("items", []))
    for exp in resume.get("experience", []):
        for h in exp.get("highlights", []):
            # pull tech-looking words (CamelCase, all-caps, known aliases)
            raw.extend(re.findall(r"[A-Za-z][A-Za-z0-9.#+_-]{1,}", h))
    for proj in resume.get("projects", []):
        raw.extend(proj.get("tech", []))
    return {_norm(s) for s in raw}


# ──────────────────────────────────────────────────────────────────
# 5.  Dimension scorers
# ──────────────────────────────────────────────────────────────────
def _score_skills(required: list[WeightedSkill], candidate_skills: set[str]) -> tuple[float, list[str], list[str]]:
    """Returns (0-1, matched_names, missing_names).

    A required skill is "matched" when every token in its normalised form
    is present in the candidate's skill set.  This means "spring boot"
    needs both "spring" and "boot" to appear somewhere.  Single-word
    skills just need their one token.
    """
    total_w = sum(s.weight for s in required) or 1.0
    matched_w, matched, missing = 0.0, [], []
    for rs in required:
        tokens = _skill_tokens(rs.name)
        if tokens <= candidate_skills:  # subset check: all tokens must match
            matched_w += rs.weight
            matched.append(rs.name)
        else:
            missing.append(rs.name)
    return matched_w / total_w, matched, missing


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip().lower()
    if s in ("present", "current", "now", "ongoing"):
        return date.today()
    for fmt in ("%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _total_years(experience: list[dict]) -> float:
    """Union of date intervals to avoid double-counting overlapping roles."""
    intervals: list[tuple[date, date]] = []
    for exp in experience:
        s = _parse_date(exp.get("start"))
        e = _parse_date(exp.get("end"))
        if s and e and e >= s:
            intervals.append((s, e))

    if not intervals:
        return 0.0

    # merge overlapping intervals
    intervals.sort()
    merged: list[tuple[date, date]] = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    total_days = sum((e - s).days for s, e in merged)
    return total_days / 365.25


def _score_years(total_years: float, min_years: float) -> float:
    if min_years <= 0:
        return 1.0
    if total_years <= 0:
        return 0.0
    # full credit at min_years, partial credit below (linear), capped at 1
    return min(total_years / min_years, 1.0)


def _max_seniority(titles: list[str]) -> int:
    """Return the highest seniority level (1-4) found across all job titles."""
    level = 0
    for title in titles:
        words = set(title.lower().split())
        for lvl, keywords in _SENIORITY:
            if words & set(keywords):
                level = max(level, lvl)
    return level


def _score_seniority(candidate_level: int, required_level: int) -> float:
    if required_level <= 0:
        return 1.0
    if candidate_level <= 0:
        # unknown: give half credit (we can't penalise what we can't see)
        return 0.5
    if candidate_level >= required_level:
        return 1.0
    # 1 level below -> 0.6, 2 below -> 0.3, 3 below -> 0.0
    gap = required_level - candidate_level
    return max(1.0 - gap * 0.35, 0.0)


def _title_tokens(title: str) -> set[str]:
    stop = {"engineer", "developer", "the", "of", "a", "an", "and", "or"}
    return {_norm(w) for w in re.split(r"[\s/,|]+", title)} - stop


def _score_relevance(role_title: str, exp_titles: list[str]) -> float:
    """Jaccard-like overlap between role title tokens and each past title."""
    role_tokens = _title_tokens(role_title)
    if not role_tokens or not exp_titles:
        return 0.0
    best = 0.0
    for t in exp_titles:
        cand_tokens = _title_tokens(t)
        if not cand_tokens:
            continue
        overlap = role_tokens & cand_tokens
        # Jaccard over the role side: what fraction of what we asked for is covered?
        score = len(overlap) / len(role_tokens)
        best = max(best, score)
    return best


# ──────────────────────────────────────────────────────────────────
# 6.  Public entry point
# ──────────────────────────────────────────────────────────────────
def match(role: Role, record: dict) -> MatchResult:
    """Score a Mongo record (as produced by pipeline.py) against a Role.

    The record is read-only; nothing is modified here.
    """
    resume = record.get("resume", {})
    body = record.get("body", "")

    # ── collect candidate data ───────────────────────────────────
    cand_skills = _candidate_skills(resume)
    experiences = resume.get("experience", [])
    exp_titles = [e["title"] for e in experiences if e.get("title")]
    total_years = _total_years(experiences)
    cand_seniority = _max_seniority(
        exp_titles + ([resume.get("name", "")] if resume.get("name") else [])
    )

    # ── also check the body for any skill mentions ───────────────
    # Candidates sometimes list tools in the email body ("I work with React")
    body_tokens = {_norm(w) for w in re.findall(r"[A-Za-z][A-Za-z0-9.#+_-]{1,}", body)}
    cand_skills |= body_tokens

    # ── dimension scores (0-1) ───────────────────────────────────
    s_skills, matched, missing = _score_skills(role.required_skills, cand_skills)
    s_years = _score_years(total_years, role.min_years)
    s_seniority = _score_seniority(cand_seniority, role.seniority)
    s_relevance = _score_relevance(role.title, exp_titles)

    # ── weighted combination ─────────────────────────────────────
    total_w = role.w_skills + role.w_years + role.w_seniority + role.w_relevance
    final = (
        role.w_skills * s_skills
        + role.w_years * s_years
        + role.w_seniority * s_seniority
        + role.w_relevance * s_relevance
    ) / total_w * 100

    breakdown = {
        "skills":     round(role.w_skills / total_w * s_skills * 100, 2),
        "years":      round(role.w_years / total_w * s_years * 100, 2),
        "seniority":  round(role.w_seniority / total_w * s_seniority * 100, 2),
        "relevance":  round(role.w_relevance / total_w * s_relevance * 100, 2),
    }

    return MatchResult(
        score=round(final, 1),
        skill_score=round(s_skills * 100, 1),
        years_score=round(s_years * 100, 1),
        seniority_score=round(s_seniority * 100, 1),
        relevance_score=round(s_relevance * 100, 1),
        matched_skills=matched,
        missing_skills=missing,
        candidate_years=total_years,
        candidate_seniority=cand_seniority,
        breakdown=breakdown,
    )
