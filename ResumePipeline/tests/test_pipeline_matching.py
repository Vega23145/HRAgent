from types import SimpleNamespace
from unittest.mock import patch

import pytest

from resumepipeline.resume_pipeline.config import Config
from resumepipeline.resume_pipeline.email import send_rejection
from resumepipeline.resume_pipeline.matching import RoleMatcher
from resumepipeline.resume_pipeline.pipeline import process_message


class MemoryStore:
    def __init__(self):
        self.records = {}
        self.jobs = []
        self.email_logs = []

    def has(self, key):
        return key in self.records

    def get(self, key):
        return self.records.get(key)

    def save(self, key, record):
        self.records[key] = record

    def log_rejection(self, job, email_log):
        self.jobs.append(job)
        self.email_logs.append(email_log)


class MemoryFiles:
    def __init__(self):
        self.files = {}

    def has(self, name):
        return name in self.files

    def write(self, name, payload):
        self.files[name] = payload

    def remove(self, name):
        self.files.pop(name, None)


def test_config_honors_legacy_mongo_db_with_hub_uri(monkeypatch):
    monkeypatch.setenv("HUB_MONGO_URI", "mongodb://mongo:27017")
    monkeypatch.delenv("HUB_MONGO_DB", raising=False)
    monkeypatch.setenv("MONGO_DB", "legacy_resumes")

    config = Config.from_env()

    assert config.mongo_db == "legacy_resumes"
    assert config.role_db == "legacy_resumes"
    assert config.role_collection == "roles"


def test_config_loads_project_env_file(monkeypatch, tmp_path):
    from resumepipeline.resume_pipeline import config as config_module

    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=dotenv-key\n"
        "IMAP_HOST=imap.example.com\n"
        "EMAIL_AUTO_REJECT_SCORE_THRESHOLD=37\n"
    )
    monkeypatch.setattr(config_module, "_ENV_FILE", env_file)
    for key in ("GEMINI_API_KEY", "IMAP_HOST", "EMAIL_AUTO_REJECT_SCORE_THRESHOLD"):
        monkeypatch.setenv(key, "temporary-value")
        monkeypatch.delenv(key)

    config = Config.from_env()

    assert config.gemini_api_key == "dotenv-key"
    assert config.imap_host == "imap.example.com"
    assert config.auto_reject_score_threshold == 37


def test_process_message_saves_role_scores_with_resume():
    role_documents = [{
        "_id": "python-backend",
        "title": "Junior Python Backend Engineer",
        "required_skills": [{"name": "python", "weight": 1}],
        "seniority": 1,
    }]
    role_collection = SimpleNamespace(find=lambda query: role_documents)
    matcher = RoleMatcher(role_collection)
    attachment = SimpleNamespace(filename="resume.pdf", payload=b"resume bytes")
    mail = SimpleNamespace(
        attachments=[attachment],
        message_id="message-1",
        sender="candidate@example.com",
        subject="Application",
        date="2026-10-09",
        body="",
    )
    contacts = SimpleNamespace(emails=[], phones=[], urls=[])
    resume = {
        "name": "Candidate",
        "skills": [{"category": "Languages", "items": ["Python"]}],
        "experience": [{"title": "Junior Backend Engineer", "start": "2025", "end": "present", "highlights": []}],
        "projects": [],
    }
    store, files = MemoryStore(), MemoryFiles()

    with (
        patch("resumepipeline.resume_pipeline.pipeline.parse_mail", return_value=mail),
        patch("resumepipeline.resume_pipeline.pipeline.read_text", return_value="A" * 100),
        patch("resumepipeline.resume_pipeline.pipeline.prepare", return_value=("A" * 100, contacts)),
    ):
        keys = process_message(
            b"raw email",
            lambda text: (resume, {}),
            store,
            files,
            matcher,
        )

    assert len(keys) == 1
    result = store.records[keys[0]]["match"]["python-backend"]
    assert 0 <= result["score"] <= 100
    assert result["matched_skills"] == ["python"]
    assert "breakdown" in result
    assert files.files[keys[0] + ".pdf"] == b"resume bytes"


def test_process_message_always_saves_match_field():
    attachment = SimpleNamespace(filename="resume.pdf", payload=b"resume bytes")
    mail = SimpleNamespace(
        attachments=[attachment],
        message_id="message-2",
        sender="candidate@example.com",
        subject="Application",
        date="2026-10-09",
        body="",
    )
    contacts = SimpleNamespace(emails=[], phones=[], urls=[])
    store, files = MemoryStore(), MemoryFiles()

    with (
        patch("resumepipeline.resume_pipeline.pipeline.parse_mail", return_value=mail),
        patch("resumepipeline.resume_pipeline.pipeline.read_text", return_value="A" * 100),
        patch("resumepipeline.resume_pipeline.pipeline.prepare", return_value=("A" * 100, contacts)),
    ):
        keys = process_message(b"raw email", lambda text: ({"name": "Candidate"}, {}), store, files)

    assert store.records[keys[0]]["match"] == {}


def test_auto_rejects_only_when_every_role_score_is_below_threshold(monkeypatch):
    monkeypatch.setenv("EMAIL_AUTO_REJECT_SCORE_THRESHOLD", "40")
    config = Config.from_env()
    attachment = SimpleNamespace(filename="resume.pdf", payload=b"resume bytes")
    mail = SimpleNamespace(
        attachments=[attachment],
        message_id="message-auto-reject",
        sender="candidate@example.com",
        subject="Application",
        date="2026-10-09",
        body="",
    )
    contacts = SimpleNamespace(emails=["candidate@example.com"], phones=[], urls=[])
    store, files = MemoryStore(), MemoryFiles()
    sends = []

    def failed_sender(cfg, **kwargs):
        sends.append(kwargs)
        raise RuntimeError("SMTP unavailable")

    with (
        patch("resumepipeline.resume_pipeline.pipeline.parse_mail", return_value=mail),
        patch("resumepipeline.resume_pipeline.pipeline.read_text", return_value="A" * 100),
        patch("resumepipeline.resume_pipeline.pipeline.prepare", return_value=("A" * 100, contacts)),
    ):
        with pytest.raises(RuntimeError, match="SMTP unavailable"):
            process_message(
                b"raw email",
                lambda text: ({"name": "Candidate"}, {}),
                store,
                files,
                matcher=lambda record: {"role-a": {"score": 39.9}, "role-b": {"score": 0}},
                email_config=config,
                email_sender=failed_sender,
            )
        key = next(iter(store.records))
        assert store.records[key]["rejection_email"] == {"status": "pending"}

        keys = [key]
        process_message(
            b"raw email",
            lambda text: ({}, {}),
            store,
            files,
            matcher=lambda record: {},
            email_config=config,
            email_sender=lambda cfg, **kwargs: sends.append(kwargs),
        )

    assert len(keys) == 1
    assert sends == [
        {
            "to_addr": "candidate@example.com",
            "candidate_name": "Candidate",
            "reason": "Your resume scored below the minimum match score of 40 for every role we reviewed.",
            "role_scores": [
                {"title": "Role A", "score": "39.9"},
                {"title": "Role B", "score": "0.0"},
            ],
        },
        {
            "to_addr": "candidate@example.com",
            "candidate_name": "Candidate",
            "reason": "Your resume scored below the minimum match score of 40 for every role we reviewed.",
            "role_scores": [
                {"title": "Role A", "score": "39.9"},
                {"title": "Role B", "score": "0.0"},
            ],
        },
    ]
    delivery = store.records[keys[0]]["rejection_email"]
    assert delivery["status"] == "sent"
    assert store.records[keys[0]]["status"] == "rejected"
    assert len(store.records[keys[0]]["email_history"]) == 1
    assert store.records[keys[0]]["email_history"][0]["action"] == "rejected"
    assert store.records[keys[0]]["email_history"][0]["job_id"] == delivery["job_id"]
    assert len(store.jobs) == 1
    assert store.jobs[0]["action"] == "rejected"
    assert store.email_logs[0]["candidate_email"] == "candidate@example.com"
    assert store.email_logs[0]["status"] == "sent"


def test_auto_rejection_does_not_send_when_any_role_meets_threshold(monkeypatch):
    from resumepipeline.resume_pipeline.pipeline import _all_role_scores_below

    assert not _all_role_scores_below({"role-a": {"score": 39}, "role-b": {"score": 40}}, 40)
    assert not _all_role_scores_below({"role-a": {"score": 39}, "role-b": {}}, 40)
    assert not _all_role_scores_below({}, 40)


def test_send_rejection_renders_mako_template_and_sends_synchronously(monkeypatch):
    from unittest.mock import MagicMock

    from resumepipeline.resume_pipeline import email

    smtp = MagicMock()
    monkeypatch.setattr(email.smtplib, "SMTP_SSL", MagicMock(return_value=smtp))
    smtp.__enter__.return_value = smtp
    config = SimpleNamespace(
        email_dry_run=False,
        email_smtp_user="sender@example.com",
        email_smtp_password="app-password",
        email_org_name="Example Org",
        email_sender_name="Hiring Team",
        email_smtp_tls=True,
        email_smtp_host="smtp.example.com",
        email_smtp_port=465,
    )

    send_rejection(
        config,
        to_addr="candidate@example.com",
        candidate_name="Candidate",
        reason="Your score was below 40 for every role.",
        role_scores=[{"title": "Backend Engineer", "score": "12.5"}],
    )

    message = smtp.send_message.call_args.args[0]
    body = message.get_content()
    assert message["To"] == "candidate@example.com"
    assert message["Subject"] == "Application update from Example Org"
    assert "Your score was below 40 for every role." in body
    assert "Backend Engineer: 12.5/100" in body