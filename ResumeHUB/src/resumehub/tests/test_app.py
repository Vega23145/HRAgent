"""Smoke tests that need no database (the lifespan, and so Mongo, is not started)."""
import pytest
from fastapi.testclient import TestClient

from resumehub.app.core.config import Settings
from resumehub.app.core.loader import discover
from resumehub.app.main import create_app


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


def test_admin_ui_served_with_csp(client):
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/admin/app.js").status_code == 200


def test_prod_refuses_default_secrets():
    with pytest.raises(RuntimeError, match="Refusing to start"):
        Settings(_env_file=None, env="prod").validate_for_env()
