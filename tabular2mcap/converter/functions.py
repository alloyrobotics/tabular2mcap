import json
import logging
from collections.abc import Callable

import numpy as np
import pandas as pd
from jinja2 import Environment, StrictUndefined, Template
from pydantic import BaseModel, Field, PrivateAttr
from scipy.spatial.transform import Rotation as R

from tabular2mcap.converter.common import ConvertedRow
from tabular2mcap.loader.models import ConverterFunctionDefinition

logger = logging.getLogger(__name__)


class ConverterFunctionJinja2Environment(Environment):
    """
    Specialized Jinja2 environment for ConverterFunction that provides math functions,
    custom filters, and disables autoescape for JSON-like output.
    """

    def __init__(self):
        # Ensure autoescape is False and StrictUndefined is used
        super().__init__(autoescape=False, undefined=StrictUndefined)

        # Add math functions to global namespace
        self.globals.update(
            {
                "pi": np.pi,
                "cos": np.cos,
                "sin": np.sin,
                "tan": np.tan,
                "sqrt": np.sqrt,
                "log": np.log,
                "exp": np.exp,
                "abs": abs,
                "min": min,
                "max": max,
                # Custom functions
                "euler_to_quaternion": self._euler_to_quaternion,
                "latlon_to_utm": self._latlon_to_utm,
            }
        )

    def _euler_to_quaternion(self, euler_angles, seq="xyz"):
        """Convert Euler angles (roll, pitch, yaw) in degrees to quaternion.

        Args:
            euler_angles: List or tuple of 3 angles in degrees
            seq: Sequence of rotations, default "xyz" (roll, pitch, yaw)
        """
        quat_dict = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        try:
            if isinstance(euler_angles, (list, tuple)) and len(euler_angles) == 3:
                roll, pitch, yaw = euler_angles
                r = R.from_euler(
                    seq, [np.radians(roll), np.radians(pitch), np.radians(yaw)]
                )
                quat = r.as_quat()  # [x, y, z, w]
                quat_dict = {
                    "x": float(quat[0]),
                    "y": float(quat[1]),
                    "z": float(quat[2]),
                    "w": float(quat[3]),
                }
            else:
                logger.warning(f"Invalid euler_angles format: {euler_angles}")
        except Exception as e:
            logger.error(f"Error converting euler angles to quaternion: {e}")

        return json.dumps(quat_dict)

    def _latlon_to_utm(self, lat, lon, height=0):
        """Convert latitude/longitude to UTM coordinates."""
        # Simple approximation for small areas
        x = lon * 111320 * np.cos(np.radians(lat))
        y = lat * 111320
        utm_dict = {"x": float(x), "y": float(y), "z": float(height)}
        return json.dumps(utm_dict)


class ConverterFunction(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    definition: ConverterFunctionDefinition = Field(
        description="The definition of the converter function."
    )
    jinja2_env: Environment | None = Field(
        description="Optional Jinja2 environment to use. If not provided, a new one will be created.",
        default=None,
    )
    _jinja2_template: Template = PrivateAttr(default=None)
    _log_time_template: Template | None = PrivateAttr(default=None)
    _publish_time_template: Template | None = PrivateAttr(default=None)

    def init_jinja2_template(self):
        """Initialize Jinja2 template and environment after model creation."""
        # Use provided environment or create a new one
        if self.jinja2_env is None:
            logger.warning("No Jinja2 environment provided, creating a new one")
            self.jinja2_env = ConverterFunctionJinja2Environment()

        # Create template from string
        self._jinja2_template = self.jinja2_env.from_string(self.definition.template)
        if self.definition.log_time_template is not None:
            self._log_time_template = self.jinja2_env.from_string(
                self.definition.log_time_template
            )
        if self.definition.publish_time_template is not None:
            self._publish_time_template = self.jinja2_env.from_string(
                self.definition.publish_time_template
            )
        return self

    def convert_row(self, row: pd.Series) -> ConvertedRow:
        """Convert a pandas row using the Jinja2 template."""
        try:
            # Replace NaN values with None while still a Series
            row = row.where(pd.notna(row), None)

            # Convert pandas Series to dict for Jinja2
            context = row.to_dict()

            # Render template
            result = self._jinja2_template.render(**context)

            # Parse JSON result
            message_data = json.loads(result)

            # Calculate log_time_ns
            if self._log_time_template is not None:
                log_time_ns = int(self._log_time_template.render(**context))
            elif "timestamp" in message_data:
                log_time_ns = (
                    message_data["timestamp"]["sec"] * 1_000_000_000
                    + message_data["timestamp"]["nsec"]
                )
            elif "header" in message_data and "stamp" in message_data["header"]:
                stamp = message_data["header"]["stamp"]
                log_time_ns = stamp["sec"] * 1_000_000_000 + stamp.get(
                    "nsec", stamp.get("nanosec", 0)
                )
            else:
                raise ValueError(
                    "No log_time_template provided and no timestamp found in message"
                )

            # Calculate publish_time_ns
            if self._publish_time_template is not None:
                publish_time_ns = int(self._publish_time_template.render(**context))
            else:
                publish_time_ns = log_time_ns

            return ConvertedRow(
                data=message_data,
                log_time_ns=log_time_ns,
                publish_time_ns=publish_time_ns,
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in template result: {e}")
            logger.error(f"Template result: {result}")
            raise
        except Exception as e:
            logger.error(f"Error converting row with template: {e}")
            logger.error(f"Row data: {row.to_dict()}")
            raise


def generate_generic_converter_func(
    schema_keys: list[str] | dict[str, str],
    converter_func: Callable | None = None,
) -> Callable:
    def convert_row(row: pd.Series) -> ConvertedRow:
        result = (
            converter_func(row)
            if converter_func
            else ConvertedRow(data={}, log_time_ns=0, publish_time_ns=0)
        )
        if isinstance(schema_keys, dict):
            # ros2key, original_key
            msg_row_key_pairs = schema_keys.items()
        else:
            # original_key, original_key
            msg_row_key_pairs = [(key, key) for key in schema_keys]

        for msg_key, row_key in msg_row_key_pairs:
            value = row[row_key]
            # Convert pandas/numpy types to Python native types
            if hasattr(value, "tolist"):
                value = value.tolist()
            elif hasattr(value, "item"):  # numpy scalar
                value = value.item()
            elif hasattr(value, "to_pydatetime"):  # pandas timestamp
                value = value.to_pydatetime().isoformat()  # type: ignore

            # Handle different value types for null checking
            if isinstance(value, list) or pd.notna(value):
                result.data[msg_key] = value
            else:
                result.data[msg_key] = None
        return result

    return convert_row
