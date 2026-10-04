# Resume Hub

Modular FastAPI backend over MongoDB: CRUD for `resumes` and `roles`, the `resume_matcher`
service, role-based access with fine-grained permissions, and an admin panel.

```
app/
  main.py              create_app(): discovers modules, mounts routers, security headers
  core/                the plugin kernel (no business logic)
    plugin.py          Module base class, AdminResource, AppContext
    loader.py          discovery (app/modules/* + entry points), dependency order, mounting
    permissions.py     resource:action matching, wildcards, deny-beats-allow
    deps.py            get_principal(), require("res:action"), pagination
    security.py        argon2 hashing, JWT access/refresh
    audit.py           append-only audit trail
  modules/
    auth/       login, refresh, logout (revokes all tokens), change-password, /me
    users/      users + access roles (RBAC) + permission catalog
    job_roles/  CRUD on the `roles` collection (validated schema)
    resumes/    CRUD, search, PII redaction, file download
    matching/   wraps resume_matcher: single (sync), per-role / all (background jobs), leaderboards
    admin/      /admin UI, /admin/manifest, /admin/stats, audit log
```

## Run

```bash
uv sync
cp .env.example .env                      # then edit
PYTHONPATH=src/hragent/resume_hub uv run uvicorn app.main:app --reload
```

First start creates the roles `admin` / `recruiter` / `viewer` and, if there are no users, an
admin from `HUB_BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD`. Admin UI: `http://localhost:8000/admin/`,
API docs: `/docs`. With `HUB_ENV=prod` the app refuses to start on default secrets.

The parser and matcher use the same `HUB_MONGO_*` variables as the API.

## Permissions

`resource:action`, with wildcards `*`, `resumes:*`, `*:read`. Effective access =
(permissions of the user's roles + the user's `grants`) minus the user's `denies`; **deny always wins**.

| Resource | Actions |
|---|---|
| `resumes` | `read`, `read_pii`, `create`, `update`, `delete`, `download` |
| `job_roles` | `read`, `create`, `update`, `delete` |
| `matching` | `read`, `run`, `run_bulk`, `manage` |
| `users` | `read`, `create`, `update`, `delete`, `assign` |
| `access_roles` | `read`, `create`, `update`, `delete` |
| `admin` | `access`, `audit` |

`resumes:read_pii` is the field-level control: without it, contact details, the raw mail body and
the sender are removed from responses, excluded from search, and cannot be written.

Anti-escalation rules: you can only grant permissions you hold; you cannot edit or delete a user
or role that holds permissions you lack; you cannot change your own roles/grants/denies/active
flag; the last active administrator cannot be removed; built-in roles cannot be deleted and
`admin` is pinned to `*`.

## Endpoints (all under `/api/v1`)

- `POST /auth/login` (form: username=email, password), `/auth/refresh`, `/auth/logout`, `/auth/change-password`, `GET /auth/me`
- `/resumes` list (`q, skill, role, min_score, has_match, sort, page, size`) / `POST` / `GET|PUT|PATCH|DELETE /{id}` / `GET /{id}/file`
- `/job-roles` list / `POST` / `GET|PUT|PATCH|DELETE /{id}` (`?purge_matches=true` also clears stored matches)
- `POST /matching/resumes/{resume}/roles/{role}`, `POST /matching/roles/{role}/run`, `POST /matching/run-all`,
  `GET /matching/jobs[/{id}]`, `GET /matching/roles/{role}/leaderboard`, `GET /matching/resumes/{id}`
- `/users`, `/access-roles`, `GET /permissions`
- `GET /admin/manifest|stats|audit`

`match` is owned by the matcher: it cannot be set through the resume endpoints, and `PUT` preserves it.
Role documents are stored exactly as the schema defines (no extra metadata fields); change history
lives in the audit log. Editing a role does not recompute stored scores: re-run matching.

## Adding a module

Create `app/modules/notes/` (any folder not starting with `_` is discovered), or ship it as a
separate package with an entry point in group `resume_hub.modules`.

```python
# app/modules/notes/__init__.py
from .plugin import module  # noqa: F401

# app/modules/notes/plugin.py
from fastapi import APIRouter, Depends
from app.core.deps import require
from app.core.plugin import AdminResource, Module

router = APIRouter()

@router.get("")
async def list_notes(_=Depends(require("notes:read"))):
    return {"items": [], "total": 0, "page": 1, "size": 20}

class Notes(Module):
    name = "notes"                       # mounted at /api/v1/notes
    depends_on = ("resumes",)            # optional; load order + fail-fast if missing
    permissions = {"notes:read": "Read notes"}   # appears in the catalog, role editor and /me
    admin_resources = (AdminResource(    # appears in the admin panel with no UI code
        key="notes", label="Notes", endpoint="/notes",
        columns=(("Id", "_id"),), read="notes:read"),)
    def router(self): return router
    # also optional: ensure_indexes, on_startup, on_shutdown, stats, mounts

module = Notes()
```

Restrict what runs with `HUB_ENABLED_MODULES='["resumes","job_roles","matching","admin"]'`
(`auth` and `users` are always on). A module whose dependency is disabled fails at startup, not at request time.
The `admin` role picks up new permissions automatically (`*`); grant them to other roles in the panel.

## Notes for production

- The admin UI keeps tokens in `sessionStorage` and renders all data as text nodes under a strict CSP
  (no inline script/style). Resume content comes from inbound email, so treat it as untrusted.
- Login throttling is per process; add gateway or Redis rate limiting when running several workers.
- Bulk matching runs in the worker that accepted the request, tracked in `match_jobs`; jobs left
  `running` by a crash are marked failed on the next start. Overlapping jobs are rejected (409);
  that check is not atomic across workers.
- Access tokens carry the user's `token_version`; logout, password change and admin password reset
  bump it, which revokes all outstanding tokens at once.
- Mongo access uses PyMongo's native `AsyncMongoClient` (Motor is deprecated).
- `pytest` runs database-free smoke tests (discovery, auth gating, CSP, permission logic).
