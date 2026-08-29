def is_velunex_allowed(patient: dict) -> bool:
    """Return whether Velunex is allowed for the patient."""
    if patient.get("velunex_allergy", False):
        return False

    return True
