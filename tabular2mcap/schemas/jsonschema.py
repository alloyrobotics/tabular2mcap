"""Foxglove schema utilities for accessing message definitions."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_foxglove_jsonschema(schema_name: str) -> bytes:
    """Get a Foxglove schema by name.

    Args:
        schema_name: Name of the schema (e.g., 'LocationFix', 'Pose')

    Returns:
        Bytes containing the schema definition
    """
    base_dir = (
        Path(__file__).parent.parent
        / "external"
        / "foxglove-sdk"
        / "schemas"
        / "jsonschema"
    )
    schema_path = base_dir / f"{schema_name}.json"
    if schema_path.exists():
        try:
            with open(schema_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading schema {schema_name}: {e}")
            return b""
    else:
        logger.error(f"Schema file {schema_path} does not exist.")
        return b""
