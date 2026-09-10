from atomic_runner import run_controlled_test
from reporter import write_report
from validator import TelemetryUnavailableError, preflight, wait_for_detection

TECHNIQUE_ID = "T1059.001"
TEST_NAME = "controlled-powershell-marker"
MARKER = "ADV_DETECTION_VALIDATOR_T1059_001"
EVENT_ID = 4104


def main() -> None:
    readiness = preflight()
    if not readiness.ready:
        print(f"RESULT: PRECHECK FAILED — {readiness.message}")
        return

    execution = run_controlled_test(TEST_NAME, TECHNIQUE_ID, MARKER)
    if not execution.success:
        print(f"RESULT: TEST EXECUTION FAILED — {execution.error}")
        return

    try:
        validation = wait_for_detection(TECHNIQUE_ID, EVENT_ID, MARKER, execution.correlation_id, execution.started_at)
    except TelemetryUnavailableError as error:
        print(f"RESULT: TELEMETRY UNAVAILABLE — {error}")
        return

    write_report(TECHNIQUE_ID, TEST_NAME, EVENT_ID, validation.detected,
                 correlation_id=execution.correlation_id, attempts=validation.attempts, evidence=validation.evidence)
    print(f"RESULT: {'PASS' if validation.detected else 'FAIL'}")
    if not validation.detected:
        print("No matching Event ID 4104 telemetry arrived before the validation timeout.")


if __name__ == "__main__":
    main()
