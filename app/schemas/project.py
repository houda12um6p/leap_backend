import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


_JIRA_KEY_PREFIX_RE = re.compile(r'^[A-Z][A-Z0-9]+$')


def _normalise_jira_key(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip().upper()
    if not cleaned:
        return None
    # Accept "LEAP" or "LEAP-42" — store only the prefix.
    cleaned = cleaned.split('-', 1)[0]
    if not _JIRA_KEY_PREFIX_RE.match(cleaned):
        raise ValueError(
            "jira_key must be a Jira project prefix (uppercase letters/digits, "
            "starting with a letter, e.g. 'LEAP')."
        )
    return cleaned


def _normalise_jira_url(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip().rstrip('/')
    if not cleaned:
        return None
    if not re.match(r'^https?://[\w.\-]+(:\d+)?(/[\w.\-/]*)?$', cleaned):
        raise ValueError(
            "jira_base_url must be a full URL "
            "(e.g. https://your-org.atlassian.net)."
        )
    return cleaned


def _normalise_email(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        return None
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[-1]:
        raise ValueError("jira_email must be a valid email address.")
    return cleaned


def _normalise_token(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = v.strip()
    return cleaned or None


class ProjectBase(BaseModel):
    name: str
    repo_url: str
    status: str = "active"
    jira_key: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r'^https?://(www\.)?github\.com/[\w.\-]+/[\w.\-]+$'
        if not re.match(pattern, v):
            raise ValueError(
                "repo_url must be a valid GitHub repository URL "
                "(e.g. https://github.com/owner/repo)"
            )
        return v.rstrip('/')

    @field_validator("status", mode="before")
    @classmethod
    def normalise_status(cls, v: str) -> str:
        return v.lower()

    @field_validator("jira_key", mode="before")
    @classmethod
    def normalise_jira_key(cls, v: str | None) -> str | None:
        return _normalise_jira_key(v)

    @field_validator("jira_base_url", mode="before")
    @classmethod
    def normalise_jira_url(cls, v: str | None) -> str | None:
        return _normalise_jira_url(v)

    @field_validator("jira_email", mode="before")
    @classmethod
    def normalise_jira_email(cls, v: str | None) -> str | None:
        return _normalise_email(v)


class ProjectCreate(ProjectBase):
    """Project create payload. `jira_api_token` is the plaintext token; it is
    encrypted server-side and never returned in any response."""
    jira_api_token: str | None = None

    @field_validator("jira_api_token", mode="before")
    @classmethod
    def normalise_jira_api_token(cls, v: str | None) -> str | None:
        return _normalise_token(v)


class ProjectUpdate(BaseModel):
    """Partial update. Any field omitted is left unchanged. Sending an explicit
    null on a Jira field clears it. Sending an empty string on jira_api_token
    also clears the stored token."""
    name: str | None = None
    repo_url: str | None = None
    status: str | None = None
    jira_key: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None

    @field_validator("jira_key", mode="before")
    @classmethod
    def normalise_jira_key(cls, v: str | None) -> str | None:
        return _normalise_jira_key(v)

    @field_validator("jira_base_url", mode="before")
    @classmethod
    def normalise_jira_url(cls, v: str | None) -> str | None:
        return _normalise_jira_url(v)

    @field_validator("jira_email", mode="before")
    @classmethod
    def normalise_jira_email(cls, v: str | None) -> str | None:
        return _normalise_email(v)

    @field_validator("jira_api_token", mode="before")
    @classmethod
    def normalise_jira_api_token(cls, v: str | None) -> str | None:
        return _normalise_token(v)


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_url: str
    status: str
    jira_key: str | None
    jira_base_url: str | None
    jira_email: str | None
    jira_api_token_set: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
