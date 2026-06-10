"""Optional production observability hooks."""
from __future__ import annotations

import logging
import os

LOGGER = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Initialise Sentry when SENTRY_DSN is configured.

    Missing SDKs or DSNs never block local demos, CI, or anonymous fallback
    mode. Production images install ``sentry-sdk`` from requirements.txt.
    """
    dsn = (os.getenv("SENTRY_DSN") or os.getenv("BACKEND_SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception as exc:  # pragma: no cover - depends on optional SDK
        LOGGER.warning("Sentry DSN configured but sentry-sdk is unavailable: %s", exc)
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", os.getenv("ENVIRONMENT", "development")),
        release=os.getenv("SENTRY_RELEASE"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        send_default_pii=False,
    )
    LOGGER.info("Sentry initialised for backend error monitoring.")
    return True


def capture_startup_exception(exc: Exception) -> None:
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        return

