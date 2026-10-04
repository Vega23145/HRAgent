# resume-matcher

Standalone module that reads resumes and roles from MongoDB and writes
match scores back into each resume document.  No dependency on the
resume-pipeline package.

```
                     ┌──────────────────────────┐
  roles collection   │  RoleDB.to_role()         │
  ───────────────►   │                           │
                     │  algo.match()             │──► resume_doc["match"][role_id]
  resumes collection │                           │
  ───────────────►   │  ResumeDB.save_result()   │
                     └──────────────────────────┘
```

## Module layout

| file | responsibility |
|---|---|
| `algo.py` | pure matching algorithm — no I/O |
| `db.py` | `ResumeDB`, `RoleDB` — thin wrappers over pymongo collections |
| `runner.py` | `match_one`, `match_role`, `match_all` — orchestration |
| `config.py` | env-var config |
| `__main__.py` | CLI |

## Install

```
uv sync
```
cp .env.example .env   # fill in Mongo URIs
```

## CLI

```bash
# add a role
uv run -m resumehub.app.role_engine.resume_matcher roles add role.json

# score all resumes against one role (skips already-matched)
uv run -m resumehub.app.role_engine.resume_matcher run-role junior-python-backend

# force re-score
uv run -m resumehub.app.role_engine.resume_matcher run-role junior-python-backend --overwrite

# score everything against every stored role
uv run -m resumehub.app.role_engine.resume_matcher run-all

# score one resume against one role and print the result
uv run -m resumehub.app.role_engine.resume_matcher run-one abc123 junior-python-backend

# top 10 matches for a role
uv run -m resumehub.app.role_engine.resume_matcher top junior-python-backend --n 10

# manage roles
uv run -m resumehub.app.role_engine.resume_matcher roles list
uv run -m resumehub.app.role_engine.resume_matcher roles show junior-python-backend
uv run -m resumehub.app.role_engine.resume_matcher roles rm  junior-python-backend
```

## Role JSON format

```json
{
  "_id": "junior-python-backend",
  "title": "Junior Python Backend Engineer",
  "description": "Entry-level backend role focused on developing APIs and backend services using Python.",
  "department": "Engineering",
  "team": "Backend Engineering",
  "employment_type": "full-time",
  "work_mode": "hybrid",
  "experience_level": "junior",

  "responsibilities": [
    "Develop and maintain REST APIs",
    "Build backend services using Python",
    "Work with relational databases",
    "Write unit tests and debug backend issues",
    "Participate in code reviews"
  ],

  "tech_stack": [
    "Python",
    "FastAPI",
    "PostgreSQL",
    "Docker",
    "Git"
  ],

  "nice_to_have": [
    "SQLAlchemy",
    "pytest",
    "Redis",
    "AWS"
  ],

  "required_skills": [
    {"name": "python", "weight": 2.0},
    {"name": "fastapi", "weight": 1.5},
    {"name": "postgresql", "weight": 1.0},
    {"name": "docker", "weight": 1.0}
  ],

  "min_years": 0.5,
  "seniority": 1,
  "w_skills": 0.40,
  "w_years": 0.25,
  "w_seniority": 0.20,
  "w_relevance": 0.15
}
```

`seniority`: 1 junior / 2 mid / 3 senior / 4 lead  
`w_*`: dimension weights (need not sum to 1; normalised internally)

## Match result (stored in resume doc)

```json
"match": {
  "junior-python-backend": {
    "score": 90.0,
    "skill_score": 100.0,
    "years_score": 100.0,
    "seniority_score": 100.0,
    "relevance_score": 33.3,
    "matched_skills": ["python", "fastapi", "postgresql", "docker"],
    "missing_skills": [],
    "candidate_years": 1.2,
    "candidate_seniority": 1,
    "breakdown": {
      "skills": 40.0, "years": 25.0,
      "seniority": 20.0, "relevance": 5.0
    }
  }
}
```

## Use from code
Public API to be called by the backend to server the Client Requests.

```python
from resumehub.app.role_engine.resume_matcher.config import Config
from resumehub.app.role_engine.resume_matcher.db import connect
from resumehub.app.role_engine.resume_matcher.runner import match_one, match_role, match_all

cfg = Config.from_env()
resume_db, role_db = connect(cfg)

# one resume, one role
result = match_one("abc123", "junior-python-backend", resume_db, role_db)

# all resumes, one role
stats = match_role("junior-python-backend", resume_db, role_db)

# everything
stats = match_all(resume_db, role_db)
```

## Tests (offline, no Mongo needed)

```
uv run pytest src/hragent/resume_hub/app/role_engine/tests
```
