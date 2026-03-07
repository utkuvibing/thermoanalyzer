from datetime import UTC, datetime, timedelta

from utils.license_manager import (
    APP_VERSION,
    activate_license_key,
    create_signed_license,
    encode_license_key,
    license_allows_write,
    load_license_state,
    start_trial,
)


def test_activate_license_key_persists_and_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))

    payload = create_signed_license(
        customer_name="Ada Lovelace",
        company_name="Acme Lab",
        sku="PROFESSIONAL",
        seat_count=1,
        issued_at=datetime(2026, 3, 7, tzinfo=UTC),
        expires_at=datetime(2027, 3, 7, tzinfo=UTC),
        allowed_major_version=2,
    )
    key = encode_license_key(payload)

    state = activate_license_key(key, app_version=APP_VERSION)
    loaded = load_license_state(app_version=APP_VERSION)

    assert state["status"] == "activated"
    assert loaded["status"] == "activated"
    assert loaded["license"]["company_name"] == "Acme Lab"
    assert loaded["license"]["customer_name"] == "Ada Lovelace"


def test_trial_becomes_expired_read_only_after_end_date(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))
    monkeypatch.setenv("THERMOANALYZER_COMMERCIAL_MODE", "1")

    start_at = datetime(2026, 3, 7, tzinfo=UTC)
    start_trial(app_version=APP_VERSION, now=start_at)

    expired = load_license_state(
        app_version=APP_VERSION,
        now=start_at + timedelta(days=15),
    )

    assert expired["status"] == "expired_read_only"
    assert "expired" in expired["message"].lower()


def test_dev_build_is_fully_writable_without_license(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))
    monkeypatch.delenv("THERMOANALYZER_COMMERCIAL_MODE", raising=False)

    state = load_license_state(app_version=APP_VERSION)

    assert state["status"] == "development"
    assert license_allows_write(state) is True


def test_commercial_mode_requires_license_for_write_access(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))
    monkeypatch.setenv("THERMOANALYZER_COMMERCIAL_MODE", "1")

    state = load_license_state(app_version=APP_VERSION)

    assert state["status"] == "unlicensed"
    assert license_allows_write(state) is False
