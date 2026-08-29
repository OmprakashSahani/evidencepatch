def is_merovant_allowed(patient: dict) -> bool:
    """Return whether Merovant is allowed for the patient."""
    if patient.get("merovant_allergy", False):
        return False

    if patient.get("marker_x", 0) >= 70:
        return False

    return True
