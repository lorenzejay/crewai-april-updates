"""Minimal Crew checkpointing example aligned with the CrewAI docs.

See: https://docs.crewai.com/en/concepts/checkpointing

Three tasks: **research** → **tune for {audience}** → **improve tone** (one checkpoint
per completed task). Helpers: ``run_fresh``, ``resume_from``, ``fork_from`` (refuses
terminal all-done snapshots unless ``allow_completed=True``). See
``CHECKPOINT_ROOT``, ``list_crew_checkpoint_files`` for demos.
"""

from __future__ import annotations

import json
from pathlib import Path

from crewai import Agent, Crew, Task
from crewai.state.checkpoint_config import CheckpointConfig

from showcase.shared import get_llm

# JSON checkpoints in repo-root ``.checkpoints/`` (default JsonProvider layout).
_CHECKPOINT_DIR = Path(__file__).resolve().parents[3] / ".checkpoints"
# Exposed for notebooks / CLI: ``crewai checkpoint --location <this> list``
CHECKPOINT_ROOT = str(_CHECKPOINT_DIR)

DEFAULT_TOPIC = "The 2026 state of open-source AI coding agents."
DEFAULT_AUDIENCE = "senior engineers evaluating CrewAI for a production system"


def _crew_completed_vs_total_json(restore_from: str) -> tuple[int, int] | None:
    """If ``restore_from`` points at a crew JSON snapshot, return ``(done, total)`` tasks."""
    if "#" in restore_from:
        return None
    path = Path(restore_from)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    for entity in data.get("entities", []):
        if entity.get("entity_type") != "crew":
            continue
        tasks = entity.get("tasks") or []
        if not tasks:
            return None
        done = sum(1 for t in tasks if t.get("output") is not None)
        return done, len(tasks)
    return None


def list_crew_checkpoint_files(*, branch: str = "main", limit: int = 20) -> list[Path]:
    """Newest-first JSON paths under ``.checkpoints/<branch>/`` (handy after ``run_fresh``)."""
    root = _CHECKPOINT_DIR / branch
    if not root.is_dir():
        return []
    files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def forkable_crew_checkpoint_paths(*, branch: str = "main", limit: int = 30) -> list[Path]:
    """Like ``list_crew_checkpoint_files`` but only snapshots where a crew task is still pending."""
    out: list[Path] = []
    for path in list_crew_checkpoint_files(branch=branch, limit=limit):
        stats = _crew_completed_vs_total_json(str(path))
        if stats is None:
            continue
        done, total = stats
        if done < total:
            out.append(path)
    return out


def checkpoint_config(*, restore_from: str | None = None) -> CheckpointConfig:
    """Docs defaults: JsonProvider, ``task_completed``, optional ``restore_from``."""
    return CheckpointConfig(
        location=str(_CHECKPOINT_DIR),
        on_events=["task_completed"],
        max_checkpoints=10,
        restore_from=restore_from,
    )


def build_crew() -> Crew:
    """Research → audience tune → tone polish. ``checkpoint=…`` saves after each task."""
    researcher = Agent(
        role="Research Analyst",
        goal="Surface the most load-bearing facts about {topic}",
        backstory="Concrete, verifiable facts only — no marketing tone.",
        llm=get_llm(),
    )
    strategist = Agent(
        role="Audience Strategist",
        goal="Shape content so it lands for {audience}",
        backstory=(
            "Chooses depth, jargon level, framing, and examples for the reader. "
            "Does not invent facts beyond the supplied research."
        ),
        llm=get_llm(),
    )
    editor = Agent(
        role="Line Editor",
        goal="Improve readability and tone without changing substance",
        backstory=(
            "Tightens sentences, improves flow, and warms or sharpens voice as fits "
            "the draft. Never adds claims or alters who the piece is written for."
        ),
        llm=get_llm(),
    )

    research = Task(
        description=(
            "Topic: {topic}\n\n"
            "List 4–5 one-sentence facts. Each must be concrete and checkable."
        ),
        expected_output="Markdown bullet list.",
        agent=researcher,
    )
    tuned_for_audience = Task(
        description=(
            "Topic: {topic}\n"
            "Audience: {audience}\n\n"
            "Using ONLY the research above, produce a short markdown draft aimed at "
            "this audience.\n\n"
            "Focus on *fit*: vocabulary, assumptions, what to emphasize, one example "
            "idea they'd care about. Do not worry about literary polish yet — clear "
            "and direct is fine."
        ),
        expected_output="Markdown draft (rough tone OK).",
        agent=strategist,
        context=[research],
    )
    improve_tone = Task(
        description=(
            "Revise the audience-tuned draft below.\n\n"
            "Goals: smoother sentences, clearer rhythm, consistent voice. You may "
            "reorder sentences for impact.\n\n"
            "Hard rules: do not add new facts, statistics, or sources; do not change "
            "the target audience or the core message; keep length roughly similar."
        ),
        expected_output="Polished markdown — same substance and audience as the draft.",
        agent=editor,
        context=[tuned_for_audience],
    )

    return Crew(
        agents=[researcher, strategist, editor],
        tasks=[research, tuned_for_audience, improve_tone],
        verbose=True,
        checkpoint=checkpoint_config(),
    )


def run_fresh(topic: str | None = None, audience: str | None = None) -> Crew:
    """Kick off with checkpointing already on the crew (see ``build_crew``)."""
    crew = build_crew()
    crew.kickoff(
        inputs={
            "topic": topic or DEFAULT_TOPIC,
            "audience": audience or DEFAULT_AUDIENCE,
        },
    )
    return crew


def resume_from(restore_from: str) -> Crew:
    """Continue the **same** branch with snapshot inputs — not for changing ``topic``/``audience``.

    Use this after an interrupt or error when you want the exact same run to proceed.
    """
    cfg = checkpoint_config(restore_from=restore_from)
    crew = Crew.from_checkpoint(cfg)
    # Continue writing checkpoints on this run (clear restore target only).
    crew.checkpoint = cfg.model_copy(update={"restore_from": None})
    crew.kickoff()
    return crew


def fork_from(
    restore_from: str,
    *,
    branch: str = "experiment",
    inputs: dict[str, str] | None = None,
    allow_completed: bool = False,
) -> Crew:
    """Restore a checkpoint on a **new** branch, then ``kickoff`` with optional input overrides.

    Pass only the keys you want to change (e.g. ``{"audience": "…"}``); the rest stay
    from the checkpoint. Matches ``Crew.fork`` + ``kickoff(inputs=…)`` in the docs.

    **Important:** if the snapshot already has **every** task completed, a forked
    ``kickoff`` has nothing left to run (same as resume). For a meaningful fork,
    use a checkpoint from *after* task 1 or 2, not the final file — or pass
    ``allow_completed=True`` to skip this guard (SQLite ``db#id`` paths skip it
    automatically because we cannot inspect them here).
    """
    stats = _crew_completed_vs_total_json(restore_from)
    if stats is not None and not allow_completed:
        done, total = stats
        if done >= total:
            raise ValueError(
                f"All {total} crew tasks are already done in this snapshot — fork "
                "would not re-run work. Pick an earlier checkpoint (e.g. under "
                f"{_CHECKPOINT_DIR / 'main'!s} with only research or audience-tune "
                "complete), or pass allow_completed=True."
            )
    cfg = checkpoint_config(restore_from=restore_from)
    crew = Crew.fork(cfg, branch=branch)
    crew.checkpoint = cfg.model_copy(update={"restore_from": None})
    crew.kickoff(inputs=inputs)
    return crew


if __name__ == "__main__":
    result_crew = run_fresh()
    print(result_crew.tasks[-1].output.raw)
    # resume_from("./.checkpoints.db#20260423T104512_ab12cd34")
    # fork_from("./.checkpoints/20260423T154939_71d1a9d5_p-20260423T154919_36305730", branch="experiment", inputs={"audience": "senior executives looking for agentic transformation within their org"})
