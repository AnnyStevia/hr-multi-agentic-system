"""Convert provider-agnostic BaseTool instances into LLM ToolDefinition schemas."""

from __future__ import annotations

from typing import Any

from app.ai.core.llm.base import ToolDefinition
from app.ai.tools.base import BaseTool


def tool_to_definition(tool: BaseTool) -> ToolDefinition:
    """Map a BaseTool to an LLM-facing ToolDefinition (JSON Schema parameters)."""
    schema = tool.input_model.model_json_schema()
    parameters = _normalize_parameters_schema(schema)
    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        parameters=parameters,
    )


def _normalize_parameters_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure a Mistral-friendly object schema without changing field semantics."""
    parameters = dict(schema)
    parameters.pop("$defs", None)
    parameters.pop("definitions", None)
    parameters.pop("$schema", None)
    if "type" not in parameters:
        parameters["type"] = "object"
    if "properties" not in parameters:
        parameters["properties"] = {}
    return parameters
