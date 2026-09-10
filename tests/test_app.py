from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import app as webapp
from validator import PreflightResult, TelemetryUnavailableError, ValidationResult


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(webapp, "HISTORY_FILE", tmp_path / "validation-history.json")


@pytest.fixture
def client():
    return webapp.app.test_client()


def ready_preflight():
    return PreflightResult(True, True, True, "Preflight passed.")


def execution():
    now = datetime.now(timezone.utc)
    return SimpleNamespace(success=True, correlation_id="run-123", started_at=now, error="")


def test_history_is_persisted_and_newest_first(client):
    webapp.add_history_entry("PASS", True, correlation_id="a")
    webapp.add_history_entry("FAIL", False, error_code="detection_timeout")
    response = client.get("/api/history")
    assert response.status_code == 200
    assert [item["result"] for item in response.get_json()] == ["FAIL", "PASS"]


def test_api_validation_success_records_history(client, monkeypatch):
    monkeypatch.setattr(webapp, "preflight", ready_preflight)
    monkeypatch.setattr(webapp, "run_controlled_test", lambda *args: execution())
    monkeypatch.setattr(webapp, "wait_for_detection", lambda *args: ValidationResult("T1059.001", 4104, "marker", True, "evidence", 2))
    response = client.post("/api/validate")
    assert response.status_code == 200
    assert response.get_json()["result"] == "PASS"
    assert client.get("/api/history").get_json()[0]["detected"] is True


def test_api_no_detection_returns_fail_and_history(client, monkeypatch):
    monkeypatch.setattr(webapp, "preflight", ready_preflight)
    monkeypatch.setattr(webapp, "run_controlled_test", lambda *args: execution())
    monkeypatch.setattr(webapp, "wait_for_detection", lambda *args: ValidationResult("T1059.001", 4104, "marker", False, None, 3))
    response = client.post("/api/validate")
    assert response.status_code == 200
    assert response.get_json()["error_code"] == "detection_timeout"
    assert client.get("/api/history").get_json()[0]["result"] == "FAIL"


def test_api_returns_json_when_telemetry_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(webapp, "preflight", ready_preflight)
    monkeypatch.setattr(webapp, "run_controlled_test", lambda *args: execution())
    monkeypatch.setattr(webapp, "wait_for_detection", lambda *args: (_ for _ in ()).throw(TelemetryUnavailableError("log unavailable")))
    response = client.post("/api/validate")
    assert response.status_code == 503
    assert response.is_json
    assert response.get_json()["error_code"] == "telemetry_unavailable"


def test_api_execution_failure_returns_json(client, monkeypatch):
    monkeypatch.setattr(webapp, "preflight", ready_preflight)
    monkeypatch.setattr(webapp, "run_controlled_test", lambda *args: SimpleNamespace(success=False, correlation_id="run-123", error="execution failed"))
    response = client.post("/api/validate")
    assert response.status_code == 502
    assert response.get_json()["error_code"] == "execution_failed"


def test_api_unexpected_failure_is_json(client, monkeypatch):
    monkeypatch.setattr(webapp, "preflight", lambda: (_ for _ in ()).throw(RuntimeError("unexpected")))
    response = client.post("/api/validate")
    assert response.status_code == 500
    assert response.is_json
    assert response.get_json()["error_code"] == "internal_error"


def test_clear_history(client):
    webapp.add_history_entry("PASS", True)
    response = client.delete("/api/history")
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert client.get("/api/history").get_json() == []
