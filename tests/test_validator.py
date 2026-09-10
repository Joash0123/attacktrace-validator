from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.validator import (
    PreflightResult,
    TelemetryUnavailableError,
    ValidationResult,
    preflight,
    query_powershell_events,
    validate,
    wait_for_detection,
)


def test_validate_returns_detection_when_evidence_exists():
    with patch("src.validator.query_powershell_events", return_value="Event ID: 4104"):
        result = validate("T1059.001", 4104, "ADV_DETECTION_VALIDATOR_T1059_001", "run-1")
    assert result.detected is True
    assert result.evidence == "Event ID: 4104"


def test_validate_returns_no_detection_when_event_is_absent():
    with patch("src.validator.query_powershell_events", return_value=None):
        result = validate("T1059.001", 4104, "ADV_DETECTION_VALIDATOR_T1059_001", "run-1")
    assert result.detected is False


def test_preflight_reports_missing_powershell():
    with patch("src.validator.shutil.which", return_value=None):
        result = preflight()
    assert result == PreflightResult(False, False, None, "powershell.exe was not found on PATH.")


def test_event_query_keeps_marker_out_of_logged_command():
    captured = {}

    def run_query(command, timeout=10, environment_updates=None):
        captured["command"] = command
        captured["environment"] = environment_updates
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    with patch("src.validator._run_powershell", side_effect=run_query):
        assert query_powershell_events(
            "ADV_DETECTION_VALIDATOR_T1059_001", "unique-run", datetime(2026, 1, 2, 3, 4, 5, 123456, timezone.utc),
        ) is None

    assert "ADV_DETECTION_VALIDATOR_T1059_001" not in captured["command"]
    assert "unique-run" not in captured["command"]
    assert captured["environment"]["ADV_VALIDATOR_MARKER"] == "ADV_DETECTION_VALIDATOR_T1059_001"
    assert captured["environment"]["ADV_VALIDATOR_START_TIME"] == "2026-01-02T03:04:05.123456Z"


def test_wait_for_detection_retries_until_evidence_arrives():
    no_detection = ValidationResult("T1059.001", 4104, "marker", False)
    detected = ValidationResult("T1059.001", 4104, "marker", True, "evidence")
    with patch("src.validator.validate", side_effect=[no_detection, detected]), patch("src.validator.time.sleep"):
        result = wait_for_detection("T1059.001", 4104, "marker", "run-1", datetime.now(timezone.utc), 2, 0.01)
    assert result.detected is True
    assert result.attempts == 2


def test_wait_for_detection_surfaces_telemetry_failure():
    with patch("src.validator.validate", side_effect=TelemetryUnavailableError("log unavailable")):
        with pytest.raises(TelemetryUnavailableError, match="log unavailable"):
            wait_for_detection("T1059.001", 4104, "marker", "run-1", datetime.now(timezone.utc), 0)
