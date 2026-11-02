"""Tiny JSON Schema subset validator (type, enum, required, properties, additionalProperties, items, minItems,
maxLength). Enough for the agent battery, without third-party packages."""

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is_type(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


def errors(value, schema, path="$"):
    """List of problems; empty means valid."""
    out = []
    t = schema.get("type")
    if t is not None:
        allowed = t if isinstance(t, list) else [t]
        if not any(_is_type(value, x) for x in allowed):
            return [f"{path}: expected {'/'.join(allowed)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, str) and "maxLength" in schema and len(value) > schema["maxLength"]:
        out.append(f"{path}: longer than {schema['maxLength']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                out.append(f"{path}: missing {k}")
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    out.append(f"{path}: unexpected key {k}")
        for k, sub in props.items():
            if k in value:
                out += errors(value[k], sub, f"{path}.{k}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                out += errors(item, schema["items"], f"{path}[{i}]")
    return out
