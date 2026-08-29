# Synthetic Clinical Guidance

**Document ID:** SYN-AVENORIL-2026-V9  
**Version:** 9.0  
**Status:** Authoritative synthetic update

## Medication and Workflows

Avenoril has separate synthetic initiation and continuation workflows.

> Avenoril and all workflow requirements in this document are fictional and created solely for this benchmark.

## Previous Recommendation

For initiation, Avenoril was contraindicated in individuals with a recorded Avenoril allergy. Initiation also required `baseline_review_complete` to be true; otherwise, initiation was denied.

For continuation, Avenoril was contraindicated in individuals with a recorded Avenoril allergy. Continuation also required `followup_current` to be true; otherwise, continuation was denied.

Marker-V had no eligibility effect in either workflow.

## Updated Recommendation

The recorded Avenoril allergy contraindication remains unchanged in both initiation and continuation.

The initiation prerequisite remains unchanged: `baseline_review_complete` must be true.

The continuation prerequisite remains unchanged: `followup_current` must be true.

A new contraindication applies when Marker-V is greater than or equal to 65 units. This restriction applies across both Avenoril workflows: initiation and continuation. Marker-V below 65 units does not alter existing eligibility.

This single evidence update therefore has repository-wide impact across both workflow implementations. No unrelated medication behavior or restrictions are changed.

## Implementation Note

Software implementing this guidance should enforce the new Marker-V contraindication in every affected Avenoril workflow while preserving each workflow's independent prerequisites, the allergy contraindication, and unrelated behavior.

## Review Requirement

Any software change derived from this synthetic guidance requires human review before deployment.

## Benchmark Notice

This document contains entirely synthetic clinical information. Avenoril, Marker-V, thresholds, prerequisites, workflows, recommendations, populations, and all clinical information are fictional and must not be used for real-world medical purposes.
