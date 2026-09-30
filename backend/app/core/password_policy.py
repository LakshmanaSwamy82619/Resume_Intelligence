from __future__ import annotations

import re


def password_policy_issues(password: str) -> list[str]:
    issues = []
    if len(password) < 8:
        issues.append("Use at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        issues.append("Include at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        issues.append("Include at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        issues.append("Include at least one number.")
    if not re.search(r"[^A-Za-z0-9\s]", password):
        issues.append("Include at least one special character.")
    return issues


def enforce_password_policy(password: str) -> None:
    issues = password_policy_issues(password)
    if issues:
        from app.core.exceptions import ValidationAppError

        raise ValidationAppError(" ".join(issues))
