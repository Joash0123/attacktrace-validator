import time

from atomic_runner import run_controlled_test
from validator import validate
from reporter import write_report


TECHNIQUE_ID = "T1059.001"
TEST_NAME = "controlled-powershell-marker"
MARKER = "ADV_DETECTION_VALIDATOR_T1059_001"


def main() -> None:
    print("=" * 50)
    print("ADVERSARY DETECTION VALIDATOR")
    print("=" * 50)

    print("\n[1] Running controlled test...")

    execution = run_controlled_test(
        test_name=TEST_NAME,
        technique_id=TECHNIQUE_ID,
        marker=MARKER,
    )

    print(f"Test: {execution.test_name}")
    print(f"Execution successful: {execution.success}")

    if not execution.success:
        print("\nRESULT: TEST EXECUTION FAILED")
        print(execution.error)
        return

    print("\n[2] Waiting for telemetry...")
    time.sleep(2)

    print("[3] Validating telemetry...")

    validation = validate(
        technique_id=TECHNIQUE_ID,
        event_id=4104,
        marker=MARKER,
    )

    print(f"Detected: {validation.detected}")
    write_report(
    technique_id=TECHNIQUE_ID,
    test_name=TEST_NAME,
    event_id=4104,
    detected=validation.detected,
)

    print("Report: reports/validation-report.json")

    print("\n" + "=" * 50)

    if validation.detected:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")

    print("=" * 50)


if __name__ == "__main__":
    main()
