def is_dorevex_allowed(patient: dict) -> bool:
    """Return whether Dorevex is allowed for the patient."""
    if patient.get("dorevex_allergy", False):
        return False

    treatment_path = patient.get("treatment_path")
    if treatment_path == "primary":
        return True

    if treatment_path == "adjunct":
        return (
            patient.get("marker_u", 0) >= 30
            and patient.get("specialist_approved", False)
        )

    return False
