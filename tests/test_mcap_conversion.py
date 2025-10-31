"""Tests for MCAP file reading and conversion."""

import logging
import shutil
from pathlib import Path

import pytest
from mcap.reader import make_reader

from tabular2mcap import convert_tabular_to_mcap

DATA_PATH = Path(__file__).parent / "data"
TEST_OUTPUT_PATH = Path(__file__).parent / "test_output"
ALL_MCAP_NAMES = [
    "alloy",
    "lerobot",
]
ALL_WRITER_FORMATS = ["json", "ros2"]
logger = logging.getLogger(__name__)


def setup_mcap_conversion(mcap_name: str, writer_format: str):
    input_path = DATA_PATH / mcap_name
    output_path = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Setting up test with MCAP file: {output_path}")
    convert_tabular_to_mcap(
        input_path=input_path,
        output_path=output_path,
        config_path=input_path / writer_format / "config.yaml",
        topic_prefix="",
        converter_functions_path=input_path
        / writer_format
        / "converter_functions.yaml",
        test_mode=False,
    )


@pytest.fixture(scope="module", autouse=True)
def mcap_files():
    """Fixture that provides the MCAP file path. Runs once per module."""

    if TEST_OUTPUT_PATH.exists():
        shutil.rmtree(TEST_OUTPUT_PATH)
        logger.info(f"Deleted test output directory: {TEST_OUTPUT_PATH}")

    yield

    logger.info("Tearing down test module - cleaning up output files")
    if TEST_OUTPUT_PATH.exists():
        shutil.rmtree(TEST_OUTPUT_PATH)
        logger.info(f"Deleted test output directory: {TEST_OUTPUT_PATH}")


@pytest.mark.parametrize("mcap_name", ALL_MCAP_NAMES)
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_mcap_conversion(mcap_name: str, writer_format: str):
    """Test mcap conversion for all mcap files and writer formats."""
    setup_mcap_conversion(mcap_name, writer_format)
    mcap_file = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    ref_folder = DATA_PATH / f"{mcap_name}"
    ref_mcap_file = ref_folder / writer_format / f"{mcap_name}.mcap"

    with open(mcap_file, "rb") as f, open(ref_mcap_file, "rb") as ref_f:
        reader = make_reader(f)
        ref_reader = make_reader(ref_f)

        # Test summary
        summary = vars(reader.get_summary())  # convert to dict
        ref_summary = vars(ref_reader.get_summary())  # convert to dict
        for key, value in summary.items():
            if key in ["chunk_indexes"]:
                continue
            elif key in ["schemas", "channels", "attachment_indexes"]:
                assert len(value) == len(ref_summary[key]), f"{key} count mismatch"
            else:
                assert value == ref_summary[key], (
                    f"{key} mismatch: {value} != {ref_summary[key]}"
                )

        # Test messages
        messages = list(reader.iter_messages())
        ref_messages = list(ref_reader.iter_messages())
        assert len(messages) == len(ref_messages), "Messages count mismatch"

        # Test attachments
        attachments = list(reader.iter_attachments())
        for attachment in attachments:
            original_file = ref_folder / attachment.name
            assert original_file.exists(), f"Original file not found: {original_file}"
            with open(original_file, "rb") as orig_f:
                assert attachment.data == orig_f.read(), (
                    f"Attachment {attachment.name} data mismatch"
                )

        # Test metadata
        metadata_records = list(reader.iter_metadata())
        for metadata in metadata_records:
            original_file = ref_folder / metadata.name
            assert original_file.exists(), f"Original file not found: {original_file}"
