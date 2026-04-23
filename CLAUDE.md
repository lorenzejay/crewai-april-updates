# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Follow-along showcase of five CrewAI features (through April 2026): Build with AI, Agent Skills, Plan-and-Execute, Unified Memory, and Checkpointing. Each runtime demo lives in a module-numbered notebook plus a paired Flow under `src/showcase/flows/`.

## Commands

Setup (uv is preferred — the project declares `[tool.uv]` dev deps):

```bash
uv venv && source .venv/bin/activate
uv pip install -e .
cp .env.example .env   # add ANTHROPIC_API_KEY (default) and/or OPENAI_API_KEY
```

Run a single Flow end-to-end:

```bash
python -m showcase.flows.skills_flow
python -m showcase.flows.planning_flow
python -m showcase.flows.memory_flow
python -m showcase.flows.checkpoint_flow
```

Notebooks: `jupyter notebook notebooks/0X_*.ipynb`.

Tests / lint: `pytest` and `ruff` are declared as dev deps but the `tests/` directory is empty — there are no existing tests or lint config to conform to yet.

## Provider switching

All flows call `get_llm()` from `showcase.shared`, which reads env vars:

- `SHOWCASE_MODEL` — litellm-style model string, full override.
- `SHOWCASE_LLM` — `anthropic` (default, → `anthropic/claude-sonnet-4-6`) or `openai` (→ `openai/gpt-4.1-mini`).

Never hardcode a model string in flow code; always route through `get_llm()` so both provider paths keep working.

## Architecture

Most feature demos are a `crewai.flow.Flow[State]` with a pydantic `BaseModel` state and `@start()` / `@listen(previous_step)` methods. The Flow wraps one or more `Agent` + `Task` pairs that run via `task.execute_sync()` and write results back onto `self.state`. **Module 04** is different: a checkpointed `Crew` in `checkpoint_flow.py` (three tasks), not a Flow. Keep the Flow shape when adding new Flow-based demos.

Per-module specifics that aren't obvious from reading one file:

- **`skills_flow.py`** — resolves `SKILLS_DIR` with `parents[3]` from the file location (`src/showcase/flows/…` → repo root). `skills/*/SKILL.md` files are the fixtures; agents load them via the `skills=[...]` kwarg.
- **`planning_flow.py`** — uses `PlanningConfig(reasoning_effort=..., max_attempts=..., max_steps=...)` on the Agent, not a separate planner agent. The executor handles plan → step → observe → replan internally.
- **`memory_flow.py`** — constructs a `Memory` instance lazily and assigns via `object.__setattr__(self, "memory", ...)` because `Flow` attributes are frozen. Scope isolation uses `memory.scope(f"/{user_id}")`; callers write and recall through the scoped handle.
- **`checkpoint_flow.py`** — JsonProvider checkpoints under repo-root `.checkpoints/` (`CHECKPOINT_ROOT`, `parents[3]`). Three-task crew (research → audience tune → tone). `run_fresh()`, `resume_from(path)`, `fork_from(..., inputs=..., allow_completed=...)`. `fork_from` rejects JSON snapshots where every task already completed (nothing left to run). Helpers: `list_crew_checkpoint_files`, `forkable_crew_checkpoint_paths`.

## Conventions

- `from __future__ import annotations` at the top of every flow module.
- Public re-exports live in `src/showcase/shared/__init__.py` — import `get_llm` from `showcase.shared`, not the submodule.
- Package layout uses the src-layout; `pyproject.toml` points `hatch` at `src/showcase`.
