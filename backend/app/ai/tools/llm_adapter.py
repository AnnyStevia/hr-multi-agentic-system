"""Convert provider-agnostic BaseTool instances into LLM ToolDefinition schemas."""

from __future__ import annotations

from copy import deepcopy
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
    """Flatten $defs/$refs and simplify optional unions for Gemini/Mistral."""
    defs = dict(schema.get("$defs") or schema.get("definitions") or {})
    parameters = deepcopy(schema)
    parameters.pop("$defs", None)
    parameters.pop("definitions", None)
    parameters.pop("$schema", None)

    parameters = _resolve_refs(parameters, defs)
    parameters = _simplify_nullable_unions(parameters)

    if "type" not in parameters:
        parameters["type"] = "object"
    if "properties" not in parameters:
        parameters["properties"] = {}
    return parameters


def _resolve_refs(node: Any, defs: dict[str, Any], *, stack: tuple[str, ...] = ()) -> Any:
    """Inline JSON Schema $ref pointers into $defs (Gemini rejects dangling refs)."""
    if isinstance(node, list):
        return [_resolve_refs(item, defs, stack=stack) for item in node]
    if not isinstance(node, dict):
        return node

    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        name = ref.split("/")[-1]
        if name in stack:
            # Break cycles; return a permissive object.
            return {"type": "object"}
        target = defs.get(name)
        if target is None:
            return {"type": "object"}
        resolved = _resolve_refs(deepcopy(target), defs, stack=stack + (name,))
        # Merge sibling keywords (e.g. description) onto the resolved target.
        extras = {k: v for k, v in node.items() if k != "$ref"}
        if extras:
            if isinstance(resolved, dict):
                merged = dict(resolved)
                merged.update(extras)
                return merged
        return resolved

    return {key: _resolve_refs(value, defs, stack=stack) for key, value in node.items()}


def _simplify_nullable_unions(node: Any) -> Any:
    """Turn anyOf=[T, null] into a plain T schema (optional via default / not required)."""
    if isinstance(node, list):
        return [_simplify_nullable_unions(item) for item in node]
    if not isinstance(node, dict):
        return node

    simplified = {key: _simplify_nullable_unions(value) for key, value in node.items()}
    any_of = simplified.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        non_null = [item for item in any_of if not _is_null_schema(item)]
        has_null = any(_is_null_schema(item) for item in any_of)
        if has_null and len(non_null) == 1 and isinstance(non_null[0], dict):
            merged = dict(non_null[0])
            for key, value in simplified.items():
                if key == "anyOf":
                    continue
                merged[key] = value
            return merged
    return simplified


def _is_null_schema(item: Any) -> bool:
    return isinstance(item, dict) and item.get("type") == "null"
