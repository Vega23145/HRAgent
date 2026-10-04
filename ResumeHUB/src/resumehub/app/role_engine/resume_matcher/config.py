import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    resume_uri: str
    resume_db: str
    resume_col: str
    role_uri: str
    role_db: str
    role_col: str

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            resume_uri=e("HUB_MONGO_URI", e("RESUME_MONGO_URI", "mongodb://localhost:27017")),
            resume_db=e("HUB_MONGO_DB", e("RESUME_MONGO_DB", "resumes")),
            resume_col=e("HUB_RESUME_COLLECTION", e("RESUME_MONGO_COLLECTION", "resumes")),
            role_uri=e("HUB_MONGO_URI", e("ROLE_MONGO_URI", "mongodb://localhost:27017")),
            role_db=e("HUB_MONGO_DB", e("ROLE_MONGO_DB", "resumes")),
            role_col=e("HUB_ROLE_COLLECTION", e("ROLE_MONGO_COLLECTION", "roles")),
        )
