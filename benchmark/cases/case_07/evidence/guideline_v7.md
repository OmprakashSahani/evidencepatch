# Synthetic Clinical Guidance

**Document ID:** SYN-VIRELUNE-2026-V7  
**Version:** 7.0  
**Status:** Authoritative synthetic update

## Medication

Virelune

> Virelune is a fictional medication created solely for this benchmark.

## Previous Recommendation

Virelune was contraindicated in individuals with a recorded Virelune allergy.

Virelune was also contraindicated when Marker-T was greater than or equal to 80 units. Otherwise, Virelune was allowed. No exception applied to the Marker-T restriction.

## Updated Recommendation

The recorded Virelune allergy contraindication remains unchanged and takes precedence over every other condition.

The contraindication for Marker-T values greater than or equal to 80 units remains the default rule.

A narrow exception is introduced for a person with Marker-T greater than or equal to 80 units. Virelune may be allowed only when both of the following requirements are met:

- `exception_approved` is true.
- `monitoring_current` is true.

If either requirement is absent or false, the Marker-T restriction continues to deny Virelune. This exception must never override a recorded Virelune allergy.

For Marker-T values below 80 units, existing eligibility behavior remains unchanged and does not require either exception field to be true.

No unrelated medication behavior or restrictions are changed by this update.

## Implementation Note

Software implementing this guidance should introduce only the narrow exception while preserving the default Marker-T restriction, allergy precedence, below-threshold eligibility, and unrelated behavior.

## Review Requirement

Any software change derived from this synthetic guidance requires human review before deployment.

## Benchmark Notice

This document contains entirely synthetic clinical information. Virelune, Marker-T, exception rules, monitoring requirements, thresholds, recommendations, populations, and all clinical information are fictional and must not be used for real-world medical purposes.
