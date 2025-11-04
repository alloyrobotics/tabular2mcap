"""Common interfaces and base classes for MCAP converters."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, NamedTuple


class ConvertedRow(NamedTuple):
    """Return type for convert_row functions.

    Represents a converted row with its message data and timing information.

    Attributes:
        data: The converted message data as a dictionary
        log_time_ns: Log time in nanoseconds
        publish_time_ns: Publish time in nanoseconds
    """

    data: dict
    log_time_ns: int
    publish_time_ns: int


class ConverterBase(ABC):
    """Base interface for MCAP format converters.

    This abstract base class defines the common interface that all format-specific
    converters (JSON, ROS2, etc.) must implement.
    """

    @property
    @abstractmethod
    def writer(self) -> Any:
        """Get the underlying writer instance.

        Returns:
            The MCAP writer instance for this converter format
        """
        ...

    @abstractmethod
    def register_generic_schema(
        self,
        df: Any,
        schema_name: str,
        exclude_keys: list[str] | None = None,
    ) -> tuple[Any, Any]:
        """Register a generic schema from a DataFrame.

        Args:
            df: DataFrame to generate schema from
            schema_name: Name for the schema
            exclude_keys: Optional list of keys to exclude from schema

        Returns:
            Tuple containing the schema ID/object and schema keys mapping
        """
        ...

    @abstractmethod
    def register_schema(self, schema_name: str) -> Any:
        """Register a predefined schema by name.

        Args:
            schema_name: Name of the schema (format-specific)

        Returns:
            Schema ID or schema object (format-specific)
        """
        ...

    @abstractmethod
    def write_messages_from_iterator(
        self,
        iterator: Iterable[tuple[int, dict]],
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
        ...

    @abstractmethod
    def get_schema_template(self, schema_name: str) -> str:
        """Get the schema template for a given schema name.

        Args:
            schema_name: Name of the schema

        Returns:
            Schema template
        """
        ...


def _to_json_string(obj: Any, indent: int, current_indent: int = 0) -> str:
    """Convert object to JSON string with all values quoted."""
    indent_str = " " * current_indent
    next_indent = current_indent + indent

    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = []
        for key, value in obj.items():
            key_str = f'"{key}"'
            value_str = _to_json_string(value, indent, next_indent)
            items.append(f"{indent_str}  {key_str}: {value_str}")
        return "{\n" + ",\n".join(items) + f"\n{indent_str}}}"
    elif isinstance(obj, list):
        if not obj:
            return "[]"
        items = [_to_json_string(item, indent, next_indent) for item in obj]
        return (
            "[\n"
            + ",\n".join(f"{indent_str}  {item}" for item in items)
            + f"\n{indent_str}]"
        )
    else:
        # Always quote values as strings
        if "| int" in obj or "| float" in obj:
            return f"{obj}"
        else:
            return f'"{obj}"'


def jinja2_json_dump(data: dict, indent: int = 2) -> str:
    """Dump a dictionary to a JSON string with jinja2 template values properly quoted (eg, int or float are not quoted)."""
    return _to_json_string(data, indent)
