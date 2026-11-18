from scripts.run_local import EXECUTOR_URL, _runtime_environment


def test_local_launcher_defaults_to_offline_providers_and_no_external_executor(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("CODING_EXECUTOR_URL", "https://external.example")

    env = _runtime_environment(tmp_path, executor_on=False, live_jobs=False)

    assert env["DATABASE_URL"] == f"sqlite:///{tmp_path / 'interviv-local.sqlite3'}"
    assert env["JOBS_LIVE_FETCH"] == "0"
    assert env["LLM_LIVE_FETCH"] == "0"
    assert env["QUESTION_GENERATION_MODE"] == "csv"
    assert env["QUESTION_LLM_PROVIDER"] == "auto"
    assert env["QUESTION_REQUIRE_LLM"] == "false"
    assert "CODING_EXECUTOR_URL" not in env


def test_live_questions_flag_enables_llm_with_csv_fallback(tmp_path):
    env = _runtime_environment(tmp_path, executor_on=False, live_jobs=False, live_questions=True)

    assert env["LLM_LIVE_FETCH"] == "1"
    assert env["QUESTION_GENERATION_MODE"] == "llm_csv_fallback"
    assert env["QUESTION_REQUIRE_LLM"] == "false"


def test_live_jobs_and_local_executor_are_enabled_only_when_requested(tmp_path):
    env = _runtime_environment(tmp_path, executor_on=True, live_jobs=True)

    assert env["JOBS_LIVE_FETCH"] == "1"
    assert env["CODING_EXECUTOR_URL"] == EXECUTOR_URL
    assert env["LLM_LIVE_FETCH"] == "0"
    assert env["QUESTION_GENERATION_MODE"] == "csv"


def test_smoke_password_is_human_typable():
    """The smoke account password is copied by hand into the login form.

    A 44-character random token (the old generator) is practically
    untypable — look-alike characters and copy slips surface only as
    "Invalid email or password." The generated password must stay short,
    use an unambiguous alphabet, and still satisfy signup validation
    (at least 8 characters, one letter and one number).
    """
    import re

    from scripts.smoke_local import _new_smoke_password

    for _ in range(50):
        password = _new_smoke_password()
        assert 8 <= len(password) <= 24
        assert re.fullmatch(r"[a-z0-9-]+", password), password
        assert any(c.isalpha() for c in password)
        assert any(c.isdigit() for c in password)


def test_trusted_local_execution_is_opt_in_and_loopback_bound(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", "1")  # stale shell value

    off = _runtime_environment(tmp_path, executor_on=False, live_jobs=False)
    assert "INTERVIV_TRUSTED_LOCAL_EXECUTION" not in off
    assert off["INTERVIV_BIND_HOST"] == "127.0.0.1"

    on = _runtime_environment(tmp_path, executor_on=False, live_jobs=False, trusted_local=True)
    assert on["INTERVIV_TRUSTED_LOCAL_EXECUTION"] == "1"
    assert on["INTERVIV_BIND_HOST"] == "127.0.0.1"
    assert on["ENVIRONMENT"] == "development"
    assert "CODING_EXECUTOR_URL" not in on
