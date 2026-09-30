from __future__ import annotations


COMMON_DOMAIN_CORRECTIONS = {
    "gmai.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmail.con": "gmail.com",
}


def suggest_email_correction(email: str) -> str | None:
    local, separator, domain = email.strip().rpartition("@")
    corrected_domain = COMMON_DOMAIN_CORRECTIONS.get(domain.casefold())
    if not separator or not local or not corrected_domain:
        return None
    return f"{local}@{corrected_domain}"
