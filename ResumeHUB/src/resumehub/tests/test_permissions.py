from resumehub.app.core.permissions import covers, effective, is_allowed


def test_exact_and_wildcards():
    assert covers("resumes:read", "resumes:read")
    assert not covers("resumes:read", "resumes:update")
    assert covers("resumes:*", "resumes:delete")
    assert not covers("resumes:*", "job_roles:read")
    assert covers("*:read", "job_roles:read")
    assert not covers("*:read", "job_roles:update")
    assert covers("*", "anything:at_all")


def test_coverage_is_not_symmetric():
    # holding resumes:read does not let you hand out resumes:*
    assert not covers("resumes:read", "resumes:*")
    assert not covers("resumes:*", "*:read")
    assert covers("*", "resumes:*")


def test_deny_beats_allow():
    allow = {"*"}
    deny = {"resumes:delete"}
    assert is_allowed("resumes:read", allow, deny)
    assert not is_allowed("resumes:delete", allow, deny)
    assert not is_allowed("resumes:delete", {"resumes:*"}, {"resumes:delete"})


def test_default_deny():
    assert not is_allowed("resumes:read", set(), set())


def test_effective_expansion():
    cat = ["resumes:read", "resumes:delete", "users:read"]
    assert effective(cat, {"resumes:*"}, {"resumes:delete"}) == ["resumes:read"]
