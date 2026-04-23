# CrewAI April 2026 Feature Showcase

A follow-along tour of five notable CrewAI features shipped through April 2026. Most runtime demos use a `Flow`; Module 04 uses a checkpointed `Crew`.

## Modules

| # | Module | Feature | Released | Notebook | Flow |
|---|---|---|---|---|---|
| 00 | Build with AI | AI-native docs + skills install + AMP deploy | Apr 2026 | [`00_build_with_ai.ipynb`](notebooks/00_build_with_ai.ipynb) | — (meta) |
| 01 | Agent Skills | `SKILL.md` packs with progressive disclosure | v1.12.0 | [`01_agent_skills.ipynb`](notebooks/01_agent_skills.ipynb) | `skills_flow.py` |
| 02 | Plan-and-Execute | Planner → StepExecutor → Observer executor | v1.14.0 | [`02_plan_and_execute.ipynb`](notebooks/02_plan_and_execute.ipynb) | `planning_flow.py` |
| 03 | Unified Memory | Single `Memory` API with scope isolation | PR #4420 | [`03_unified_memory.ipynb`](notebooks/03_unified_memory.ipynb) | `memory_flow.py` |
| 04 | Checkpointing | `CheckpointConfig` + resume + fork | v1.14.0–1.14.3 | [`04_checkpointing.ipynb`](notebooks/04_checkpointing.ipynb) | `checkpoint_flow.py` (Crew) |

Start with [Module 00](notebooks/00_build_with_ai.ipynb) — it sets up your coding agent for the rest of the tour.

## Setup

```bash
cd crewai-april-feature-showcase

# Create env and install (uv recommended)
uv venv
source .venv/bin/activate
uv pip install -e .

# Or with pip
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Configure providers
cp .env.example .env
# edit .env — add ANTHROPIC_API_KEY (default) and/or OPENAI_API_KEY
```

### Picking a provider

Defaults to `anthropic/claude-sonnet-4-6`. Switch via env:

```bash
export SHOWCASE_LLM=openai           # uses openai/gpt-4.1-mini
# or fully override
export SHOWCASE_MODEL=openai/gpt-4.1
```

## Running a notebook

```bash
jupyter notebook notebooks/01_agent_skills.ipynb
```

Or run a Flow directly:

```bash
python -m showcase.flows.skills_flow
python -m showcase.flows.planning_flow
python -m showcase.flows.memory_flow
python -m showcase.flows.checkpoint_flow
```

## Repo layout

```
.
├── notebooks/            # Follow-along .ipynb, one per module
├── skills/               # SKILL.md fixtures used by Module 01
├── src/showcase/
│   ├── shared/llm.py     # provider config (Claude Sonnet / OpenAI fallback)
│   └── flows/            # One demo module per feature (Flows; 04 = Crew)
├── .checkpoints/         # Created at runtime by Module 04
├── .env.example
└── pyproject.toml        # crewai[tools,qdrant,anthropic] + jupyter
```

## Cost note

Each notebook kicks off at least one LLM call. Module 02 (planning) and Module 04 (checkpointing) run 2–4 agent turns each. Expect a few cents per full run on Claude Sonnet; much less on `gpt-4.1-mini`.
