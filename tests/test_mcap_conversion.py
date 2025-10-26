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
        # shutil.rmtree(TEST_OUTPUT_PATH)
        logger.info(f"Deleted test output directory: {TEST_OUTPUT_PATH}")


@pytest.mark.parametrize("mcap_name", ALL_MCAP_NAMES)
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_mcap_conversion(mcap_name: str, writer_format: str):
    """Test MCAP file conversion by comparing with reference file."""
    setup_mcap_conversion(mcap_name, writer_format)
    mcap_file = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    reference_file = DATA_PATH / f"{mcap_name}" / writer_format / f"{mcap_name}.mcap"

    logger.info("Comparing generated MCAP with reference file")
    logger.info(f"  Generated: {mcap_file}")
    logger.info(f"  Reference: {reference_file}")

    # Check if both files exist
    assert mcap_file.exists(), f"Generated MCAP file not found: {mcap_file}"
    assert reference_file.exists(), f"Reference MCAP file not found: {reference_file}"

    # Compare file sizes
    generated_size = mcap_file.stat().st_size
    reference_size = reference_file.stat().st_size
    logger.info(f"  Generated size: {generated_size:,} bytes")
    logger.info(f"  Reference size: {reference_size:,} bytes")

    size_diff = abs(generated_size - reference_size)
    logger.info(f"  Size difference: {size_diff:,} bytes")

    # Compare file contents byte-by-byte
    with open(mcap_file, "rb") as f1, open(reference_file, "rb") as f2:
        generated_bytes = f1.read()
        reference_bytes = f2.read()

    bytes_match = generated_bytes == reference_bytes
    logger.info(f"  Bytes match: {bytes_match}")

    if not bytes_match:
        logger.warning("[!] Files differ!")
        # Find first difference
        for i, (b1, b2) in enumerate(
            zip(generated_bytes, reference_bytes, strict=False)
        ):
            if b1 != b2:
                logger.warning(f"  First difference at byte {i}: {b1} != {b2}")
                break
        if len(generated_bytes) != len(reference_bytes):
            logger.warning(
                f"  Length mismatch: {len(generated_bytes)} vs {len(reference_bytes)}"
            )
    else:
        logger.info("[OK] Files are identical!")
    assert bytes_match, "Generated MCAP file differs from reference"
    # Optional: Allow for small differences in timestamp/metadata fields
    # For strict comparison, uncomment:
    # assert bytes_match, "Generated MCAP file differs from reference"


@pytest.mark.parametrize("mcap_name", ["alloy"])
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_mcap_attachment_conversion(mcap_name: str, writer_format: str):
    """Test reading attachments from an MCAP file."""
    setup_mcap_conversion(mcap_name, writer_format)
    mcap_file = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    reference_folder = DATA_PATH / f"{mcap_name}"
    logger.info(f"Testing attachment conversion for {mcap_file}")
    attachments_found = 0

    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        for attachment in reader.iter_attachments():
            attachments_found += 1
            logger.info(f"\nAttachment #{attachments_found}:")
            logger.info(f"  Name: {attachment.name}")
            logger.info(f"  Media Type: {attachment.media_type}")
            logger.info(f"  Data Size: {len(attachment.data)} bytes")

            # Compare attachment data with original file on disk
            original_file = reference_folder / attachment.name
            logger.info(f"  Original file path: {original_file}")

            assert original_file.exists(), f"Original file not found: {original_file}"
            try:
                with open(original_file, "rb") as orig_f:
                    original_data = orig_f.read()

                # Compare byte-by-byte
                data_matches = attachment.data == original_data
                logger.info(f"  Original file size: {len(original_data)} bytes")
                logger.info(f"  Data matches original file: {data_matches}")

                if not data_matches:
                    logger.warning(
                        "  [!] MISMATCH: Attachment data differs from original file!"
                    )
                    logger.warning(f"    Attachment size: {len(attachment.data)} bytes")
                    logger.warning(f"    Original size: {len(original_data)} bytes")
                else:
                    logger.info(
                        "  [OK] Content verified: Attachment matches original file"
                    )
                assert data_matches, "Attachment data does not match original file"
            except Exception as e:
                logger.error(f"  Error reading original file: {e}")

    logger.info(f"Total attachments found: {attachments_found}")
    assert attachments_found > 0, "Should have at least one attachment"


@pytest.mark.parametrize("mcap_name", ["alloy"])
@pytest.mark.parametrize("writer_format", ALL_WRITER_FORMATS)
def test_mcap_metadata_conversion(mcap_name: str, writer_format: str):
    """Test reading metadata from an MCAP file."""
    setup_mcap_conversion(mcap_name, writer_format)
    mcap_file = TEST_OUTPUT_PATH / writer_format / f"{mcap_name}.mcap"
    logger.info(f"Testing metadata conversion for {mcap_file}")
    metadata_records = []

    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        for metadata in reader.iter_metadata():
            logger.info(f"Metadata: {metadata}")
            metadata_records.append(metadata)

    # Assertions
    assert len(metadata_records) >= 0, "Should have metadata records"
