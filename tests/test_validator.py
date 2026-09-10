from src.validator import validate


def test_validate_returns_result():
    result = validate(
        technique_id="T1059.001",
        event_id=4104,
        marker="ADV_DETECTION_VALIDATOR_T1059_001",
    )

    assert result.technique_id == "T1059.001"
    assert result.event_id == 4104
    assert result.detected is True