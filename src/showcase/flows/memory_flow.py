"""Module 03 demo: Unified Memory across Flow steps.

Step 1 seeds memories about user preferences. Step 2 runs an agent that
recalls them before drafting a reply. Scope isolation keeps user A's
preferences separate from user B's.
"""

from __future__ import annotations

from crewai import Agent
from crewai.flow import Flow, listen, start
from crewai.memory import Memory
from pydantic import BaseModel

from showcase.shared import get_llm


class MemoryState(BaseModel):
    user_id: str = "user-1"
    question: str = ""
    reply: str = ""


def build_memory() -> Memory:
    """Fresh Memory instance. Default LanceDB storage is created on first use."""
    return Memory(llm=get_llm(), recency_weight=0.3, semantic_weight=0.6, importance_weight=0.1)


class MemoryFlow(Flow[MemoryState]):
    @start()
    def seed_preferences(self) -> None:
        """Seed facts into the current user's scope."""
        if self.memory is None:
            object.__setattr__(self, "memory", build_memory())
        scoped = self.memory.scope(f"/{self.state.user_id}")
        scoped.remember(
            "Prefers terse answers with bullet points and no preamble.",
            categories=["preferences", "tone"],
            importance=0.9,
        )
        scoped.remember(
            "Works in Python 3.11+ and uses uv, not pip.",
            categories=["stack"],
            importance=0.8,
        )
        scoped.remember(
            "Has a strong opinion against unnecessary abstraction in code reviews.",
            categories=["preferences", "reviews"],
            importance=0.85,
        )

    @listen(seed_preferences)
    async def answer(self) -> str:
        if not self.state.question:
            self.state.question = "How should I approach adding a new config field to this project?"

        assert self.memory is not None
        scoped = self.memory.scope(f"/{self.state.user_id}")
        hits = scoped.recall(self.state.question, limit=5)
        context = "\n".join(f"- {m.record.content}" for m in hits) or "(no memories)"

        agent = Agent(
            role="Personalized Assistant",
            goal="Reply to the user in their preferred style given what you know about them.",
            backstory="You adapt every reply to the user's known preferences.",
            llm=get_llm(),
        )
        output = await agent.kickoff(
            f"User question: {self.state.question}\n\n"
            f"What we know about the user:\n{context}\n\n"
            "Reply in a way that honors their preferences."
        )
        self.state.reply = output.raw
        return self.state.reply


def run(user_id: str = "user-1", question: str | None = None) -> str:
    flow = MemoryFlow()
    inputs = {"user_id": user_id}
    if question:
        inputs["question"] = question
    flow.kickoff(inputs=inputs)
    return flow.state.reply


if __name__ == "__main__":
    print(run())
