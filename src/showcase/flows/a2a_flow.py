"""Module 05 demo: A2A protocol — both sides.

This module shows two patterns in a single file:

1. **Server-side agent** (:func:`build_server_agent`) — an agent configured
   with :class:`A2AServerConfig`. Call ``agent.to_agent_card(url)`` to emit
   an A2A-compliant card that other clients can discover.

2. **Client-side Flow** (:class:`A2AClientFlow`) — a coordinator agent with
   :class:`A2AClientConfig`. With ``fail_fast=False`` it gracefully falls
   back to local execution when the remote endpoint isn't reachable, which
   keeps the notebook demo runnable without a live server.
"""

from __future__ import annotations

import os

from crewai import Agent
from crewai.a2a import A2AClientConfig, A2AServerConfig
from crewai.flow import Flow, listen, start
from pydantic import BaseModel

from showcase.shared import get_llm


class A2AClientState(BaseModel):
    question: str = "Summarize the key 2026 improvements to agent-to-agent delegation in one paragraph."
    answer: str = ""


def build_server_agent() -> Agent:
    """A worker agent exposed as an A2A server."""
    return Agent(
        role="Protocol Analyst",
        goal="Explain A2A protocol mechanics clearly and briefly",
        backstory="Standards nerd who tracks A2A spec drift.",
        llm=get_llm(),
        a2a=A2AServerConfig(
            name="ProtocolAnalyst",
            description="Answers questions about the A2A protocol.",
            version="1.0.0",
        ),
    )


class A2AClientFlow(Flow[A2AClientState]):
    """A coordinator that can delegate to a remote A2A worker."""

    @start()
    async def coordinate(self) -> str:
        endpoint = os.getenv("A2A_SHOWCASE_ENDPOINT", "http://localhost:8765/.well-known/agent-card.json")
        coordinator = Agent(
            role="Delegation Coordinator",
            goal="Answer the question using a remote specialist when one is available",
            backstory="Routes work to the right agent.",
            llm=get_llm(),
            a2a=A2AClientConfig(
                endpoint=endpoint,
                timeout=30,
                max_turns=3,
                fail_fast=False,  # degrade gracefully when the worker isn't running
            ),
        )
        output = await coordinator.kickoff(
            f"{self.state.question}\n\nRespond with a single paragraph."
        )
        self.state.answer = output.raw
        return self.state.answer


def run_client(question: str | None = None) -> str:
    flow = A2AClientFlow()
    flow.kickoff(inputs={"question": question} if question else None)
    return flow.state.answer


if __name__ == "__main__":
    print(run_client())
