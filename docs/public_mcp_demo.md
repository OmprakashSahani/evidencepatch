# Public MCP Demo

This product demonstration shows why fresh medical evidence is not automatically actionable medical evidence. It is a software-maintenance evidence disposition, not treatment advice.

## Topic and public sources

The topic is metformin use when eGFR falls below 30 mL/min/1.73 m².

The controlling source was the U.S. Food and Drug Administration document [FDA revises warnings regarding use of the diabetes medicine metformin in certain patients with reduced kidney function](https://www.fda.gov/media/96771/download), dated 2016-04-08. Its relevant software-rule meaning is: for an existing metformin user, if eGFR later falls below 30 mL/min/1.73 m², the FDA rule says discontinue metformin.

The change-pressure source was [Stopping Versus Continuing Metformin in Patients With Advanced CKD: A Nationwide Scottish Target Trial Emulation Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12101959/), published in the *American Journal of Kidney Diseases*, DOI [`10.1053/j.ajkd.2024.08.012`](https://doi.org/10.1053/j.ajkd.2024.08.012), online 2024-11-07 and in the 2025-02 journal issue. The observational study found worse survival associated with stopping metformin after advanced CKD and concluded that continued use below eGFR 30 may be appropriate, while identifying residual confounding and calling for randomized confirmation.

The FDA source is `AUTHORITATIVE` because it is the regulator's controlling labeling rule. The completed peer-reviewed study is `CURRENT` but `NON_AUTHORITATIVE`: publication lifecycle and evidentiary authority are separate dimensions.

## Corrected canonical contract

```json
{
  "evidence": [
    {
      "evidence_id": "FDA: Metformin reduced kidney function safety announcement (2016-04-08)",
      "authority": "AUTHORITATIVE",
      "status": "CURRENT",
      "proposes_executable_change": false,
      "conflicts_with_current_authority": false
    },
    {
      "evidence_id": "doi:10.1053/j.ajkd.2024.08.012",
      "authority": "NON_AUTHORITATIVE",
      "status": "CURRENT",
      "proposes_executable_change": true,
      "conflicts_with_current_authority": true
    }
  ],
  "executable_behavior_change": false,
  "semantic_equivalence": true,
  "unresolved_conflict": false,
  "ambiguous_or_incomplete": false,
  "rationale": "The disposable synthetic repository implements the controlling current FDA rule to discontinue metformin when eGFR falls below 30 mL/min/1.73 m2. The published observational AJKD study provides credible current but non-authoritative evidence supporting continued use below that threshold, creating conflicting change pressure. Because that study does not supersede the controlling FDA rule, no authoritative executable repository change is established; human review is required before treating the research finding as grounds for software change."
}
```

`unresolved_conflict` is false because the scientific evidence disagrees, but the source-authority hierarchy resolves which source currently controls executable behavior. EvidencePatch nevertheless returned `ESCALATE`: credible current non-authoritative change pressure is incompatible with controlling authority, so “no code change now” is not treated as a routine `NO_PATCH` disposition.

## Deterministic disposition and verification

- Action: `ESCALATE`
- Human review required: `true`
- Changed files: none
- Repository impact: clean
- Provenance verification: `passed = true`

All five checks passed:

1. `action_matches_governance`
2. `evidence_ids_match_contract`
3. `human_review_matches_governance`
4. `declared_changes_match_repository`
5. `repository_state_matches_action`

## Human-review checkpoint

The host initially classified the fully published research paper's status as `PROVISIONAL`. During human review, this was corrected to `CURRENT` because publication lifecycle status is distinct from evidentiary strength. The authority remained `NON_AUTHORITATIVE`.

The corrected contract was resubmitted only to the deterministic EvidencePatch MCP tools. No Exa search or fetch occurred during the correction, no repository file changed, the action remained `ESCALATE`, and all five provenance checks still passed. This correction is an explicit example of the intended human-review boundary.

## Responsibility separation

Exa discovered and fetched the public sources. The host constructed the proposed structured interpretation. EvidencePatch deterministically governed the software disposition, compared the disposable repositories, and verified provenance. Nothing was deployed, and the demonstration must not be interpreted as advice about an individual's medication.
