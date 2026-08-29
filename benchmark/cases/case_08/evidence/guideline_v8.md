# Synthetic Clinical Guidance

**Document ID:** SYN-DOREVEX-2026-V8  
**Version:** 8.0  
**Status:** Authoritative synthetic update

## Medication and Treatment Pathways

Dorevex, with the synthetic treatment pathways `primary` and `adjunct`.

> Dorevex and all treatment pathways in this document are fictional and created solely for this benchmark.

## Previous Recommendation

Dorevex was contraindicated in individuals with a recorded Dorevex allergy.

The primary pathway allowed Dorevex when no allergy was recorded.

The adjunct pathway allowed Dorevex only when Marker-U was greater than or equal to 30 units and specialist approval was recorded. If either adjunct requirement was not met, Dorevex was denied. Unsupported or unknown pathways were also denied.

## Updated Recommendation

The recorded Dorevex allergy contraindication remains unchanged.

The primary pathway remains supported and unchanged: a person without a recorded allergy whose `treatment_path` is `primary` remains eligible.

The adjunct recommendation is withdrawn in full. A `treatment_path` of `adjunct` must result in denial regardless of Marker-U value or specialist approval. Marker-U and specialist approval can no longer make adjunct use eligible.

This change withdraws the recommendation pathway itself. It is not a new Marker-U threshold and is not a change to specialist approval criteria.

Unsupported or unknown pathways remain denied. No unrelated medication behavior or restrictions are changed by this update.

## Implementation Note

Software implementing this guidance should remove eligibility through the adjunct pathway while preserving the primary pathway, allergy contraindication, unsupported-pathway denial, and unrelated behavior.

## Review Requirement

Any software change derived from this synthetic guidance requires human review before deployment.

## Benchmark Notice

This document contains entirely synthetic clinical information. Dorevex, Marker-U, treatment pathways, approval criteria, thresholds, recommendations, populations, and all clinical information are fictional and must not be used for real-world medical purposes.
