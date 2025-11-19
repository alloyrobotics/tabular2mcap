"""Tests for MCAP file reading and conversion."""

import logging
import shutil
from pathlib import Path

import pytest
from mcap.reader import make_reader

from tabular2mcap import convert_tabular_to_mcap, generate_converter_functions

DATA_PATH = Path(__file__).parent / "data"
TEST_OUTPUT_PATH = Path(__file__).parent / "test_output"
ALL_MCAP_NAMES = [
    "alloy",
    "lerobot",
]
ALL_WRITER_FORMATS = ["json", "ros2"]
logger = logging.getLogger(__name__)


def setup_mcap_conversion(
    mcap_name: str,
    writer_format: str,
    config_name: str = "config.yaml",
    best_effort: bool = False,
):
    input_path = DATA_PATH / mcap_name
    output_path = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Setting up test with MCAP file: {output_path}")
    convert_tabular_to_mcap(
        input_path=input_path,
        output_path=output_path,
        config_path=input_path / writer_format / config_name,
        topic_prefix="",
        converter_functions_path=input_path
        / writer_format
        / "converter_functions.yaml",
        test_mode=False,
        best_effort=best_effort,
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
    setup_mcap_conversion(mcap_name, writer_format, best_effort=True)
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
            if key in [
                "schemas",
                "channels",
                "chunk_indexes",
                "attachment_indexes",
                "metadata_indexes",
            ]:
                assert len(value) == len(ref_summary[key]), f"{key} count mismatch"
            else:
                assert value == ref_summary[key], (
                    f"{key} mismatch: {value} != {ref_summary[key]}"
                )

        # Test topics
        topics = {
            # Normalize path separators to Unix-style (/) for cross-platform compatibility
            (channel.topic.replace("\\", "/"), channel.message_encoding)
            for channel in summary["channels"].values()
        }
        ref_topics = {
            (channel.topic, channel.message_encoding)
            for channel in ref_summary["channels"].values()
        }
        assert topics == ref_topics, "Topics mismatch"

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


@pytest.mark.parametrize("mcap_name", ALL_MCAP_NAMES)
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_generate_converter_functions(mcap_name: str, writer_format: str):
    """Test converter function generation."""
    input_path = DATA_PATH / mcap_name
    output_path = (
        TEST_OUTPUT_PATH
        / writer_format
        / mcap_name
        / "generated_converter_functions.yaml"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_converter_functions(
        input_path=input_path,
        config_path=input_path / writer_format / "config_gen.yaml",
        converter_functions_path=output_path,
    )

    # compare the output with the reference
    ref_output_path = input_path / writer_format / "generated_converter_functions.yaml"
    with open(output_path) as f:
        output_content = f.read()
    with open(ref_output_path) as ref_f:
        ref_content = ref_f.read()
    assert output_content == ref_content, "Converter functions mismatch"


@pytest.mark.parametrize("mcap_name", ["alloy"])
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_not_best_effort_flag(mcap_name: str, writer_format: str):
    """Test that best_effort flag allows conversion to continue despite errors."""
    # Test: Without best_effort flag, should raise ValueError
    with pytest.raises(ValueError, match="Unknown converter function"):
        setup_mcap_conversion(
            mcap_name=mcap_name,
            writer_format=writer_format,
            best_effort=False,
        )
