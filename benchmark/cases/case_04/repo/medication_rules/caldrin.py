def is_caldrin_allowed(patient: dict) -> bool:
    """Return whether Caldrin is allowed for the patient."""
    if patient.get("caldrin_allergy", False):
        return False

    return patient.get("age_group") in {"adult", "adolescent"}
