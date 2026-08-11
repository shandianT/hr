"""Dependency-free validation for the repository's contract subset.

This is intentionally *not* a general JSON Schema 2020-12 implementation.  It
implements only the keywords used by ``contracts/*.schema.json`` so the local
synthetic runtime can enforce those checked-in contracts without a third-party
dependency.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Union


Schema = Union[bool, Mapping[str, Any]]


class ContractValidationError(ValueError):
    """Raised when an instance does not satisfy the supported contract subset."""

    def __init__(self, path: str, keyword: str, message: str):
        self.path = path
        self.keyword = keyword
        self.message = message
        super().__init__(f"{path}: {keyword}: {message}")


def validate_or_raise(instance: Any, schema_path: Union[str, Path]) -> None:
    """Validate ``instance`` against a checked-in schema or raise ``ValueError``.

    References must be local JSON pointers (for example ``#/$defs/Identifier``).
    The supported assertion keywords are ``$ref``, ``type``, ``required``,
    ``properties``, ``additionalProperties``, ``enum``, ``const``, numeric and
    collection bounds, string length/pattern/``date-time``, ``items``,
    ``uniqueItems``, ``allOf``, ``oneOf`` and ``if``/``then``/``else``.
    """

    path = Path(schema_path)
    with path.open("r", encoding="utf-8") as stream:
        root = json.load(stream)
    if not isinstance(root, dict):
        raise ValueError(f"schema root must be an object: {path}")
    _SubsetValidator(root).validate(instance)


class _SubsetValidator:
    _SUPPORTED_KEYWORDS = {
        "$schema",
        "$id",
        "$defs",
        "$ref",
        "title",
        "description",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "enum",
        "const",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "allOf",
        "oneOf",
        "if",
        "then",
        "else",
    }
    _DATE_TIME = re.compile(
        r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
    )
    _UTC_LEAP_SECOND_DATES = {
        "1972-06-30", "1972-12-31", "1973-12-31", "1974-12-31",
        "1975-12-31", "1976-12-31", "1977-12-31", "1978-12-31",
        "1979-12-31", "1981-06-30", "1982-06-30", "1983-06-30",
        "1985-06-30", "1987-12-31", "1989-12-31", "1990-12-31",
        "1992-06-30", "1993-06-30", "1994-06-30", "1995-12-31",
        "1997-06-30", "1998-12-31", "2005-12-31", "2008-12-31",
        "2012-06-30", "2015-06-30", "2016-12-31",
    }

    def __init__(self, root: Mapping[str, Any]):
        self._root = root
        self._audit_schema(root, "$")

    def validate(self, instance: Any) -> None:
        self._validate(instance, self._root, "$")

    def _validate(self, instance: Any, schema: Schema, path: str) -> None:
        if schema is True:
            return
        if schema is False:
            self._fail(path, "schema", "the false schema rejects every instance")
        if not isinstance(schema, Mapping):
            raise ValueError(f"unsupported non-object schema at {path}")
        reference = schema.get("$ref")
        if reference is not None:
            self._validate(instance, self._resolve_reference(reference), path)

        for subschema in self._schema_sequence(schema, "allOf", path):
            self._validate(instance, subschema, path)

        if "oneOf" in schema:
            matches = 0
            failures: List[ContractValidationError] = []
            for subschema in self._schema_sequence(schema, "oneOf", path):
                try:
                    self._validate(instance, subschema, path)
                except ContractValidationError as error:
                    failures.append(error)
                else:
                    matches += 1
            if matches != 1:
                detail = f"expected exactly one matching branch, found {matches}"
                if matches == 0 and failures:
                    detail += f"; first failure: {failures[0]}"
                self._fail(path, "oneOf", detail)

        if "if" in schema:
            condition_matches = self._matches(instance, schema["if"], path)
            branch_name = "then" if condition_matches else "else"
            if branch_name in schema:
                self._validate(instance, schema[branch_name], path)

        expected_type = schema.get("type")
        if expected_type is not None and not self._has_type(instance, expected_type):
            self._fail(
                path,
                "type",
                f"expected {expected_type!r}, got {self._type_name(instance)}",
            )

        if "const" in schema and not self._json_equal(instance, schema["const"]):
            self._fail(path, "const", f"expected {schema['const']!r}")

        if "enum" in schema:
            choices = schema["enum"]
            if not isinstance(choices, list):
                raise ValueError(f"enum must be an array at {path}")
            if not any(self._json_equal(instance, choice) for choice in choices):
                self._fail(path, "enum", f"value {instance!r} is not allowed")

        if isinstance(instance, dict):
            self._validate_object(instance, schema, path)
        elif isinstance(instance, list):
            self._validate_array(instance, schema, path)
        elif isinstance(instance, str):
            self._validate_string(instance, schema, path)
        elif self._is_number(instance):
            self._validate_number(instance, schema, path)

    def _validate_object(
        self, instance: Dict[str, Any], schema: Mapping[str, Any], path: str
    ) -> None:
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise ValueError(f"required must be an array at {path}")
        for name in required:
            if name not in instance:
                self._fail(path, "required", f"missing property {name!r}")

        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError(f"properties must be an object at {path}")
        for name, subschema in properties.items():
            if name in instance:
                self._validate(instance[name], subschema, self._child_path(path, name))

        extras = [name for name in instance if name not in properties]
        additional = schema.get("additionalProperties", True)
        if additional is False and extras:
            self._fail(
                path,
                "additionalProperties",
                f"unexpected properties: {', '.join(sorted(extras))}",
            )
        if isinstance(additional, Mapping) or isinstance(additional, bool):
            if additional is not True and additional is not False:
                for name in extras:
                    self._validate(
                        instance[name], additional, self._child_path(path, name)
                    )
        else:
            raise ValueError(f"additionalProperties has invalid schema at {path}")

    def _validate_array(
        self, instance: List[Any], schema: Mapping[str, Any], path: str
    ) -> None:
        self._check_bound(len(instance), schema, "minItems", "minimum", path)
        self._check_bound(len(instance), schema, "maxItems", "maximum", path)

        if schema.get("uniqueItems") is True:
            for index, item in enumerate(instance):
                if any(self._json_equal(item, prior) for prior in instance[:index]):
                    self._fail(path, "uniqueItems", f"duplicate item at index {index}")

        if "items" in schema:
            item_schema = schema["items"]
            for index, item in enumerate(instance):
                self._validate(item, item_schema, f"{path}[{index}]")

    def _validate_string(
        self, instance: str, schema: Mapping[str, Any], path: str
    ) -> None:
        self._check_bound(len(instance), schema, "minLength", "minimum", path)
        self._check_bound(len(instance), schema, "maxLength", "maximum", path)

        if "pattern" in schema:
            pattern = schema["pattern"]
            if not isinstance(pattern, str):
                raise ValueError(f"pattern must be a string at {path}")
            if re.search(pattern, instance) is None:
                self._fail(path, "pattern", f"value does not match {pattern!r}")

        format_name = schema.get("format")
        if format_name is not None and format_name != "date-time":
            raise ValueError(f"unsupported string format at {path}: {format_name!r}")
        if format_name == "date-time":
            if self._DATE_TIME.fullmatch(instance) is None:
                self._fail(path, "format", "expected an RFC 3339 date-time")
            normalized = instance.replace("t", "T").replace("z", "Z")
            if normalized[17:19] == "60":
                normalized = normalized[:17] + "59" + normalized[19:]
            try:
                parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            except ValueError:
                self._fail(path, "format", "date-time is not calendar-valid")
            if parsed.tzinfo is None:
                self._fail(path, "format", "date-time must include a UTC offset")
            if instance[17:19] == "60":
                utc = parsed.astimezone(timezone.utc)
                if (
                    utc.strftime("%Y-%m-%d") not in self._UTC_LEAP_SECOND_DATES
                    or utc.hour != 23
                    or utc.minute != 59
                ):
                    self._fail(path, "format", "second 60 is not a published leap second")

    def _audit_schema(self, schema: Schema, path: str) -> None:
        if isinstance(schema, bool):
            return
        if not isinstance(schema, Mapping):
            raise ValueError(f"unsupported non-object schema at {path}")
        unknown_keywords = set(schema) - self._SUPPORTED_KEYWORDS
        if unknown_keywords:
            raise ValueError(
                "unsupported schema keywords at {}: {}".format(
                    path, ", ".join(sorted(unknown_keywords))
                )
            )
        format_name = schema.get("format")
        if format_name is not None and format_name != "date-time":
            raise ValueError(f"unsupported format at {path}: {format_name!r}")
        for mapping_key in ("$defs", "properties"):
            children = schema.get(mapping_key, {})
            if not isinstance(children, Mapping):
                raise ValueError(f"{mapping_key} must be an object at {path}")
            for name, child in children.items():
                self._audit_schema(child, self._child_path(path, str(name)))
        for schema_key in ("items", "additionalProperties", "if", "then", "else"):
            if schema_key in schema:
                self._audit_schema(schema[schema_key], f"{path}/{schema_key}")
        for sequence_key in ("allOf", "oneOf"):
            if sequence_key in schema:
                for index, child in enumerate(
                    self._schema_sequence(schema, sequence_key, path)
                ):
                    self._audit_schema(child, f"{path}/{sequence_key}/{index}")

    def _validate_number(
        self, instance: Union[int, float], schema: Mapping[str, Any], path: str
    ) -> None:
        self._check_bound(instance, schema, "minimum", "minimum", path)
        self._check_bound(instance, schema, "maximum", "maximum", path)

    def _resolve_reference(self, reference: Any) -> Schema:
        if not isinstance(reference, str) or not reference.startswith("#/"):
            raise ValueError(f"only local JSON-pointer references are supported: {reference!r}")
        current: Any = self._root
        for raw_token in reference[2:].split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, Mapping) or token not in current:
                raise ValueError(f"unresolvable local reference: {reference}")
            current = current[token]
        if not isinstance(current, Mapping) and not isinstance(current, bool):
            raise ValueError(f"referenced value is not a schema: {reference}")
        return current

    def _matches(self, instance: Any, schema: Schema, path: str) -> bool:
        try:
            self._validate(instance, schema, path)
        except ContractValidationError:
            return False
        return True

    @staticmethod
    def _schema_sequence(
        schema: Mapping[str, Any], keyword: str, path: str
    ) -> Sequence[Schema]:
        value = schema.get(keyword, [])
        if not isinstance(value, list):
            raise ValueError(f"{keyword} must be an array at {path}")
        return value

    @staticmethod
    def _check_bound(
        value: Union[int, float],
        schema: Mapping[str, Any],
        keyword: str,
        direction: str,
        path: str,
    ) -> None:
        if keyword not in schema:
            return
        bound = schema[keyword]
        if not _SubsetValidator._is_number(bound):
            raise ValueError(f"{keyword} must be numeric at {path}")
        invalid = value < bound if direction == "minimum" else value > bound
        if invalid:
            relation = "at least" if direction == "minimum" else "at most"
            raise ContractValidationError(
                path, keyword, f"expected {relation} {bound}, got {value}"
            )

    @staticmethod
    def _has_type(instance: Any, expected: Any) -> bool:
        if isinstance(expected, list):
            return any(_SubsetValidator._has_type(instance, item) for item in expected)
        predicates = {
            "object": lambda value: isinstance(value, dict),
            "array": lambda value: isinstance(value, list),
            "string": lambda value: isinstance(value, str),
            "integer": lambda value: isinstance(value, int)
            and not isinstance(value, bool),
            "number": _SubsetValidator._is_number,
            "boolean": lambda value: isinstance(value, bool),
            "null": lambda value: value is None,
        }
        if expected not in predicates:
            raise ValueError(f"unsupported schema type: {expected!r}")
        return predicates[expected](instance)

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def _type_name(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, dict):
            return "object"
        if isinstance(value, list):
            return "array"
        if isinstance(value, str):
            return "string"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        return type(value).__name__

    @staticmethod
    def _json_equal(left: Any, right: Any) -> bool:
        if isinstance(left, bool) or isinstance(right, bool):
            return isinstance(left, bool) and isinstance(right, bool) and left == right
        if _SubsetValidator._is_number(left) and _SubsetValidator._is_number(right):
            return left == right
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(
                _SubsetValidator._json_equal(left[key], right[key]) for key in left
            )
        if isinstance(left, list):
            return len(left) == len(right) and all(
                _SubsetValidator._json_equal(a, b) for a, b in zip(left, right)
            )
        return left == right

    @staticmethod
    def _child_path(path: str, name: str) -> str:
        escaped = name.replace("~", "~0").replace("/", "~1")
        return f"{path}/{escaped}"

    @staticmethod
    def _fail(path: str, keyword: str, message: str) -> None:
        raise ContractValidationError(path, keyword, message)
