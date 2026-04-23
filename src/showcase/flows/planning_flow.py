"""Module 02 demo: Plan-and-Execute builds a web app inside a Daytona sandbox.

The executor plans the steps of a small todo-list single-page app, writes each
file into an isolated Daytona sandbox via `DaytonaFileTool`, and the Flow
exposes a live preview URL for the notebook to render.
"""

from __future__ import annotations

import os

from crewai import Agent
from crewai.agent.planning_config import PlanningConfig
from crewai.flow import Flow, listen, start
from crewai_tools import DaytonaExecTool, DaytonaFileTool
from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig
from pydantic import BaseModel

from showcase.shared import get_llm

PREVIEW_PORT = 8000
APP_DIR = "/home/daytona/app"
# Auto-cleanup: stop the sandbox after this many idle minutes (preview iframe
# loads don't count as activity), then delete immediately once stopped.
AUTO_STOP_MINUTES = 4
AUTO_DELETE_MINUTES = 0

DEFAULT_REQUEST = (
    "Build a single-page todo list web app. Users can add a todo via an input "
    "+ button, check items off, and delete them. Persist state in "
    "localStorage so refreshes keep the list. Style it cleanly with inline "
    "CSS — system fonts, rounded cards, high contrast, sensible spacing. "
    f"Write exactly three files at {APP_DIR}: index.html (loads style.css "
    "and app.js), style.css, app.js. Do NOT start any servers — the Flow "
    "handles serving. Verify with the file tool's list action before finishing."
)


class AppBuilderState(BaseModel):
    request: str = ""
    sandbox_id: str = ""
    build_log: str = ""
    preview_url: str = ""
    preview_token: str = ""
    rendered_html: str = ""


def _daytona_client() -> Daytona:
    api_key = os.getenv("DAYTONA_API_KEY")
    return Daytona(DaytonaConfig(api_key=api_key)) if api_key else Daytona()


class AppBuilderFlow(Flow[AppBuilderState]):
    """Plan → build a todo app in a Daytona sandbox → publish a preview URL."""

    @start()
    def provision_sandbox(self) -> None:
        if not self.state.request:
            self.state.request = DEFAULT_REQUEST
        sandbox = _daytona_client().create(
            CreateSandboxFromSnapshotParams(
                auto_stop_interval=AUTO_STOP_MINUTES,
                auto_delete_interval=AUTO_DELETE_MINUTES,
            )
        )
        self.state.sandbox_id = sandbox.id
        sandbox.fs.create_folder(APP_DIR, "0755")

    @listen(provision_sandbox)
    async def plan_and_build(self) -> str:
        tool_kwargs = {"sandbox_id": self.state.sandbox_id}
        builder = Agent(
            role="Frontend Engineer",
            goal="Ship a working single-page todo list web app into the sandbox",
            backstory=(
                "Ships tiny web apps end-to-end: writes clean HTML/CSS/JS, "
                "keeps dependencies zero, never leaves a file half-written."
            ),
            llm=get_llm(),
            planning_config=PlanningConfig(
                reasoning_effort="medium",
                max_attempts=3,
                max_steps=8,
            ),
            tools=[
                DaytonaFileTool(**tool_kwargs),
                DaytonaExecTool(**tool_kwargs),
            ],
            verbose=True,
        )
        output = await builder.kickoff(self.state.request)
        self.state.build_log = output.raw
        return self.state.build_log

    @listen(plan_and_build)
    def publish_preview(self) -> str:
        sandbox = _daytona_client().get(self.state.sandbox_id)
        sandbox.process.exec(
            f"cd {APP_DIR} && "
            f"nohup python3 -m http.server {PREVIEW_PORT} "
            f"> /tmp/server.log 2>&1 & disown"
        )
        link = sandbox.get_preview_link(PREVIEW_PORT)
        self.state.preview_url = link.url
        self.state.preview_token = getattr(link, "token", "") or ""
        try:
            html = sandbox.fs.download_file(f"{APP_DIR}/index.html")
            self.state.rendered_html = html.decode("utf-8", errors="replace")
        except Exception:
            self.state.rendered_html = ""
        return self.state.preview_url


def run(request: str | None = None) -> AppBuilderFlow:
    flow = AppBuilderFlow()
    inputs = {"request": request} if request else None
    flow.kickoff(inputs=inputs)
    return flow


if __name__ == "__main__":
    f = run()
    print("sandbox_id:", f.state.sandbox_id)
    print("preview:   ", f.state.preview_url)
    if f.state.rendered_html:
        print("html snippet:", f.state.rendered_html[:200])
