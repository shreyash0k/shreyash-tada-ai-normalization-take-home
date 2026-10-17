"""A small JSON Schema validator for the canonical output schema.

Supports the subset used by ``docs/canonical/normalized-output.schema.json``: ``type``
(string or list), ``properties``, ``required``, ``additionalProperties``
(boolean or schema), ``items``, ``enum``, ``const``, ``pattern``, ``oneOf``,
and local ``$ref`` into ``$defs``. It exists so tests can check fixture
outputs without a third-party package.
"""
import re
from typing import Any

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Return a list of human-readable violations (empty when valid)."""
    root = root if root is not None else schema
    errors: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported $ref {ref}"]
        target = root["$defs"][ref[len("#/$defs/"):]]
        return validate(instance, target, root, path)
    if "oneOf" in schema:
        passing = [alt for alt in schema["oneOf"] if not validate(instance, alt, root, path)]
        if len(passing) != 1:
            return [f"{path}: matched {len(passing)} of {len(schema['oneOf'])} oneOf alternatives"]
        return []

    declared = schema.get("type")
    if declared is not None:
        allowed = declared if isinstance(declared, list) else [declared]
        if not any(_TYPES[t](instance) for t in allowed):
            errors.append(f"{path}: expected type {allowed}, got {type(instance).__name__}")
            return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum")
    if "pattern" in schema and isinstance(instance, str) and not re.search(schema["pattern"], instance):
        errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                errors.append(f"{path}: missing required property {name!r}")
        for name, value in instance.items():
            if name in props:
                errors.extend(validate(value, props[name], root, f"{path}.{name}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property {name!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(validate(value, schema["additionalProperties"], root, f"{path}.{name}"))
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], root, f"{path}[{index}]"))
    return errors
