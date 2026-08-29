def is_serevon_allowed(patient: dict) -> bool:
    """Return whether Serevon is allowed for the patient."""
    if patient.get("serevon_allergy", False):
        return False

    return True
