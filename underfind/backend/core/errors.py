from __future__ import annotations

from typing import Optional


class QuotaExceededError(RuntimeError):
    """Raised when a provider's daily API quota would be exceeded."""

    def __init__(
        self,
        provider: str,
        used: int,
        limit: int,
        requested: int = 0,
    ):
        self.provider = provider
        self.used = used
        self.limit = limit
        self.requested = requested
        super().__init__(
            f"{provider} daily quota exhausted: {used}/{limit} units used, {requested} requested. Resets at the next quota day."
        )


class InvalidTransitionError(ValueError):
    """Raised when a job is moved to a status its current state does not allow."""


class SourceAlreadyUsedError(ValueError):
    """Raised when a source video (or a near-duplicate of it) already has a job."""

    def __init__(
        self,
        source_key: str,
        existing_job_id: Optional[str] = None,
        duplicate_of: Optional[str] = None,
    ):
        self.source_key = source_key
        self.existing_job_id = existing_job_id
        self.duplicate_of = duplicate_of
        reason = f"near-duplicate of {duplicate_of}" if duplicate_of else "already used"
        super().__init__(f"Source {source_key} is {reason} (job {existing_job_id}). Pass force=true to create anyway.")


class NotFoundError(LookupError):
    """Raised when a requested pipeline entity does not exist."""


class PermanentStageError(RuntimeError):
    """A pipeline stage failure that retrying will not fix (private/removed video, login wall, bad input)."""


class DuplicateSourceError(PermanentStageError):
    """Raised after download when the video matches an already used source on another platform."""

    def __init__(
        self,
        source_key: str,
        duplicate_of: str,
        existing_job_id: str,
        distance: int,
    ):
        self.source_key = source_key
        self.duplicate_of = duplicate_of
        self.existing_job_id = existing_job_id
        self.distance = distance
        super().__init__(
            f"Source {source_key} is a near-duplicate of {duplicate_of} (hash distance {distance}, job {existing_job_id})."
        )


class MediaToolError(RuntimeError):
    """Raised when ffmpeg fails or is unavailable."""
