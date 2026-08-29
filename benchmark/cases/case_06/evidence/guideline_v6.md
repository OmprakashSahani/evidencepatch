# Synthetic Clinical Guidance

**Document ID:** SYN-SEREVON-2026-V6  
**Version:** 6.0  
**Status:** Authoritative synthetic update

## Medication and Monitoring

Serevon, with the synthetic clinical fields `serevon_allergy` and `monitoring_current`.

> Serevon and its monitoring requirements are fictional and created solely for this benchmark.

## Previous Recommendation

Serevon was contraindicated in individuals with a recorded Serevon allergy. Otherwise, Serevon was allowed, and no monitoring requirement applied.

## Updated Recommendation

The recorded Serevon allergy contraindication remains unchanged.

Treatment is allowed only when the required monitoring is current. When `monitoring_current` is false, Serevon must be denied.

No unrelated medication restrictions are changed by this update.

## Implementation Note

Software implementing this guidance should add the independent monitoring prerequisite while preserving the allergy contraindication and all unrelated behavior.

## Review Requirement

Any software change derived from this synthetic guidance requires human review before deployment.

## Benchmark Notice

This document contains entirely synthetic clinical information. Serevon, monitoring fields and requirements, recommendations, populations, thresholds, and all clinical information are fictional and must not be used for medical purposes.
