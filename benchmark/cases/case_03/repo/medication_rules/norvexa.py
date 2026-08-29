def is_norvexa_high_dose_allowed(patient: dict) -> bool:
    """Return whether high-dose Norvexa is allowed for the patient."""
    if patient.get("norvexa_allergy", False):
        return False

    if patient.get("clearance_z", 0) < 40:
        return False

    return True
