---
name: researcher-skill
description: Research workflow for gathering, validating, and summarizing sources.
license: Apache-2.0
compatibility: "crewai>=1.12.0"
allowed_tools:
  - web-search
  - file-read
---

# Researcher Skill

When performing research, follow this workflow:

1. **Decompose** the question into 2–4 atomic sub-questions.
2. **Gather** at least two sources per sub-question. Prefer primary sources.
3. **Validate** each claim against a second source before using it.
4. **Summarize** findings in Markdown with a numbered reference list.

## Output format

```
## Findings
- Claim 1 [^1]
- Claim 2 [^2]

## References
[^1]: Source title — URL
[^2]: Source title — URL
```

Never fabricate URLs. If a fact cannot be corroborated, mark it `[unverified]`.
