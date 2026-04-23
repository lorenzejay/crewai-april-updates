---
name: citation-skill
description: Enforce strict citation format for any factual claim in agent output.
license: Apache-2.0
compatibility: "crewai>=1.12.0"
---

# Citation Skill

Every factual claim MUST carry an inline citation in the form `[^n]` and
resolve to a numbered reference at the end of the document.

## Rules

- One reference per URL. Reuse `[^n]` if the same source is cited twice.
- Use the page/article title, not the domain.
- Prefer HTTPS canonical URLs. Strip tracking params.
- If a claim has no source, prefix it with `[unverified]` and do NOT fabricate one.
