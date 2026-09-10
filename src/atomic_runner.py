from dataclasses import dataclass
import subprocess


@dataclass
class TestExecutionResult:
    test_name: str
    technique_id: str
    success: bool
    output: str = ""
    error: str = ""


def run_controlled_test(
    test_name: str,
    technique_id: str,
    marker: str,
) -> TestExecutionResult:
    """Execute a harmless PowerShell marker for telemetry validation."""

    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        f'Write-Output "{marker}"',
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
    )

    return TestExecutionResult(
        test_name=test_name,
        technique_id=technique_id,
        success=result.returncode == 0,
        output=result.stdout.strip(),
        error=result.stderr.strip(),
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