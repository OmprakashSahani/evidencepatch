def is_praxenor_allowed(patient: dict) -> bool:
    """Return whether Praxenor is allowed for the patient."""
    if patient.get("praxenor_allergy", False):
        return False

    if patient.get("marker_y", 0) >= 50:
        return False

    return True
