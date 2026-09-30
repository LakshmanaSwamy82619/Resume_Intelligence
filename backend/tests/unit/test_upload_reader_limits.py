from __future__ import annotations

import pytest

from app.core.exceptions import ValidationAppError
from app.services.resume_service import read_upload_limited


class FakeUpload:
    def __init__(self, size: int):
        self.remaining = size
        self.read_requests: list[int] = []

    async def read(self, size: int) -> bytes:
        self.read_requests.append(size)
        amount = min(size, self.remaining)
        self.remaining -= amount
        return b"x" * amount


@pytest.mark.asyncio
async def test_limited_upload_reader_returns_small_file():
    upload = FakeUpload(17)
    result = await read_upload_limited(upload, 20)
    assert len(result) == 17
    assert upload.remaining == 0


@pytest.mark.asyncio
async def test_limited_upload_reader_stops_at_limit_plus_one():
    upload = FakeUpload(1000)
    with pytest.raises(ValidationAppError):
        await read_upload_limited(upload, 20)
    assert sum(upload.read_requests) == 21
    assert upload.remaining == 979
