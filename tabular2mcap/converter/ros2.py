import logging
import re
from collections.abc import Iterable
from typing import Any

import numpy as np
from mcap_ros2._vendor.rosidl_adapter import parser as ros2_parser
from mcap_ros2.writer import Writer as McapRos2Writer
from tqdm import tqdm

from tabular2mcap.schemas.ros2msg import get_schema_definition

from .common import ConvertedRow, ConverterBase, jinja2_json_dump

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


def sanitize_ros2_field_name(key: str) -> str:
    """Convert string to valid ROS2 field name by removing invalid characters."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", key).lower()


def ros2_msg_to_template(msg_def_text: str, msg_type: str) -> dict:
    """Convert ROS2 message definition directly to template dict."""

    match = re.match(r"^([^/]+)/(?:msg/)?([^/]+)$", msg_type)
    if not match:
        raise ValueError(f"Invalid message type format: {msg_type}")
    pkg_name, msg_name = match.groups()

    # Parse all message definitions (main + dependencies)
    msg_defs = {}
    sections = msg_def_text.split("=" * 80)

    # First section is main message
    msg_defs[msg_type] = ros2_parser.parse_message_string(
        pkg_name, msg_name, sections[0].strip()
    )
    # Parse dependency sections
    for section in sections[1:]:
        if not (lines := section.strip().split("\n", 1)) or len(lines) < 2:
            continue
        if match := re.match(r"MSG: ([^/]+)/(?:msg/)?([^/]+)", lines[0]):
            dep_pkg, dep_name = match.groups()
            msg_defs[f"{dep_pkg}/{dep_name}"] = ros2_parser.parse_message_string(
                dep_pkg, dep_name, lines[1].strip()
            )

    def to_template_value(field, col_name: str = "") -> Any:
        field_type_str = str(field.type)
        if field.type.is_primitive_type():
            if "int" in field_type_str:
                filter_str = " | int"
            elif "float" in field_type_str:
                filter_str = " | float"
            else:
                filter_str = ""
            if field.type.is_array:
                count = field.type.array_size or 1
                return [
                    f"{{{{ <{col_name}_{idx}_column>{filter_str} }}}}"
                    for idx in range(count)
                ]
            else:
                return f"{{{{ <{col_name}_column>{filter_str} }}}}"
        else:
            field_type_str = str(field.type)
            if field_type_str in (
                "builtin_interfaces/Time",
                "builtin_interfaces/Duration",
            ):
                template = {
                    "sec": "{{ <sec_column> | int }}",
                    "nanosec": "{{ <nanosec_column> | int }}",
                }
            elif field_type_str in msg_defs:
                nested_def = msg_defs[field_type_str]
                template = {
                    f.name: to_template_value(f, f.name) for f in nested_def.fields
                }
                if nested_def.constants:
                    template["_constants"] = ", ".join(
                        [f"{c.name}={c.value}" for c in nested_def.constants]
                    )
            else:
                template = f"{{{{ <{col_name}_column> }}}}"

            if field.type.is_array:
                count = field.type.array_size or 1
                return [template] * count
            else:
                return template

    template = {f.name: to_template_value(f, f.name) for f in msg_defs[msg_type].fields}
    if msg_defs[msg_type].constants:
        template["_constants"] = ", ".join(
            [f"{c.name}={c.value}" for c in msg_defs[msg_type].constants]
        )
    return template


class Ros2Converter(ConverterBase):
    """ROS2 format converter that wraps ROS2-specific MCAP writer operations."""

    _writer: McapRos2Writer | None

    def __init__(self, writer: McapRos2Writer | None = None):
        """Initialize the ROS2 converter with a writer instance.

        Args:
            writer: MCAP ROS2 writer instance
        """
        self._writer = writer

    @property
    def writer(self) -> Any:
        """Get the underlying writer instance (accesses _writer attribute for ROS2)."""
        return self._writer._writer

    @staticmethod
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

    def register_generic_schema(
        self,
        df: Any,
        schema_name: str,
        exclude_keys: list[str] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        """Register a generic ROS2 schema from a DataFrame.

        Args:
            df: DataFrame to generate schema from
            schema_name: Name for the schema
            exclude_keys: Optional list of keys to exclude from schema

        Returns:
            Tuple of (schema, schema_keys)
        """
        type_var_name_pairs = []
        schema_keys = {}

        for key in df.columns:
            if exclude_keys and key in exclude_keys:
                continue
            if key == "timestamp":
                type_var_name_pairs.append(("builtin_interfaces/Time", key))
                continue

            dtype = df[key].dtype
            # Get sample data for object columns, handle case where no non-null values exist
            sample_data = None
            if dtype.kind == "O":
                non_null_values = df[key].dropna()
                if len(non_null_values) > 0:
                    sample_data = non_null_values.iloc[0]

            ros2_key = sanitize_ros2_field_name(key)
            type_var_name_pairs.append(
                (numpy_to_ros2_type(dtype, sample_data), ros2_key)
            )
            schema_keys[ros2_key] = key

        custom_msg_txt = "\n".join([f"{t} {v}" for t, v in type_var_name_pairs])
        schema_text = get_schema_definition(
            schema_name, "jazzy", custom_msg_txt=custom_msg_txt
        )
        schema = self._writer.register_msgdef(schema_name, schema_text)

        return schema, schema_keys

    def register_schema(self, schema_name: str) -> Any:
        """Register a predefined ROS2 schema by name.

        Args:
            schema_name: Name of the ROS2 message schema

        Returns:
            Schema object
        """
        schema_text = get_schema_definition(schema_name, "jazzy")
        schema = self._writer.register_msgdef(schema_name, schema_text)
        return schema

    def get_schema_template(self, schema_name: str) -> str:
        """Get the schema template for a given ROS2 schema name.

        Args:
            schema_name: Name of the ROS2 schema (e.g., 'sensor_msgs/msg/NavSatFix')

        Returns:
            Schema template
        """
        schema_text = get_schema_definition(schema_name, "jazzy")
        template = ros2_msg_to_template(schema_text, schema_name)
        return jinja2_json_dump(template)

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
        # Write messages
        for idx, converted_row in tqdm(
            iterator,
            desc=f"Writing to {topic_name}",
            total=data_length,
            leave=False,
            unit=unit,
        ):
            msg = converted_row.data
            self._writer.write_message(
                topic=topic_name,
                schema=schema_id,
                message=msg,
                log_time=converted_row.log_time_ns,
                publish_time=converted_row.publish_time_ns,
                sequence=idx,
            )
