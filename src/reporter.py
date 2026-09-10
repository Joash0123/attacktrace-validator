import json
from pathlib import Path


def write_report(
    technique_id: str,
    test_name: str,
    event_id: int,
    detected: bool,
    output_path: str = "reports/validation-report.json",
) -> None:
    report = {
        "technique": technique_id,
        "test": test_name,
        "event_id": event_id,
        "detected": detected,
        "result": "PASS" if detected else "FAIL",
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )