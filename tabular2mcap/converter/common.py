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
