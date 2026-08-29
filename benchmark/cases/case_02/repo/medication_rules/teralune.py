def is_teralune_allowed(patient: dict) -> bool:
    """Return whether Teralune is allowed for the patient."""
    if patient.get("teralune_allergy", False):
        return False

    if patient.get("marker_r", 0) >= 50:
        return False

    return True
