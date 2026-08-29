def is_avenoril_continuation_allowed(patient: dict) -> bool:
    """Return whether Avenoril continuation is allowed for the patient."""
    if patient.get("avenoril_allergy", False):
        return False

    if not patient.get("followup_current", False):
        return False

    return True
