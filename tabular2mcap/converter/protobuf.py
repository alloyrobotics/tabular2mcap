"""Protobuf converter utilities for MCAP writing."""

import importlib
import logging
import re
from collections.abc import Iterable
from typing import Any

import numpy as np
from google.protobuf import descriptor_pb2 as pb2
from google.protobuf import descriptor_pool, message_factory
from google.protobuf.descriptor import FieldDescriptor as FD
from mcap_protobuf.writer import Writer as McapProtobufWriter
from tqdm import tqdm

from .common import ConvertedRow, ConverterBase, jinja2_json_dump

logger = logging.getLogger(__name__)

# Type sets for template generation
_FLOAT_TYPES = {FD.TYPE_DOUBLE, FD.TYPE_FLOAT}
_INT_TYPES = {
    FD.TYPE_INT32,
    FD.TYPE_INT64,
    FD.TYPE_UINT32,
    FD.TYPE_UINT64,
    FD.TYPE_SINT32,
    FD.TYPE_SINT64,
    FD.TYPE_FIXED32,
    FD.TYPE_FIXED64,
    FD.TYPE_SFIXED32,
    FD.TYPE_SFIXED64,
    FD.TYPE_ENUM,
}


def _sanitize_field_name(name: str) -> str:
    """Sanitize a field name to be a valid protobuf identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()


def _numpy_to_proto_type(dtype: np.dtype, sample_value=None) -> tuple[int, bool]:
    """Map numpy dtype to protobuf field type.

    Returns:
        Tuple of (proto_type, is_repeated)
    """
    kind, size = dtype.kind, dtype.itemsize
    t = pb2.FieldDescriptorProto

    # Handle object dtype (could be list/array)
    if kind == "O" and sample_value is not None:
        if isinstance(sample_value, (list, np.ndarray)):
            # It's a repeated field - determine element type
            if len(sample_value) > 0:
                elem = sample_value[0]
                if isinstance(elem, (int, np.integer)):
                    return t.TYPE_INT64, True
                elif isinstance(elem, (float, np.floating)):
                    return t.TYPE_DOUBLE, True
                elif isinstance(elem, bool):
                    return t.TYPE_BOOL, True
            return t.TYPE_DOUBLE, True  # Default to double for numeric arrays
        elif isinstance(sample_value, str):
            return t.TYPE_STRING, False
        return t.TYPE_STRING, False

    if kind == "b":
        return t.TYPE_BOOL, False
    if kind == "i":
        return t.TYPE_INT64 if size > 4 else t.TYPE_INT32, False
    if kind == "u":
        return t.TYPE_UINT64 if size > 4 else t.TYPE_UINT32, False
    if kind == "f":
        return t.TYPE_DOUBLE if size > 4 else t.TYPE_FLOAT, False
    return t.TYPE_STRING, False


def _create_dynamic_proto_class(
    schema_name: str, columns: list[tuple[str, np.dtype, Any]]
) -> type:
    """Create a dynamic protobuf message class from column definitions.

    Args:
        schema_name: Full schema name (e.g., 'table.path.Data')
        columns: List of (column_name, dtype, sample_value) tuples
    """
    parts = schema_name.rsplit(".", 1)
    pkg_name, msg_name = (
        (parts[0], parts[-1]) if len(parts) > 1 else ("dynamic", parts[0])
    )

    # Build file descriptor
    file_proto = pb2.FileDescriptorProto()
    file_proto.name = f"{pkg_name.replace('.', '/')}/{msg_name}.proto"
    file_proto.package = pkg_name

    msg_proto = file_proto.message_type.add()
    msg_proto.name = msg_name

    for i, (col_name, dtype, sample_value) in enumerate(columns, start=1):
        field = msg_proto.field.add()
        field.name = _sanitize_field_name(col_name)
        field.number = i
        proto_type, is_repeated = _numpy_to_proto_type(dtype, sample_value)
        field.type = proto_type
        if is_repeated:
            field.label = pb2.FieldDescriptorProto.LABEL_REPEATED
        else:
            field.label = pb2.FieldDescriptorProto.LABEL_OPTIONAL

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)
    return message_factory.GetMessageClass(
        pool.FindMessageTypeByName(f"{pkg_name}.{msg_name}")
    )


def _get_foxglove_proto_class(schema_name: str) -> type:
    """Import and return a foxglove protobuf class (e.g., 'foxglove.Vector3')."""
    if not schema_name.startswith("foxglove."):
        raise ValueError(f"Unknown schema: {schema_name}. Must start with 'foxglove.'")
    msg_name = schema_name.removeprefix("foxglove.")
    module = importlib.import_module(f"foxglove_schemas_protobuf.{msg_name}_pb2")
    return getattr(module, msg_name)


def _field_to_template(field: FD, col_name: str) -> Any:
    """Convert a protobuf field descriptor to a Jinja2 template value."""
    if field.type == FD.TYPE_MESSAGE:
        nested = {
            f.name: _field_to_template(f, f.name) for f in field.message_type.fields
        }
        return [nested] if field.is_repeated else nested

    filt = (
        " | float"
        if field.type in _FLOAT_TYPES
        else " | int"
        if field.type in _INT_TYPES
        else ""
    )

    # Note: Protobuf repeated fields are variable length (no fixed size arrays).
    # Template shows single placeholder; actual data must be populated dynamically.
    if field.is_repeated:
        logger.warning(
            f"Field '{col_name}' is repeated (variable length array). "
            "Template shows single placeholder; populate with actual data."
        )
        return [f"{{{{ <{col_name}_0_column>{filt} }}}}"]
    return f"{{{{ <{col_name}_column>{filt} }}}}"


def _proto_to_template(proto_class: Any) -> dict:
    """Convert a protobuf class to a template dict."""
    return {
        f.name: _field_to_template(f, f.name) for f in proto_class.DESCRIPTOR.fields
    }


class ProtobufConverter(ConverterBase):
    """Protobuf format converter that wraps Protobuf-specific MCAP writer operations."""

    _writer: McapProtobufWriter | None
    _schemas: dict[int, Any]  # schema_id -> protobuf class
    _schema_names: dict[str, int]  # schema_name -> schema_id

    def __init__(self, writer: McapProtobufWriter | None = None):
        """Initialize the Protobuf converter with a writer instance."""
        self._writer = writer
        self._schemas = {}
        self._schema_names = {}

    @property
    def writer(self) -> Any:
        """Get the underlying writer instance."""
        return self._writer._writer  # type: ignore[union-attr]

    def register_generic_schema(
        self, df: Any, schema_name: str, exclude_keys: list[str] | None = None
    ) -> tuple[int, dict[str, str]]:
        """Register a dynamic Protobuf schema from DataFrame columns."""
        exclude = set(exclude_keys or []) | {"timestamp"}
        # Include sample value for each column to detect array types
        columns = [
            (col, df[col].dtype, df[col].iloc[0] if len(df) > 0 else None)
            for col in df.columns
            if col not in exclude
        ]

        schema_id = len(self._schemas) + 1
        self._schemas[schema_id] = _create_dynamic_proto_class(schema_name, columns)
        self._schema_names[schema_name] = schema_id

        # Return mapping: sanitized_field_name -> original_column_name
        schema_keys = {_sanitize_field_name(col): col for col, _, _ in columns}
        return schema_id, schema_keys

    def register_schema(self, schema_name: str) -> int:
        """Register a predefined Protobuf schema by name (e.g., 'foxglove.Vector3')."""
        if schema_name in self._schema_names:
            logger.warning(f"Schema '{schema_name}' already registered")
            return self._schema_names[schema_name]

        schema_id = len(self._schemas) + 1
        self._schemas[schema_id] = _get_foxglove_proto_class(schema_name)
        self._schema_names[schema_name] = schema_id
        return schema_id

    def get_schema_template(self, schema_name: str) -> str:
        """Get the schema template for a given Protobuf schema name (e.g., 'foxglove.Vector3')."""
        return jinja2_json_dump(
            _proto_to_template(_get_foxglove_proto_class(schema_name))
        )

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
            iterator: Iterator yielding (index, ConvertedRow) tuples.
                      ConvertedRow.data is a dict converted to protobuf message.
            topic_name: Topic name for the messages
            schema_id: Schema ID from register_schema (required)
            data_length: Optional total length for progress tracking
            unit: Unit label for progress tracking
        """
        if schema_id is None or schema_id not in self._schemas:
            raise ValueError(
                f"Invalid schema_id: {schema_id}. Must register schema first."
            )
        proto_class = self._schemas[schema_id]
        for _idx, converted_row in tqdm(
            iterator,
            desc=f"Writing to {topic_name}",
            total=data_length,
            leave=False,
            unit=unit,
        ):
            self._writer.write_message(  # type: ignore[union-attr]
                topic=topic_name,
                message=proto_class(**converted_row.data),
                log_time=converted_row.log_time_ns,
                publish_time=converted_row.publish_time_ns,
            )
