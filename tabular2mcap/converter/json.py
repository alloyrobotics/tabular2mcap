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


def register_generic_schema(
    writer: McapWriter,
    df: pd.DataFrame,
    schema_name: str,
    exclude_keys: list[str] | None = None,
) -> tuple[int, list]:
    # Use generic JSON schema with column-based conversion
    columns = [(key, df[key].dtype) for key in df.columns]

    if exclude_keys is not None:
        columns = [(key, dtype) for key, dtype in columns if key not in exclude_keys]

    schema_id = register_json_schema_from_columns(writer, schema_name, columns)
    schema_keys = [key for key, _ in columns]

    return schema_id, schema_keys


def register_schema(
    writer: McapWriter,
    schema_name: str,
) -> int:
    """Register schema and return schema ID and conversion function.

    Args:
        writer: MCAP writer instance
        schema_name: Name of the schema (e.g., "LocationFix" for Foxglove)

    Returns:
        Tuple of (schema_id, convert_row_function)
    """
    if schema_name.startswith("foxglove."):
        schema_id = register_foxglove_schema(
            writer, schema_name.removeprefix("foxglove.")
        )
    else:
        raise ValueError(
            f"Unknown schema: {schema_name}. Must be prefixed with 'foxglove.' or none."
        )

    return schema_id


def write_messages_from_iterator(
    writer: McapWriter,
    iterator: Iterable[tuple[int, dict]],
    topic_name: str,
    schema_id: int | None,
    data_length: int | None = None,
    unit: str = "msg",
) -> None:
    """Write messages from a DataFrame with flexible conversion options.

    This function can handle both Foxglove-specific schemas and generic JSON schemas
    by using different conversion strategies.

    Args:
        writer: MCAP writer instance
        iterator: Iterable of tuples containing the index and message
        topic_name: Full topic name for the messages
        schema_id: Schema ID from register_foxglove_schema
    """
    # Register channel
    channel_id = writer.register_channel(
        topic=topic_name,
        schema_id=schema_id if schema_id is not None else 0,
        message_encoding=MessageEncoding.JSON,
    )

    # Write messages
    for _idx, msg in tqdm(
        iterator,
        desc=f"Writing to {topic_name}",
        total=data_length,
        leave=False,
        unit=unit,
    ):
        # Calculate buf_time_ns from message timestamp
        buf_time_ns = msg["timestamp"]["sec"] * 1_000_000_000 + msg["timestamp"]["nsec"]

        if "data" in msg and isinstance(msg["data"], bytes):
            msg["data"] = base64.b64encode(msg["data"]).decode("utf-8")

        writer.add_message(
            channel_id=channel_id,
            data=json.dumps(msg).encode("utf-8"),
            log_time=buf_time_ns,
            publish_time=buf_time_ns,
        )
