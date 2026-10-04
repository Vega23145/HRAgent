from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ResumeId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{3,63}$")]
FileName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,200}$")]
RESUME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{3,63}$")


class Loose(BaseModel):
    """Tolerant models: the pipeline owns this schema, so unknown fields are preserved."""

    model_config = ConfigDict(extra="allow")


class EmailMeta(Loose):
    message_id: str | None = None
    sender: str | None = None
    subject: str | None = None
    date: str | None = None


class Contact(Loose):
    emails: list[str] = []
    phones: list[str] = []
    urls: list[str] = []


class SkillGroup(Loose):
    category: str | None = None
    items: list[str] = []


class Experience(Loose):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    highlights: list[str] = []


class Education(Loose):
    institution: str | None = None
    degree: str | None = None
    major: str | None = None
    location: str | None = None
    start: str | None = None
    end: str | None = None
    grade: str | None = None
    highlights: list[str] = []


class Project(Loose):
    name: str | None = None
    tech: list[str] = []
    highlights: list[str] = []


class Certification(Loose):
    name: str | None = None
    issuer: str | None = None
    score: str | None = None


class ResumeBody(Loose):
    name: str | None = None
    summary: str | None = None
    skills: list[SkillGroup] = []
    experience: list[Experience] = []
    education: list[Education] = []
    projects: list[Project] = []
    certifications: list[Certification] = []
    interests: list[str] = []


class ResumeDoc(Loose):
    email: EmailMeta | None = None
    body: str | None = None
    contact: Contact | None = None
    resume_file: FileName | None = None
    resume: ResumeBody = Field(default_factory=ResumeBody)


class ResumeCreate(ResumeDoc):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: ResumeId | None = Field(None, alias="_id")
