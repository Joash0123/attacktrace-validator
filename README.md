# Adversary Detection Validator

A Windows-focused Flask dashboard that safely validates PowerShell Script Block Logging detection for ATT&CK technique **T1059.001 (PowerShell)**. It executes one harmless marker, waits for the corresponding Event ID **4104** telemetry, and records a clear PASS or FAIL result.

## What the validation does

The application runs `Write-Output` with the controlled marker `ADV_DETECTION_VALIDATOR_T1059_001` and a unique run identifier. It does not modify files, registry settings, services, users, or network configuration.

The validator then searches `Microsoft-Windows-PowerShell/Operational` for Event ID 4104 containing both the controlled marker and the unique identifier. This avoids a false PASS from an older marker event. Results, errors, and history are stored under `reports/`.

## Prerequisites

- Windows with Windows PowerShell (`powershell.exe`) available on `PATH`.
- Permission to read `Microsoft-Windows-PowerShell/Operational`.
- PowerShell Script Block Logging enabled through Group Policy or equivalent endpoint-management policy. The relevant policy is:
  `Computer Configuration > Administrative Templates > Windows Components > Windows PowerShell > Turn on PowerShell Script Block Logging`.
- Python 3.10 or later.

If Script Block Logging is disabled, inaccessible, or telemetry does not arrive within the bounded wait period, the application records a FAIL with a specific reason rather than reporting a false PASS.

## Windows setup and dashboard run

From PowerShell in the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python web\app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Click **Run validation** to execute the controlled marker. The dashboard provides validation history, pass rate, recent activity, CSV export, JSON download, and history clearing.

## Testing

The test suite uses mocks and does not invoke PowerShell or Windows Event Logs:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

## Project structure

```text
src/                 Controlled test, preflight/telemetry validation, report writer
web/app.py           Flask API and history persistence
web/templates/       Dashboard
tests/               Unit and API tests
reports/             Generated validation report and history (ignored by Git)
```
