from dataclasses import dataclass
from datetime import datetime, timezone
import subprocess
from uuid import uuid4


@dataclass
class TestExecutionResult:
    test_name: str
    technique_id: str
    success: bool
    correlation_id: str
    started_at: datetime
    finished_at: datetime
    output: str = ""
    error: str = ""


def run_controlled_test(
    test_name: str,
    technique_id: str,
    marker: str,
    correlation_id: str | None = None,
) -> TestExecutionResult:
    """Execute a harmless, uniquely correlated PowerShell marker."""

    correlation_id = correlation_id or str(uuid4())
    emitted_marker = f"{marker}::{correlation_id}"
    started_at = datetime.now(timezone.utc)

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", f'Write-Output "{emitted_marker}"'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        error, output, success = result.stderr.strip(), result.stdout.strip(), result.returncode == 0
    except FileNotFoundError:
        error, output, success = "powershell.exe was not found on this system.", "", False
    except subprocess.TimeoutExpired:
        error, output, success = "The controlled PowerShell test timed out.", "", False

    return TestExecutionResult(
        test_name=test_name,
        technique_id=technique_id,
        success=success,
        correlation_id=correlation_id,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        output=output,
        error=error,
    )


if __name__ == "__main__":
    result = run_controlled_test(
        test_name="controlled-powershell-marker",
        technique_id="T1059.001",
        marker="ADV_DETECTION_VALIDATOR_T1059_001",
    )

    print(f"Test: {result.test_name}")
    print(f"Technique: {result.technique_id}")
    print(f"Execution successful: {result.success}")

    if result.output:
        print(f"Output: {result.output}")

    if result.error:
        print(f"Error: {result.error}")
