from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    HR = "hr"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class RequirementPriority(str, enum.Enum):
    MANDATORY = "mandatory"
    PREFERRED = "preferred"


class MatchStatus(str, enum.Enum):
    MATCHED = "matched"
    PARTIAL = "partial"
    MISSING = "missing"


class NotificationType(str, enum.Enum):
    ACCOUNT_CREATED = "account_created"
    PASSWORD_RESET = "password_reset"
    SECURITY_EVENT = "security_event"
    BULK_UPLOAD_COMPLETED = "bulk_upload_completed"
    PROCESSING_FAILED = "processing_failed"
    PROCESSING_COMPLETED = "processing_completed"
    EVALUATION_REQUEST = "evaluation_request"
    SYSTEM = "system"


class RetrievalMethod(str, enum.Enum):
    HYBRID = "hybrid"
    SEMANTIC_ONLY = "semantic_only"
    LEXICAL_ONLY = "lexical_only"


class ProcessingJobType(str, enum.Enum):
    SINGLE_RESUME = "single_resume"
    BULK_RESUME = "bulk_resume"
    REINDEX = "reindex"
