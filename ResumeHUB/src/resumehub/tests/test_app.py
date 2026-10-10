"""Smoke tests that need no database (the lifespan, and so Mongo, is not started)."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from fastapi.testclient import TestClient

from resumehub.app.core.config import Settings
from resumehub.app.core.deps import Principal
from resumehub.app.core.loader import discover
from resumehub.app.main import create_app
from resumehub.app.modules.resumes import router as resumes_router
from resumehub.app.modules.resumes.router import _summary


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(Settings(env="dev")))


def test_all_modules_discovered_in_dependency_order():
    names = tuple(m.name for m in discover(Settings()))
    print(names)
    assert set(names) == {'admin', 'users', 'auth', 'resumes', 'email_agent', 'job_roles', 'matching', 'task_review'}
    assert names.index("users") < names.index("auth")
    assert names.index("resumes") < names.index("matching")


def test_disabling_a_module_keeps_always_on_ones():
    names = {m.name for m in discover(Settings(enabled_modules=["resumes"]))}
    assert names == {"auth", "users", "resumes"}


def test_matching_without_its_dependencies_fails_loudly():
    with pytest.raises(RuntimeError, match="depends on missing"):
        discover(Settings(enabled_modules=["matching"]))


def test_openapi_builds_and_lists_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/auth/login", "/api/v1/resumes", "/api/v1/job-roles", "/api/v1/users",
              "/api/v1/access-roles", "/api/v1/matching/run-all", "/api/v1/admin/manifest"):
        assert p in paths


@pytest.mark.parametrize("path", [
    "/api/v1/resumes", "/api/v1/job-roles", "/api/v1/users", "/api/v1/access-roles",
    "/api/v1/permissions", "/api/v1/matching/jobs", "/api/v1/admin/stats", "/api/v1/auth/me",
])
def test_protected_routes_require_auth(client, path):
    assert client.get(path).status_code == 401


def test_bad_token_is_rejected(client):
    r = client.get("/api/v1/resumes", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_resume_summary_includes_candidate_details_and_matches():
    doc = {
        "_id": "resume-1234",
        "status": "rejected",
        "email_history": [
            {"action": "interview", "sent_at": "2026-10-09T12:00:00Z", "status": "sent", "subject": "Private"}
        ],
        "resume": {
            "name": "Candidate",
            "skills": [{"category": "Languages", "items": ["Python"]}],
            "experience": [{"title": "Engineer", "company": "Example"}],
        },
        "match": {"backend-engineer": {"score": 87, "matched_skills": ["Python"]}},
    }

    summary = _summary(doc, pii=False)

    assert summary["resume"]["skills"] == doc["resume"]["skills"]
    assert summary["resume"]["experience"] == doc["resume"]["experience"]
    assert summary["status"] == "rejected"
    assert summary["match"] == doc["match"]
    assert summary["scores"] == {"backend-engineer": 87}
    assert summary["email_history"] == [
        {"action": "interview", "sent_at": "2026-10-09T12:00:00Z", "status": "sent", "role_id": None, "task_id": None}
    ]


def test_discard_resume_removes_linked_submissions_and_file(monkeypatch, tmp_path):
    resume_file = tmp_path / "candidate.pdf"
    resume_file.write_bytes(b"resume")
    resume_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"resume_file": resume_file.name}),
        delete_one=AsyncMock(return_value=SimpleNamespace(deleted_count=1)),
    )
    submissions = SimpleNamespace(delete_many=AsyncMock(return_value=SimpleNamespace(deleted_count=2)))
    monkeypatch.setattr(resumes_router.db, "resumes", lambda: resume_collection)
    monkeypatch.setattr(resumes_router.db, "get_db", lambda: {"task_submissions": submissions})
    monkeypatch.setattr(resumes_router, "get_settings", lambda: SimpleNamespace(resume_files_dir=str(tmp_path)))
    audit = AsyncMock()
    monkeypatch.setattr(resumes_router, "audit", audit)
    request = Request({"type": "http", "method": "DELETE", "path": "/api/v1/resumes/resume-1234"})
    actor = Principal(id="user-1", email="user@example.com", full_name=None, roles=[])

    response = asyncio.run(resumes_router.delete_resume("resume-1234", request, actor))

    assert response.status_code == 204
    resume_collection.delete_one.assert_awaited_once_with({"_id": "resume-1234"})
    submissions.delete_many.assert_awaited_once_with({"candidate_id": "resume-1234"})
    assert not Path(resume_file).exists()
    assert audit.await_args.args[4] == {"task_submissions_deleted": 2}


def test_admin_ui_served_with_csp(client):
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/admin/app.js").status_code == 200


def test_prod_refuses_default_secrets():
    with pytest.raises(RuntimeError, match="Refusing to start"):
        Settings(_env_file=None, env="prod").validate_for_env()
