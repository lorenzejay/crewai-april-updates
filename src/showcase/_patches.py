"""Runtime patches applied on ``import showcase``.

Upstream bug: ``crewai.state.checkpoint_listener._do_checkpoint`` calls
``state.model_dump(mode="json")`` without a fallback. If the live
``RuntimeState`` includes any ``BaseTool`` with an ``args_schema:
type[BaseModel]`` field (e.g. the Daytona tools), pydantic raises
``PydanticSerializationError: Unable to serialize unknown type:
<class 'pydantic._internal._model_construction.ModelMetaclass'>`` — the
``PlainSerializer`` declared on the field is not applied when the tool
is dumped as a nested member of the root state.

This module wraps ``_do_checkpoint`` to pass a ``fallback`` that converts
class references to their JSON schema (or a ``__class__`` stub for
non-pydantic classes).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _json_fallback(v: Any) -> Any:
    """Serialise values that pydantic's JSON encoder can't handle natively."""
    if isinstance(v, type):
        if issubclass(v, BaseModel):
            try:
                return v.model_json_schema()
            except Exception:  # noqa: BLE001 — best-effort stub
                return {"__class__": v.__qualname__}
        return {"__class__": f"{v.__module__}.{v.__qualname__}"}
    return str(v)


def _apply_checkpoint_serialization_fix() -> None:
    import crewai.state.checkpoint_listener as cl

    if getattr(cl, "_showcase_patched", False):
        return

    original_do_checkpoint = cl._do_checkpoint

    def _patched_do_checkpoint(state, cfg, event=None):  # type: ignore[no-untyped-def]
        cl._prepare_entities(state.root)
        payload = state.model_dump(mode="json", fallback=_json_fallback)
        if event is not None:
            payload["trigger"] = event.type
        data = json.dumps(payload)
        location = cfg.provider.checkpoint(
            data,
            cfg.location,
            parent_id=state._parent_id,
            branch=state._branch,
        )
        state._chain_lineage(cfg.provider, location)

        checkpoint_id = cfg.provider.extract_id(location)
        cl.logger.info(
            "Checkpoint saved. Resume with: crewai checkpoint resume %s",
            checkpoint_id,
        )
        if cfg.max_checkpoints is not None:
            cfg.provider.prune(
                cfg.location, cfg.max_checkpoints, branch=state._branch
            )

    cl._do_checkpoint = _patched_do_checkpoint
    cl._do_checkpoint_original = original_do_checkpoint  # type: ignore[attr-defined]
    cl._showcase_patched = True  # type: ignore[attr-defined]


_apply_checkpoint_serialization_fix()
