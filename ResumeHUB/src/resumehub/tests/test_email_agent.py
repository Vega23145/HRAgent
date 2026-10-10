import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bson import ObjectId
from fastapi.encoders import jsonable_encoder

from resumehub.app.core.deps import Page, Principal
from resumehub.app.modules.email_agent import router as email_router, worker as email_worker


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args):
        return self

    def skip(self, *_args):
        return self

    def limit(self, *_args):
        return self

    async def to_list(self):
        return self.documents


class FakeEmailCollection:
    def __init__(self, documents):
        self.documents = documents

    async def count_documents(self, _filter):
        return len(self.documents)

    def find(self, _filter):
        return FakeCursor(self.documents)


def test_job_log_response_serializes_mongo_object_ids(monkeypatch):
    object_id = ObjectId()
    monkeypatch.setattr(
        email_router,
        "_emails",
        lambda: FakeEmailCollection([{"_id": object_id, "job_id": "job-1"}]),
    )
    actor = Principal(id="user-1", email="user@example.com", full_name=None, roles=[])

    response = asyncio.run(email_router.job_log("job-1", None, Page(1, 20), actor))
    encoded = jsonable_encoder(response)

    assert encoded["items"][0]["_id"] == str(object_id)


def test_successful_rejection_email_marks_resume_rejected(monkeypatch):
    candidate = {
        "_id": "resume-1234",
        "resume": {"name": "Candidate"},
        "contact": {"emails": ["candidate@example.com"]},
    }
    update_one = AsyncMock()
    insert_one = AsyncMock()
    resumes = SimpleNamespace(find_one=AsyncMock(return_value=candidate), update_one=update_one)
    cfg = SimpleNamespace(dry_run=False, sender_name="Hiring", org_name="Example")
    monkeypatch.setattr(email_worker, "get_email_settings", lambda: cfg)
    monkeypatch.setattr(email_worker, "send", Mock())
    monkeypatch.setattr(email_worker.db, "resumes", lambda: resumes)
    monkeypatch.setattr(email_worker, "_emails", lambda: SimpleNamespace(insert_one=insert_one))

    result = asyncio.run(email_worker._send_one("job-1", candidate, {}, "rejected", {}))

    assert result["status"] == "sent"
    update_one.assert_awaited_once()
    update = update_one.await_args.args[1]
    assert update["$set"] == {"status": "rejected"}
    history_push = update["$push"]["email_history"]
    assert history_push["$sort"] == {"sent_at": 1}
    assert history_push["$each"][0]["action"] == "rejected"
    assert history_push["$each"][0]["status"] == "sent"
    insert_one.assert_awaited_once()