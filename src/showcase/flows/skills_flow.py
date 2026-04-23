"""Module 01 demo: a Flow that equips an Agent with skills discovered from disk."""

from __future__ import annotations

from pathlib import Path

from crewai import Agent
from crewai.flow import Flow, listen, start
from pydantic import BaseModel

from showcase.shared import get_llm

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


class SkillsState(BaseModel):
    topic: str = ""
    result: str = ""


class SkillsFlow(Flow[SkillsState]):
    """Runs a research agent with two skills loaded from SKILLS_DIR."""

    @start()
    def pick_topic(self) -> None:
        if not self.state.topic:
            self.state.topic = "The evolution of multi-agent coordination protocols in 2026"

    @listen(pick_topic)
    async def research(self) -> str:
        researcher = Agent(
            role="Research Analyst",
            goal=f"Produce a well-cited 150-word brief on: {self.state.topic}",
            backstory="Senior analyst who follows the installed skills to the letter.",
            llm=get_llm(),
            skills=[SKILLS_DIR],
            verbose=True,
        )
        output = await researcher.kickoff(
            f"Write a 150-word briefing on: {self.state.topic}. "
            "Respond with Markdown containing '## Findings' and '## References' sections."
        )
        self.state.result = output.raw
        return self.state.result


def run() -> str:
    flow = SkillsFlow()
    flow.kickoff()
    return flow.state.result


if __name__ == "__main__":
    print(run())
