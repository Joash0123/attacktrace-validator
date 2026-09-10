\# Adversary Detection Validator



A Windows-based security validation tool that executes a controlled PowerShell test, validates the resulting Windows PowerShell telemetry, and produces a JSON validation report.



\## Overview



This project demonstrates a simple adversary-detection validation workflow:



1\. Execute a controlled PowerShell marker.

2\. Generate PowerShell Script Block Logging telemetry.

3\. Search the Windows PowerShell Operational log for the marker.

4\. Validate the expected MITRE ATT\&CK technique and event ID.

5\. Generate a JSON PASS/FAIL report.

6\. Run automated tests with pytest.



\## ATT\&CK Mapping



\- Technique: T1059.001 — PowerShell

\- Telemetry source: Microsoft-Windows-PowerShell/Operational

\- Event ID: 4104 — Script Block Logging



\## Project Structure



```text

adversary-detection-validator/

├── reports/

│   └── .gitkeep

├── src/

│   ├── atomic\_runner.py

│   ├── main.py

│   ├── reporter.py

│   └── validator.py

├── tests/

│   └── test\_validator.py

├── test-config.json

├── requirements.txt

└── README.md

