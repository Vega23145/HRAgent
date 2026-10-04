from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from resumehub.app.core.utils import SLUG_PATTERN

SlugId = Annotated[str, StringConstraints(pattern=SLUG_PATTERN)]


class RequiredSkill(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    weight: float = Field(gt=0, le=10)

    @field_validator("name")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.strip().lower()


class JobRoleBase(BaseModel):
    # extras are kept so the matcher can evolve the schema without this API dropping fields
    model_config = ConfigDict(extra="allow")

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    department: str | None = None
    team: str | None = None
    employment_type: str = "full-time"
    work_mode: str = "onsite"
    experience_level: str = "junior"
    responsibilities: list[str] = []
    tech_stack: list[str] = []
    nice_to_have: list[str] = []
    required_skills: list[RequiredSkill] = Field(min_length=1)
    min_years: float = Field(0, ge=0)
    seniority: int = Field(1, ge=0)
    w_skills: float = Field(0.40, ge=0, le=1)
    w_years: float = Field(0.25, ge=0, le=1)
    w_seniority: float = Field(0.20, ge=0, le=1)
    w_relevance: float = Field(0.15, ge=0, le=1)

    @model_validator(mode="after")
    def _check(self):
        total = self.w_skills + self.w_years + self.w_seniority + self.w_relevance
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"w_* weights must sum to 1.0 (got {total:.3f})")
        names = [s.name for s in self.required_skills]
        if len(set(names)) != len(names):
            raise ValueError("required_skills contains duplicate names")
        return self


class JobRoleCreate(JobRoleBase):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    id: SlugId = Field(alias="_id")
