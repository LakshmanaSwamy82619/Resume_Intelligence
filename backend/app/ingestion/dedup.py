"""
Duplicate detection (Section 27).

Three layers, cheapest first:
  1. file_hash        -- exact byte-identical re-upload (SHA-256 of the raw file)
  2. content_hash      -- identical extracted text (catches re-saved/re-exported
                          copies of the same file, e.g. re-printed to PDF)
  3. fingerprint       -- normalized (email + phone + name) identity match,
                          catches the same candidate uploaded from a
                          differently-formatted resume

Optional semantic duplicate detection (near-duplicate resumes with no
shared identity fields) is left as a documented extension point: it would
compare whole-document embeddings with a high similarity threshold, but
enabling it by default risks false-positive-merging two different
candidates who happen to have very similar resumes -- so we deliberately
require deterministic identity signals here and leave embedding based
similarity to informational review rather than automatic merging (README
"Known limitations").
"""
from __future__ import annotations

import hashlib
import re


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def compute_content_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def normalize_text_for_hash(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip().lower()
    return collapsed


def compute_candidate_fingerprint(email: str | None, phone: str | None, full_name: str | None) -> str | None:
    # Email is treated as the primary identity key on its own: two resumes
    # from the same email address are the same candidate even if a phone
    # number was updated, mistyped, or omitted on one of them. Phone is
    # only used as the identity key when no email is present, and full
    # name is the last-resort fallback.
    if email:
        key = email.strip().lower()
    elif phone:
        key = re.sub(r"\D", "", phone)
    elif full_name:
        key = full_name.strip().lower()
    else:
        return None
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
