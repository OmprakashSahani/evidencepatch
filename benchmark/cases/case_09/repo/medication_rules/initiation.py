def is_avenoril_initiation_allowed(patient: dict) -> bool:
    """Return whether Avenoril initiation is allowed for the patient."""
    if patient.get("avenoril_allergy", False):
        return False

    if not patient.get("baseline_review_complete", False):
        return False

    return True
