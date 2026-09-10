from datetime import datetime
import json
from pathlib import Path
import sys

from flask import Flask, jsonify, render_template

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
REPORTS_DIR = PROJECT_ROOT / "reports"
HISTORY_FILE = REPORTS_DIR / "validation-history.json"
sys.path.insert(0, str(SRC_DIR))

from atomic_runner import run_controlled_test
from reporter import write_report
from validator import TelemetryUnavailableError, preflight, wait_for_detection

app = Flask(__name__)
TECHNIQUE_ID = "T1059.001"
TEST_NAME = "controlled-powershell-marker"
MARKER = "ADV_DETECTION_VALIDATOR_T1059_001"
EVENT_ID = 4104


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(history):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)


def add_history_entry(result, detected, **details):
    history = load_history()
    history.insert(0, {
        "timestamp": datetime.now().astimezone().isoformat(),
        "technique": TECHNIQUE_ID,
        "event_id": EVENT_ID,
        "test": TEST_NAME,
        "detected": detected,
        "result": result,
        **{key: value for key, value in details.items() if value is not None},
    })
    save_history(history[:50])


def validation_response(result, detected, status_code=200, **details):
    payload = {
        "success": status_code < 400,
        "result": result,
        "detected": detected,
        "technique": TECHNIQUE_ID,
        "event_id": EVENT_ID,
        "test": TEST_NAME,
        **{key: value for key, value in details.items() if value is not None},
    }
    return jsonify(payload), status_code


def record_failure(code, message, **details):
    add_history_entry("FAIL", False, error_code=code, error_message=message, **details)
    write_report(TECHNIQUE_ID, TEST_NAME, EVENT_ID, False, str(REPORTS_DIR / "validation-report.json"),
                 error_code=code, error_message=message, **details)
    return validation_response("FAIL", False, 503 if code in {"powershell_unavailable", "telemetry_unavailable", "logging_disabled"} else 502,
                               error_code=code, error=message, **details)


@app.errorhandler(Exception)
def json_error(error):
    """Ensure API failures never fall back to Flask's HTML error response."""
    if not str(getattr(error, "description", "")).startswith("404") and not str(error).startswith("404"):
        app.logger.exception("Unhandled application error")
    if str(getattr(error, "description", "")).startswith("404"):
        return error
    return validation_response("FAIL", False, 500, error_code="internal_error", error="An unexpected server error occurred.")


@app.route("/")
def index():
    return render_template("index.html", technique_id=TECHNIQUE_ID, test_name=TEST_NAME, event_id=EVENT_ID)


@app.get("/api/history")
def get_history():
    return jsonify(load_history())


@app.post("/api/validate")
def run_validation():
    readiness = preflight()
    if not readiness.powershell_available:
        return record_failure("powershell_unavailable", readiness.message)
    if not readiness.event_log_accessible:
        return record_failure("telemetry_unavailable", readiness.message)
    if readiness.script_block_logging_enabled is False:
        return record_failure("logging_disabled", "PowerShell Script Block Logging is disabled. Enable it before validating.")

    execution = run_controlled_test(TEST_NAME, TECHNIQUE_ID, MARKER)
    if not execution.success:
        return record_failure("execution_failed", execution.error or "The controlled PowerShell test failed.",
                              correlation_id=execution.correlation_id)

    try:
        validation = wait_for_detection(
            TECHNIQUE_ID, EVENT_ID, MARKER, execution.correlation_id, execution.started_at,
        )
    except TelemetryUnavailableError as error:
        return record_failure("telemetry_unavailable", str(error), correlation_id=execution.correlation_id)

    result = "PASS" if validation.detected else "FAIL"
    details = {
        "correlation_id": execution.correlation_id,
        "attempts": validation.attempts,
        "evidence": validation.evidence,
    }
    if not validation.detected:
        details.update(error_code="detection_timeout", error_message="No matching Event ID 4104 telemetry arrived before the validation timeout.")
    add_history_entry(result, validation.detected, **details)
    write_report(TECHNIQUE_ID, TEST_NAME, EVENT_ID, validation.detected,
                 str(REPORTS_DIR / "validation-report.json"), **details)
    return validation_response(result, validation.detected, 200, **details,
                               error=details.get("error_message"))


@app.delete("/api/history")
def clear_history():
    try:
        HISTORY_FILE.unlink(missing_ok=True)
    except OSError as error:
        return jsonify(success=False, error="Unable to clear validation history.", error_code="history_clear_failed"), 500
    return jsonify(success=True, message="Validation history cleared.")


if __name__ == "__main__":
    app.run(debug=True)
