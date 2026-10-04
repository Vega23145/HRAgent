from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator

from resumehub.app.core.utils import SLUG_PATTERN

TaskId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{3,63}$")]
RoleId = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]


class TaskCreate(BaseModel):
    """Recruiter creates a hiring task for a role."""

    model_config = ConfigDict(extra="forbid")

    role_id: RoleId
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    instructions: str = Field("", max_length=5000)
    # optional: close submissions after this ISO datetime string
    deadline: str | None = Field(None, max_length=32)
    is_open: bool = True  # recruiter can close submissions without deleting the task


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1, max_length=5000)
    instructions: str | None = Field(None, max_length=5000)
    deadline: str | None = None
    is_open: bool | None = None


URL = Annotated[str, StringConstraints(min_length=5, max_length=500)]


class SubmissionCreate(BaseModel):
    """Candidate submits their work for a hiring task."""

    model_config = ConfigDict(extra="forbid")

    # identity
    candidate_id: str = Field(min_length=1, max_length=64,
                              description="The resume _id stored in the resumes collection")
    candidate_name: str = Field(min_length=1, max_length=120)
    candidate_email: str | None = Field(None, max_length=254)

    # deliverables
    demo_video_url: URL = Field(description="Google Drive / Loom / YouTube link of the demo video")
    project_url: URL | None = Field(None, description="Live / deployed project URL")
    repo_url: URL | None = Field(None, description="GitHub / GitLab repository URL")
    notes: str = Field("", max_length=3000, description="Free-text response from the candidate")

    @field_validator("candidate_email")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if v else v


class SubmissionReview(BaseModel):
    """Recruiter writes a verdict on a submission."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "under_review", "accepted", "rejected"]
    notes: str = Field("", max_length=3000)
    score: float | None = Field(None, ge=0, le=100)
