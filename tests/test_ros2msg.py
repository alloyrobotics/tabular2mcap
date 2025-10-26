#!/usr/bin/env python3
"""Test script for the GPL-free ROS2 schema implementation."""

import logging

import pytest

from tabular2mcap.schemas.ros2msg import get_schema_definition

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "msg_type",
    [
        "geometry_msgs/TransformStamped",
        "foxglove_msgs/LocationFix",
        "tf2_msgs/TFMessage",
    ],
)
def test_message_definition(msg_type: str):
    """Test the message definition retrieval."""
    logger.info("\nTesting message definition retrieval...")

    # This will try to download and parse a real ROS2 message
    result = get_schema_definition(msg_type, "jazzy")

    # Test that we got a valid definition
    assert result is not None, "Message definition should not be None"
