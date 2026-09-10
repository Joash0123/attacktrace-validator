from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import json
import os
import shutil
import subprocess
import time


POWER_SHELL_LOG = "Microsoft-Windows-PowerShell/Operational"


class TelemetryUnavailableError(RuntimeError):
    """Raised when the PowerShell Operational log cannot be queried."""


@dataclass
class PreflightResult:
    powershell_available: bool
    event_log_accessible: bool
    script_block_logging_enabled: Optional[bool]
    message: str = ""

    @property
    def ready(self) -> bool:
        return self.powershell_available and self.event_log_accessible and self.script_block_logging_enabled is not False


@dataclass
class ValidationResult:
    technique_id: str
    event_id: int
    marker: str
    detected: bool
    evidence: Optional[str] = None
    attempts: int = 1


def _run_powershell(
    command: str,
    timeout: int = 10,
    environment_updates: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    # The host may inject a PowerShell 7 module path into this Windows
    # PowerShell process.  That module is incompatible with powershell.exe's
    # native diagnostics module and prevents Get-WinEvent from loading.
    environment = os.environ.copy()
    for key in list(environment):
        if key.lower() == "psmodulepath":
            del environment[key]
    if environment_updates:
        environment.update(environment_updates)
    try:
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout, env=environment,
        )
    except FileNotFoundError as exc:
        raise TelemetryUnavailableError("powershell.exe was not found on this system.") from exc
    except subprocess.TimeoutExpired as exc:
        raise TelemetryUnavailableError("The PowerShell telemetry query timed out.") from exc


def preflight() -> PreflightResult:
    """Confirm PowerShell and the required Operational log can be inspected."""
    if shutil.which("powershell.exe") is None:
        return PreflightResult(False, False, None, "powershell.exe was not found on PATH.")

    command = rf'''
try {{
    Get-Command Get-WinEvent -ErrorAction Stop | Out-Null
    $log = Get-WinEvent -ListLog "{POWER_SHELL_LOG}" -ErrorAction Stop
    $policy = Get-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging" -ErrorAction SilentlyContinue
    $enabled = if ($null -eq $policy) {{ $null }} else {{ [bool]($policy.EnableScriptBlockLogging -eq 1) }}
    [PSCustomObject]@{{ powershell_available = $true; event_log_accessible = [bool]$log.IsEnabled; script_block_logging_enabled = $enabled; message = if (-not $log.IsEnabled) {{ "The PowerShell Operational log is disabled." }} else {{ "Preflight passed." }} }} | ConvertTo-Json -Compress
}} catch {{
    [PSCustomObject]@{{ powershell_available = $true; event_log_accessible = $false; script_block_logging_enabled = $null; message = $_.Exception.Message }} | ConvertTo-Json -Compress
    exit 1
}}
'''
    result = _run_powershell(command)
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return PreflightResult(True, False, None, result.stderr.strip() or "Invalid preflight response.")
    return PreflightResult(
        bool(data.get("powershell_available")), bool(data.get("event_log_accessible")),
        data.get("script_block_logging_enabled"), data.get("message") or result.stderr.strip(),
    )


def query_powershell_events(
    marker: str, correlation_id: str | None = None, not_before: datetime | None = None, max_events: int = 500,
) -> Optional[str]:
    """Find the current run's Event ID 4104 Script Block Logging evidence."""
    correlation_filter = ""
    if correlation_id:
        correlation_filter = " -and $_.Message -like ('*' + $correlation + '*')"
    start_filter = ""
    if not_before:
        start_time = not_before.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        start_filter = "; StartTime = $startTime"

    command = rf'''
try {{
    $marker = $env:ADV_VALIDATOR_MARKER
    $correlation = $env:ADV_VALIDATOR_CORRELATION
    $startTime = [DateTimeOffset]::Parse(
        $env:ADV_VALIDATOR_START_TIME,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::RoundtripKind
    ).UtcDateTime
    $event = Get-WinEvent -FilterHashtable @{{ LogName = "{POWER_SHELL_LOG}"; Id = 4104{start_filter} }} -MaxEvents {max_events} -ErrorAction Stop |
        Where-Object {{ $_.Message -like ('*' + $marker + '*'){correlation_filter} }} |
        Select-Object -First 1 TimeCreated, Id, Message
    if ($null -ne $event) {{ $event | ConvertTo-Json -Compress }}
}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}
'''
    result = _run_powershell(
        command,
        environment_updates={
            "ADV_VALIDATOR_MARKER": marker,
            "ADV_VALIDATOR_CORRELATION": correlation_id or "",
            "ADV_VALIDATOR_START_TIME": start_time if not_before else "",
        },
    )
    if result.returncode != 0:
        raise TelemetryUnavailableError(result.stderr.strip() or "Unable to query PowerShell Event ID 4104.")
    evidence = result.stdout.strip()
    if not evidence:
        return None
    try:
        event = json.loads(evidence)
        return f"TimeCreated: {event.get('TimeCreated')} | Event ID: {event.get('Id')} | {event.get('Message', '').strip()}"
    except json.JSONDecodeError:
        return evidence


def validate(
    technique_id: str, event_id: int, marker: str, correlation_id: str | None = None, not_before: datetime | None = None,
) -> ValidationResult:
    evidence = query_powershell_events(marker, correlation_id, not_before)
    return ValidationResult(technique_id, event_id, marker, evidence is not None, evidence)


def wait_for_detection(
    technique_id: str, event_id: int, marker: str, correlation_id: str, not_before: datetime,
    timeout_seconds: float = 8, poll_interval: float = 0.75,
) -> ValidationResult:
    """Retry a bounded number of times while telemetry is delivered."""
    deadline, attempts = time.monotonic() + timeout_seconds, 0
    while True:
        attempts += 1
        result = validate(technique_id, event_id, marker, correlation_id, not_before)
        result.attempts = attempts
        if result.detected or time.monotonic() >= deadline:
            return result
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
