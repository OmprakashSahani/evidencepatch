def is_zoravel_allowed(patient: dict) -> bool:
    """Return whether Zoravel is allowed for the patient."""
    if patient.get("zoravel_allergy", False):
        return False

    if patient.get("marker_w", 0) >= 75:
        return False

    return True
