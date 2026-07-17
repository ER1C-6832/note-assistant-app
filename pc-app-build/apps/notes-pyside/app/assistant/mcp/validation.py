"""Small deterministic validator for the frozen descriptor schema subset."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .contracts import JsonValue


class SchemaValidationError(ValueError):
    pass


def validate_arguments(
    value: object, schema: Mapping[str, JsonValue], *, path: str = "arguments"
) -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, Mapping):
            raise SchemaValidationError(f"{path} must be an object")
        properties = schema.get("properties")
        property_map = properties if isinstance(properties, Mapping) else {}
        required = schema.get("required")
        required_names = (
            required if isinstance(required, Sequence) and not isinstance(required, str) else ()
        )
        for name in required_names:
            if isinstance(name, str) and name not in value:
                raise SchemaValidationError(f"{path}.{name} is required")
        if schema.get("additionalProperties") is False:
            unknown = sorted(str(key) for key in value if key not in property_map)
            if unknown:
                raise SchemaValidationError(f"{path} contains unknown fields: {', '.join(unknown)}")
        for key, item in value.items():
            child = property_map.get(key)
            if isinstance(key, str) and isinstance(child, Mapping):
                validate_arguments(item, child, path=f"{path}.{key}")
        one_of = schema.get("oneOf")
        if isinstance(one_of, Sequence) and not isinstance(one_of, (str, bytes, bytearray)):
            matches = 0
            for branch in one_of:
                if not isinstance(branch, Mapping):
                    continue
                branch_required = branch.get("required")
                names = (
                    branch_required
                    if isinstance(branch_required, Sequence)
                    and not isinstance(branch_required, (str, bytes, bytearray))
                    else ()
                )
                if names and all(isinstance(name, str) and name in value for name in names):
                    matches += 1
            if matches != 1:
                raise SchemaValidationError(f"{path} must match exactly one allowed argument shape")
        return

    if expected == "array":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise SchemaValidationError(f"{path} must be an array")
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            raise SchemaValidationError(f"{path} must contain at least {minimum} items")
        if isinstance(maximum, int) and len(value) > maximum:
            raise SchemaValidationError(f"{path} must contain at most {maximum} items")
        if schema.get("uniqueItems") is True:
            markers = [repr(item) for item in value]
            if len(set(markers)) != len(markers):
                raise SchemaValidationError(f"{path} must not contain duplicates")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                validate_arguments(item, item_schema, path=f"{path}[{index}]")
        return

    if expected == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path} must be a string")
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            raise SchemaValidationError(f"{path} is too short")
        if isinstance(maximum, int) and len(value) > maximum:
            raise SchemaValidationError(f"{path} is too long")
        enum = schema.get("enum")
        if isinstance(enum, Sequence) and not isinstance(enum, str) and value not in enum:
            raise SchemaValidationError(f"{path} has an unsupported value")
        return

    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SchemaValidationError(f"{path} must be an integer")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int) and value < minimum:
            raise SchemaValidationError(f"{path} is below the minimum")
        if isinstance(maximum, int) and value > maximum:
            raise SchemaValidationError(f"{path} is above the maximum")
        return

    if expected == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path} must be a boolean")
        return

    raise SchemaValidationError(f"{path} uses an unsupported schema type")
