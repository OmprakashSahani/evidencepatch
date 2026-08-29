def is_lumetra_allowed(patient: dict) -> bool:
    """Return whether Lumetra is allowed for the patient."""
    if patient.get("lumetra_allergy", False):
        return False

    return patient.get("age_group") == "adult"
