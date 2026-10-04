"""
The schema Gemini is forced to emit (response_schema).

Token discipline: no field descriptions (the schema is billed as input on every
call; rules live once in prompts.py) and no contact fields (regex does those).
Nullable scalars + plain lists only: the best-supported subset of Gemini's
schema dialect.
"""
from pydantic import BaseModel

SCHEMA_VERSION = "1"


class SkillGroup(BaseModel):
    category: str
    items: list[str]


class Experience(BaseModel):
    company: str
    title: str | None
    location: str | None
    start: str | None
    end: str | None
    highlights: list[str]


class Education(BaseModel):
    institution: str
    degree: str | None
    major: str | None
    location: str | None
    start: str | None
    end: str | None
    grade: str | None
    highlights: list[str]


class Project(BaseModel):
    name: str
    tech: list[str]
    highlights: list[str]


class Certification(BaseModel):
    name: str
    issuer: str | None
    score: str | None


class ResumeExtraction(BaseModel):
    name: str | None
    summary: str | None
    skills: list[SkillGroup]
    experience: list[Experience]
    education: list[Education]
    projects: list[Project]
    certifications: list[Certification]
    interests: list[str]
