from app.services.patient_errors import patient_facing_detail


def test_patient_facing_detail_uses_fallback_for_generic_http_phrase() -> None:
    assert patient_facing_detail(
        "Bad Request",
        "Uploaded document does not appear to be a medical bill.",
    ) == "Uploaded document does not appear to be a medical bill."


def test_patient_facing_detail_keeps_specific_message() -> None:
    message = "This looks like a prescription, not a hospital bill."
    assert patient_facing_detail(message, "fallback") == message


def test_patient_facing_detail_uses_fallback_for_blank_message() -> None:
    assert patient_facing_detail("   ", "fallback") == "fallback"
