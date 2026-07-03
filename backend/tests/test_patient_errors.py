from app.services.patient_errors import document_mismatch_detail, patient_facing_detail


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


def test_document_mismatch_detail_names_file_and_suggested_type() -> None:
    message = document_mismatch_detail(
        filename="invoice.pdf",
        assigned_type="bill",
        message="This looks like a prescription, not a hospital bill.",
        fallback="Uploaded document does not appear to be a medical bill.",
        suggested_type="prescription",
    )
    assert '"invoice.pdf"' in message
    assert "Hospital bill" in message
    assert "prescription" in message.lower()
    assert "Prescription" in message


def test_document_mismatch_detail_uses_fallback_without_suggestion() -> None:
    message = document_mismatch_detail(
        filename="scan.jpg",
        assigned_type="lab_report",
        message=None,
        fallback="Uploaded document does not appear to be a lab report.",
        suggested_type=None,
    )
    assert '"scan.jpg"' in message
    assert "Lab report" in message
    assert "does not appear to be a lab report" in message
