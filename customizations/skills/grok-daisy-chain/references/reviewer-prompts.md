# Two-reviewer synthesis, then three original-proposer votes

## E1 synthesis prompt
Read the source evidence and ALL P1/P2/P3 options. Compare correctness, feasibility, coverage and risk. Combine the best compatible elements into ONE concrete option. Explain retained/rejected pieces, exact changes, tests, rollback and unresolved objections. Keeping one original unchanged is allowed only with rationale after assessing all three. Do not invent facts or scope. You synthesize; you do not cast a final vote.

## E2 synthesis-refinement prompt
Read the same source evidence, all three originals and E1's draft/rationale. Refine into ONE final candidate, preserving both reviewer contributions and unresolved objections. Do not merely name a winner or return three choices. No coherent evidence-backed action means INSUFFICIENT_EVIDENCE or REJECT, not an invented patch. Preserve disagreement for the final voters; reviewer unanimity is not required. Freeze exact disposition, action/patch, target revision, evidence, tests and rollback into the candidate digest.

## P1/P2/P3 final-voter prompt — three separate calls
You are reconvened in your original proposer role, not a resumed session unless supported. Read the evidence, all original options, BOTH reviewer contributions, objections and frozen candidate. Independently judge this combined option, not your original favorite. Return strict JSON:

    {"role":"P1", "candidate_digest":"<exact supplied digest>", "approved":true, "reasoning":"<evidence-based>", "objections":[]}

Use your assigned role. Do not change the candidate while voting or fabricate other votes. Distinguish preference dissent from substantiated safety, authorization or evidence blockers.

## Deterministic aggregation
Require one valid ballot each from P1/P2/P3 on the same candidate digest, with strict boolean approvals. Two or three approvals pass; zero or one fail. **2–1 is sufficient.** Missing/invalid ballots are INCOMPLETE, not fabricated negative votes. Preserve dissent. No simulated panel, five-agent unanimity or E1/E2 shortcut. Changed candidates require fresh votes. Passing the vote proceeds to the authorized fix workflow with all objective testing/security and human merge/release controls intact. Advisory and insufficient-evidence candidates never execute patches or alter services.
