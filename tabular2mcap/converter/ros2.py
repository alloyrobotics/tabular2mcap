import logging
import re
from collections.abc import Iterable

import numpy as np
import pandas as pd
from mcap.records import Schema
from mcap_ros2.writer import Writer as McapRos2Writer
from tqdm import tqdm

from tabular2mcap.schemas.ros2msg import get_schema_definition

logger = logging.getLogger(__name__)


def numpy_to_ros2_type(dtype: np.dtype, sample_data=None) -> str:
    """Convert numpy dtype to ROS2 type."""
    kind = dtype.kind
    itemsize = dtype.itemsize

    if kind == "b":  # boolean
        return "bool"
    elif kind == "i":  # signed integer
        return f"int{itemsize * 8}"
    elif kind == "u":  # unsigned integer
        return f"uint{itemsize * 8}"
    elif kind == "f":  # floating point
        return f"float{itemsize * 8}"
    elif kind == "O":  # object (check if it's a list)
        if sample_data is None:
            return "string[]"
        elif isinstance(sample_data, str):
            return "string"
        else:
            return f"{numpy_to_ros2_type(sample_data.dtype)}[]"
    else:
        return "string"


def sanitize_schema_name(schema_name: str) -> str:
    """Convert string to valid ROS2 schema name by removing invalid characters."""
    schema_parts = schema_name.split("/")
    package_name = "/".join(schema_parts[:-1])
    msg_name = schema_parts[-1]

    package_name = re.sub(r"[^a-zA-Z0-9]", "_", package_name).lower()
    # Convert to PascalCase: remove invalid chars, split by underscores, capitalize each part
    msg_name = re.sub(r"[^a-zA-Z0-9_]", "_", msg_name)
    msg_parts = [part.capitalize() for part in msg_name.split("_") if part]
    msg_name = "".join(msg_parts)

    return f"{package_name}/{msg_name}"


def sanitize_ros2_field_name(key: str) -> str:
    """Convert string to valid ROS2 field name by removing invalid characters."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", key).lower()


def register_generic_schema(
    writer: McapRos2Writer,
    df: pd.DataFrame,
    schema_name: str,
    exclude_keys: list[str] | None = None,
) -> tuple[int, dict[str, str]]:
    type_var_name_pairs = [("builtin_interfaces/Time", "timestamp")]
    schema_keys = {}

    for key in df.columns:
        if key in exclude_keys:
            continue
        dtype = df[key].dtype
        # Get sample data for object columns, handle case where no non-null values exist
        sample_data = None
        if dtype.kind == "O":
            non_null_values = df[key].dropna()
            if len(non_null_values) > 0:
                sample_data = non_null_values.iloc[0]

        ros2_key = sanitize_ros2_field_name(key)
        type_var_name_pairs.append((numpy_to_ros2_type(dtype, sample_data), ros2_key))
        schema_keys[ros2_key] = key

    custom_msg_txt = "\n".join([f"{t} {v}" for t, v in type_var_name_pairs])
    schema_text = get_schema_definition(
        schema_name, "jazzy", custom_msg_txt=custom_msg_txt
    )
    schema = writer.register_msgdef(schema_name, schema_text)

    return schema, schema_keys


def register_schema(
    writer: McapRos2Writer,
    schema_name: str,
) -> Schema:
    """Register schema and return schema ID and conversion function.

    Args:
        writer: MCAP writer instance
        schema_name: Name of the schema (e.g., "LocationFix" for Foxglove)

    Returns:
        Tuple of (schema_id, convert_row_function)
    """
    schema_text = get_schema_definition(schema_name, "jazzy")
    schema = writer.register_msgdef(schema_name, schema_text)
    return schema


def write_messages_from_iterator(
    writer: McapRos2Writer,
    iterator: Iterable[tuple[int, dict]],
    topic_name: str,
    schema_id: int | None,
    data_length: int | None = None,
    unit: str = "msg",
) -> None:
    """Write messages from an iterator."""

    # Write messages
    for idx, msg in tqdm(
        iterator,
        desc=f"Writing to {topic_name}",
        total=data_length,
        leave=False,
        unit=unit,
    ):
        # Calculate buf_time_ns from message timestamp
        if "timestamp" in msg:
            buf_time_ns = (
                msg["timestamp"]["sec"] * 1_000_000_000 + msg["timestamp"]["nsec"]
            )
        elif "header" in msg and "stamp" in msg["header"]:
            buf_time_ns = (
                msg["header"]["stamp"]["sec"] * 1_000_000_000
                + msg["header"]["stamp"]["nanosec"]
            )
        else:
            raise ValueError("No timestamp found in message")
        writer.write_message(
            topic=topic_name,
            schema=schema_id,
            message=msg,
            log_time=buf_time_ns,
            publish_time=buf_time_ns,
            sequence=idx,
        )
