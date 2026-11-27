"""Render staging entry point wrapping the existing billing ASGI application."""
import os
from monetization_staging_config import validate_staging_environment

validate_staging_environment(os.environ)

from monetization_service import app  # noqa: E402,F401
