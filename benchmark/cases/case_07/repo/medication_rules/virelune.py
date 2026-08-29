def is_virelune_allowed(patient: dict) -> bool:
    """Return whether Virelune is allowed for the patient."""
    if patient.get("virelune_allergy", False):
        return False

    if patient.get("marker_t", 0) >= 80:
        return False

    return True
