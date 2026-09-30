from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_configuration_requires_a_long_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="development", JWT_SECRET_KEY=None)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="production", JWT_SECRET_KEY=None)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="production", JWT_SECRET_KEY="too-short")


def test_production_configuration_accepts_configured_secret_without_printing_it():
    settings = Settings(_env_file=None, APP_ENV="production", JWT_SECRET_KEY="a" * 48)
    assert settings.APP_ENV == "production"
    assert len(settings.JWT_SECRET_KEY) == 48
