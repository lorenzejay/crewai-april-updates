"""Module 04 demo: checkpointing on a Crew, with a clean resume vs fork split.

Two complementary demos, sharing one SQLite DB at the repo-root default path.

Crew demo — a 2-agent launch-copy pipeline:
    Strategist (positioning)  →  Copywriter (tagline + value props)

Each task completion writes a checkpoint. From any of those checkpoints you can:

    RESUME  — continue the same branch with the original inputs. Completed
              tasks stay; remaining tasks run normally. Same lineage.

    FORK    — restore the same state but assign a NEW branch label and
              optionally override inputs. Later tasks re-render with new
              values. Parent_id still points at the source — a true branch.

Helpers: ``run_fresh()``, ``resume_from()``, ``fork_from()``.

Agent demo — standalone ``Agent.kickoff()`` with context-threaded resume.
Unchanged from the prior iteration. Helpers: ``run_fresh_agent()``,
``resume_agent()``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from crewai import Agent, Crew, Task
from crewai.lite_agent_output import LiteAgentOutput
from crewai.state.checkpoint_config import CheckpointConfig
from crewai.state.provider.sqlite_provider import SqliteProvider

from showcase.shared import get_llm

CHECKPOINT_DB = str(Path(__file__).resolve().parents[3] / ".checkpoints.db")

DEFAULT_IDEA = (
    "A CLI that generates deterministic database migration plans from a Git diff."
)
DEFAULT_TONE = "confident, specific, no hype"

# Agent-demo defaults (unchanged)
DEFAULT_AGENT_PROMPT = (
    "In 80 words, explain why WAL-mode SQLite is a good fit for a per-process "
    "checkpoint store. Focus on concurrency and crash safety."
)
DEFAULT_AGENT_FOLLOWUP = (
    "Now name TWO specific failure modes to watch for in that design. "
    "One sentence each."
)


# ===================================================================
# Crew demo: build + checkpoint + resume + fork
# ===================================================================


def _checkpoint_config(restore_from: str | None = None) -> CheckpointConfig:
    """Checkpoint after every task completion. Keeps 20 rows per branch."""
    return CheckpointConfig(
        location=CHECKPOINT_DB,
        provider=SqliteProvider(),
        on_events=["task_completed"],
        max_checkpoints=20,
        restore_from=restore_from,
    )


def _build_crew() -> Crew:
    """Build a fresh 2-agent launch-copy Crew. Inputs: {idea}, {tone}."""
    strategist = Agent(
        role="Positioning Strategist",
        goal="Name the single sharpest positioning for {idea}",
        backstory=(
            "Seasoned PMM who cuts through fluff. Writes positioning that "
            "names the target reader, their pain, and one clear differentiator."
        ),
        llm=get_llm(),
    )
    copywriter = Agent(
        role="Launch Copywriter",
        goal="Turn positioning into launch copy that lands",
        backstory="Writes taglines that survive a CEO's first read.",
        llm=get_llm(),
    )

    positioning = Task(
        description=(
            "Produce a one-paragraph positioning statement for {idea}.\n"
            "Name the target reader, the pain, and the single differentiator.\n"
            "Tone: {tone}."
        ),
        expected_output="One paragraph, 3–4 sentences max.",
        agent=strategist,
    )
    write_copy = Task(
        description=(
            "Turn the positioning above into launch copy for {idea}. "
            "Tone: {tone}.\n"
            "Respond in Markdown with exactly two sections:\n"
            "  ## Tagline — one line, under 12 words.\n"
            "  ## Value props — three bullets, each under 12 words."
        ),
        expected_output="Markdown with '## Tagline' and '## Value props' sections.",
        agent=copywriter,
        context=[positioning],
    )

    return Crew(agents=[strategist, copywriter], tasks=[positioning, write_copy])


def run_fresh(idea: str | None = None, tone: str | None = None) -> Crew:
    """Fresh Crew kickoff with checkpointing on.

    Writes two checkpoints (one per ``task_completed``). Returns the crew
    so the caller can inspect ``crew.tasks[-1].output``.
    """
    crew = _build_crew()
    inputs = {"idea": idea or DEFAULT_IDEA, "tone": tone or DEFAULT_TONE}
    crew.kickoff(inputs=inputs, from_checkpoint=_checkpoint_config())
    return crew


def resume_from(checkpoint_path: str) -> Crew:
    """Resume on the SAME branch — continue as if nothing happened.

    Rehydrates the snapshot. Any task that already completed keeps its output.
    Remaining tasks run with the original inputs from the snapshot. New
    checkpoints land on the same branch with ``parent_id`` pointing at the
    snapshot — a straight continuation of the lineage.
    """
    cfg = _checkpoint_config(restore_from=checkpoint_path)
    crew = Crew.from_checkpoint(cfg)
    # from_checkpoint doesn't re-attach `.checkpoint` — wire it so the
    # resumed run keeps writing checkpoints.
    crew.checkpoint = cfg.model_copy(update={"restore_from": None})
    crew.kickoff()
    return crew


def fork_from(
    checkpoint_path: str,
    branch: str = "experiment",
    idea: str | None = None,
    tone: str | None = None,
) -> Crew:
    """Fork onto a NEW branch, optionally overriding inputs.

    Same restoration as ``resume_from``, but ``Crew.fork(cfg, branch=...)``
    assigns a new branch label so every subsequent checkpoint carries it.
    ``parent_id`` still points at the source — so the new branch is a
    discoverable fork in the lineage tree, not a separate run.

    ``idea`` / ``tone`` are forwarded to ``kickoff(inputs=...)`` so any task
    that hasn't completed yet (or any task re-running on the new branch)
    renders its ``{idea}`` / ``{tone}`` placeholders with the new values.
    """
    cfg = _checkpoint_config(restore_from=checkpoint_path)
    crew = Crew.fork(cfg, branch=branch)
    crew.checkpoint = cfg.model_copy(update={"restore_from": None})

    overrides: dict[str, str] = {}
    if idea is not None:
        overrides["idea"] = idea
    if tone is not None:
        overrides["tone"] = tone
    crew.kickoff(inputs=overrides or None)
    return crew


# ===================================================================
# Agent demo: fresh + resume (unchanged from prior iteration)
# ===================================================================


def _analyst() -> Agent:
    return Agent(
        role="Architecture Analyst",
        goal="Explain a piece of architecture clearly",
        backstory="Senior engineer who writes crisp technical explainers.",
        llm=get_llm(),
    )


def _agent_checkpoint_config(restore_from: str | None = None) -> CheckpointConfig:
    return CheckpointConfig(
        location=CHECKPOINT_DB,
        provider=SqliteProvider(),
        on_events=["lite_agent_execution_completed"],
        max_checkpoints=20,
        restore_from=restore_from,
    )


async def run_fresh_agent(prompt: str | None = None) -> LiteAgentOutput:
    """Kick off a fresh Architecture Analyst agent with checkpointing."""
    agent = _analyst()
    return await agent.kickoff(
        prompt or DEFAULT_AGENT_PROMPT,
        from_checkpoint=_agent_checkpoint_config(),
    )


async def resume_agent(
    prior_output: str,
    new_prompt: str,
    checkpoint_path: str,
) -> LiteAgentOutput:
    """Resume an agent kickoff with a new prompt, threading prior context in.

    The checkpoint restores agent config + tool usage counters, but NOT the
    prior kickoff's conversation scratchpad — so the caller passes the prior
    ``output.raw`` and it's threaded into the new message explicitly.
    """
    agent = _analyst()
    message = f"You previously wrote:\n\n{prior_output}\n\n{new_prompt}"
    return await agent.kickoff(
        message,
        from_checkpoint=_agent_checkpoint_config(restore_from=checkpoint_path),
    )


# ===================================================================
# CLI entry point — runs the Crew demo + an agent demo as sanity check
# ===================================================================


def _latest_crew_checkpoint_id() -> str | None:
    """Newest crew checkpoint id, for chaining run_fresh → resume demos."""
    import sqlite3

    db_path = Path(CHECKPOINT_DB)
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT id FROM checkpoints "
            "WHERE json(data) LIKE '%Positioning Strategist%' "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def _latest_agent_checkpoint_id() -> str | None:
    import sqlite3

    db_path = Path(CHECKPOINT_DB)
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as db:
        row = db.execute(
            "SELECT id FROM checkpoints "
            "WHERE json(data) LIKE '%Architecture Analyst%' "
            "ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    # --- Crew demo: fresh kickoff ---
    crew = run_fresh()
    print("=== Launch copy (main branch) ===\n")
    print(crew.tasks[-1].output.raw)

    # --- Crew demo: fork with a different tone ---
    ck = _latest_crew_checkpoint_id()
    if ck:
        print(f"\n=== Forking from {ck} with tone='aggressive' ===\n")
        forked = fork_from(
            f"{CHECKPOINT_DB}#{ck}",
            branch="aggressive",
            tone="aggressive and irreverent",
        )
        print(forked.tasks[-1].output.raw)

    # --- Agent demo: fresh + resume ---
    print("\n=== Agent kickoff #1 ===\n")
    first = asyncio.run(run_fresh_agent())
    print(first.raw)

    ck_agent = _latest_agent_checkpoint_id()
    if ck_agent:
        print(f"\n=== Agent kickoff #2 (resume from {ck_agent}) ===\n")
        second = asyncio.run(
            resume_agent(
                prior_output=first.raw,
                new_prompt=DEFAULT_AGENT_FOLLOWUP,
                checkpoint_path=f"{CHECKPOINT_DB}#{ck_agent}",
            )
        )
        print(second.raw)
