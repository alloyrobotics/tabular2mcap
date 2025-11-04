"""JSON converter utilities for MCAP writing."""

import base64
import json
import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd
from mcap.well_known import MessageEncoding, SchemaEncoding
from mcap.writer import Writer as McapWriter
from tqdm import tqdm

from tabular2mcap.schemas import get_foxglove_jsonschema

from .common import ConvertedRow, ConverterBase, jinja2_json_dump

logger = logging.getLogger(__name__)


def register_json_schema_from_columns(
    writer: McapWriter, schema_name: str, columns: list[tuple[str, Any]]
) -> int:
    """Create and register a JSON schema from column names and their dtypes.

    Args:
        writer: MCAP writer instance
        schema_name: Name of the schema (e.g., "LocationFix")
        columns: List of (key, dtype) tuples for schema generation

    Returns:
        Schema ID that was registered
    """
    # Create JSON schema from the list of columns
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "timestamp": {  # always include timestamp
                "type": "object",
                "title": "time",
                "properties": {
                    "sec": {"type": "integer", "minimum": 0},
                    "nsec": {"type": "integer", "minimum": 0, "maximum": 999999999},
                },
                "description": "Timestamp of the message",
            },
        },
    }

    # Add properties for each key with appropriate type inference
    properties: dict[str, Any] = schema["properties"]
    for key, dtype in columns:
        if pd.api.types.is_integer_dtype(dtype):
            properties[key] = {"type": "integer"}
        elif pd.api.types.is_float_dtype(dtype):
            properties[key] = {"type": "number"}
        elif pd.api.types.is_bool_dtype(dtype):
            properties[key] = {"type": "boolean"}
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            properties[key] = {"type": "string"}  # Will be converted to ISO format
        elif isinstance(dtype, pd.CategoricalDtype):
            properties[key] = {"type": "string"}
        else:
            # Default to string for object/string types
            properties[key] = {"type": "string"}

    # Register the schema
    schema_id = writer.register_schema(
        name=schema_name,
        encoding="jsonschema",
        data=json.dumps(schema).encode(),
    )

    return schema_id


def register_foxglove_schema(writer: McapWriter, schema_name: str) -> int:
    """Register a Foxglove schema with the MCAP writer.

    Args:
        writer: MCAP writer instance
        schema_name: Name of the Foxglove schema (e.g., "LocationFix")

    Returns:
        Schema ID for use in channel registration
    """
    # Get schema data
    schema_data = get_foxglove_jsonschema(schema_name)

    # Register schema
    schema_id = writer.register_schema(
        name=f"foxglove.{schema_name}",
        encoding=SchemaEncoding.JSONSchema,
        data=schema_data,
    )

    return schema_id


def to_template_value(prop_def: dict, col_name: str = "") -> Any:
    prop_type = prop_def.get("type", "unknown")

    if prop_type == "object" and "properties" in prop_def:
        return {n: to_template_value(d, n) for n, d in prop_def["properties"].items()}
    elif prop_type == "array":
        items = prop_def.get("items", {})
        count = prop_def.get("minItems", 1)
        item_type = items.get("type")
        if item_type == "object" and "properties" in items:
            return [
                {
                    n: to_template_value(d, f"{n}_{idx}")
                    for n, d in items["properties"].items()
                }
                for idx in range(count)
            ]
        else:
            if item_type == "integer":
                filter_str = " | int"
            elif item_type == "number":
                filter_str = " | float"
            else:
                filter_str = ""
            return [
                f"{{{{ <{f'{col_name}_{idx}_column'}>{filter_str} }}}}"
                for idx in range(count)
            ]
    else:
        comment_str = ""
        filter_str = ""
        if "oneOf" in prop_def:
            options = prop_def["oneOf"]
            comment_str = " # one of " + " or ".join(
                [f"{option['const']} ({option['title']})" for option in options]
            )
            filter_str = " | int"
        elif prop_type == "integer":
            filter_str = " | int"
        elif prop_type == "number":
            filter_str = " | float"
        return f"{{{{ <{col_name}_column>{filter_str} }}}}{comment_str}"


def json_schema_to_template(schema_json_str: str | bytes) -> dict:
    """Convert schema JSON to template dict with only properties."""
    json_data = json.loads(
        schema_json_str.decode("utf-8")
        if isinstance(schema_json_str, bytes)
        else schema_json_str
    )
    if "properties" not in json_data:
        return {}

    result = {}
    for prop_name, prop_def in json_data["properties"].items():
        result[prop_name] = to_template_value(prop_def, prop_name)
    return result


class JsonConverter(ConverterBase):
    """JSON format converter that wraps JSON-specific MCAP writer operations."""

    _writer: McapWriter | None

    def __init__(self, writer: McapWriter | None = None):
        """Initialize the JSON converter with a writer instance.

        Args:
            writer: MCAP writer instance for JSON format
        """
        self._writer = writer

    @property
    def writer(self) -> McapWriter:
        """Get the underlying writer instance."""
        return self._writer

    def register_generic_schema(
        self,
        df: Any,
        schema_name: str,
        exclude_keys: list[str] | None = None,
    ) -> tuple[int, list]:
        """Register a generic JSON schema from a DataFrame.

        Args:
            df: DataFrame to generate schema from
            schema_name: Name for the schema
            exclude_keys: Optional list of keys to exclude from schema

        Returns:
            Tuple of (schema_id, schema_keys)
        """
        # Use generic JSON schema with column-based conversion
        columns = [(key, df[key].dtype) for key in df.columns]

        if exclude_keys is not None:
            columns = [
                (key, dtype) for key, dtype in columns if key not in exclude_keys
            ]

        # Create JSON schema from the list of columns
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
        }

        # Add properties for each key with appropriate type inference
        properties: dict[str, Any] = schema["properties"]
        for key, dtype in columns:
            if key == "timestamp":
                properties[key] = {
                    "type": "object",
                    "properties": {
                        "sec": {"type": "integer", "minimum": 0},
                        "nsec": {"type": "integer", "minimum": 0, "maximum": 999999999},
                    },
                }
            elif pd.api.types.is_integer_dtype(dtype):
                properties[key] = {"type": "integer"}
            elif pd.api.types.is_float_dtype(dtype):
                properties[key] = {"type": "number"}
            elif pd.api.types.is_bool_dtype(dtype):
                properties[key] = {"type": "boolean"}
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                properties[key] = {"type": "string"}  # Will be converted to ISO format
            elif isinstance(dtype, pd.CategoricalDtype):
                properties[key] = {"type": "string"}
            else:
                # Default to string for object/string types
                properties[key] = {"type": "string"}

        # Register the schema
        schema_id = self._writer.register_schema(
            name=schema_name,
            encoding="jsonschema",
            data=json.dumps(schema).encode(),
        )

        schema_keys = [key for key, _ in columns]
        return schema_id, schema_keys

    def register_schema(self, schema_name: str) -> int:
        """Register a predefined schema by name.

        Args:
            schema_name: Name of the schema (e.g., "foxglove.LocationFix")

        Returns:
            Schema ID
        """
        if schema_name.startswith("foxglove."):
            # Get schema data
            schema_data = get_foxglove_jsonschema(schema_name.removeprefix("foxglove."))

            # Register schema
            schema_id = self._writer.register_schema(
                name=f"foxglove.{schema_name.removeprefix('foxglove.')}",
                encoding=SchemaEncoding.JSONSchema,
                data=schema_data,
            )
        else:
            raise ValueError(
                f"Unknown schema: {schema_name}. Must be prefixed with 'foxglove.' or none."
            )

        return schema_id

    def write_messages_from_iterator(
        self,
        iterator: Iterable[tuple[int, ConvertedRow]],
        topic_name: str,
        schema_id: int | None,
        data_length: int | None = None,
        unit: str = "msg",
    ) -> None:
        """Write messages to MCAP from an iterator.

        Args:
            iterator: Iterator yielding (index, message) tuples
            topic_name: Topic name for the messages
            schema_id: Schema ID for the messages
            data_length: Optional total length for progress tracking
            unit: Unit label for progress tracking
        """
        # Register channel
        channel_id = self._writer.register_channel(
            topic=topic_name,
            schema_id=schema_id if schema_id is not None else 0,
            message_encoding=MessageEncoding.JSON,
        )

        # Write messages
        for _idx, converted_row in tqdm(
            iterator,
            desc=f"Writing to {topic_name}",
            total=data_length,
            leave=False,
            unit=unit,
        ):
            msg = converted_row.data
            if "data" in msg and isinstance(msg["data"], bytes):
                msg["data"] = base64.b64encode(msg["data"]).decode("utf-8")

            self._writer.add_message(
                channel_id=channel_id,
                data=json.dumps(msg).encode("utf-8"),
                log_time=converted_row.log_time_ns,
                publish_time=converted_row.publish_time_ns,
            )

    def get_schema_template(self, schema_name: str) -> str:
        """Get the schema template for a given schema name.

        Args:
            schema_name: Name of the schema

        Returns:
            Schema template
        """
        if schema_name.startswith("foxglove."):
            # Get schema data
            schema_data = get_foxglove_jsonschema(schema_name.removeprefix("foxglove."))
            data = json_schema_to_template(schema_data)
            return jinja2_json_dump(data)
        else:
            raise ValueError(
                f"Unknown schema: {schema_name}. Must be prefixed with 'foxglove.' or none."
            )
