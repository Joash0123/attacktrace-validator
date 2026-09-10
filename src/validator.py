from dataclasses import dataclass
from typing import Optional
import subprocess


@dataclass
class ValidationResult:
    technique_id: str
    event_id: int
    marker: str
    detected: bool
    evidence: Optional[str] = None


def query_powershell_events(
    marker: str,
    max_events: int = 500,
) -> Optional[str]:
    """Search PowerShell Operational events for a specific marker."""

    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            f'Get-WinEvent -LogName '
            f'"Microsoft-Windows-PowerShell/Operational" '
            f'-MaxEvents {max_events} | '
            f'Where-Object {{ $_.Id -eq 4104 -and '
            f'$_.Message -like "*{marker}*" }} | '
            f'Select-Object -First 1 TimeCreated, Id, Message | '
            f'Out-String'
        ),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    evidence = result.stdout.strip()

    return evidence if evidence else None


def validate(
    technique_id: str,
    event_id: int,
    marker: str,
) -> ValidationResult:
    """Validate whether expected telemetry exists."""

    evidence = query_powershell_events(marker)

    return ValidationResult(
        technique_id=technique_id,
        event_id=event_id,
        marker=marker,
        detected=evidence is not None,
        evidence=evidence,
    )


if __name__ == "__main__":
    result = validate(
        technique_id="T1059.001",
        event_id=4104,
        marker="ADV_DETECTION_VALIDATOR_T1059_001",
    )

    print(f"Technique: {result.technique_id}")
    print(f"Event ID: {result.event_id}")
    print(f"Detected: {result.detected}")

    if result.evidence:
        print("\nEvidence:")
        print(result.evidence)