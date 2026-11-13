"""Development-only system follow-up preview launcher (scripts/dev_system_follow_ups.py).

It is the only registration path outside the tests, it refuses to run unless
the backend is a development backend bound to loopback, and no start or
deployment configuration refers to it.
"""

from __future__ import annotations

import inspect

import pytest

from modules import system_follow_ups
from modules.system_follow_ups import validate_system_prompt
from tests.test_slice1_closure import DEPLOY_FILES, ROOT


def test_no_start_or_deploy_configuration_refers_to_the_dev_launcher():
    for name in DEPLOY_FILES:
        assert "dev_system_follow_ups" not in (ROOT / name).read_text(encoding="utf-8"), name
    # The ordinary local launcher serves the real app unless this script asks otherwise.
    from scripts import run_local

    assert inspect.signature(run_local.main).parameters["backend_app"].default == ("backend.main:app",)
    assert inspect.signature(run_local.main).parameters["extra_env"].default is None


@pytest.mark.parametrize("environment,host", [
    ("production", "127.0.0.1"), ("staging", "127.0.0.1"),
    ("development", ""), ("development", "0.0.0.0"),
])
def test_dev_launcher_refuses_outside_loopback_development(monkeypatch, environment, host):
    from backend import config
    from scripts import dev_system_follow_ups as launcher

    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("JWT_SECRET_KEY", "k9" * 24)
    monkeypatch.setenv("CORS_ORIGINS", "https://interviv.example")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unused-never-opened.sqlite3")
    monkeypatch.setenv("INTERVIV_BIND_HOST", host)
    config.get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="development-only|loopback"):
        launcher.create_app()
    assert system_follow_ups.current_trigger() is system_follow_ups.default_trigger


def test_dev_launcher_registers_only_for_a_loopback_development_backend(monkeypatch):
    from backend import config
    from backend.main import app as real_app
    from scripts import dev_system_follow_ups as launcher

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("INTERVIV_BIND_HOST", "127.0.0.1")
    config.get_settings.cache_clear()
    try:
        assert launcher.create_app() is real_app
        assert system_follow_ups.current_trigger() is launcher.preview_trigger
        proposal = launcher.preview_trigger({})
        assert validate_system_prompt(proposal.prompt, parent_answer="any answer", question_context={}) == (True, "")
    finally:
        system_follow_ups.reset_trigger()
    assert system_follow_ups.current_trigger() is system_follow_ups.default_trigger


def test_dev_launcher_runs_the_local_launcher_with_the_factory_target(monkeypatch, capsys):
    from scripts import dev_system_follow_ups as launcher
    from scripts import run_local

    seen = {}
    monkeypatch.setattr(run_local, "main", lambda **kwargs: seen.update(kwargs) or 0)
    assert launcher.main() == 0
    assert seen == {
        "backend_app": ("--factory", "scripts.dev_system_follow_ups:create_app"),
        "extra_env": {"SYSTEM_FOLLOW_UPS_ENABLED": "true"},
    }
    assert "this local backend only" in capsys.readouterr().out
