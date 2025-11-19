import argparse
import logging
import sys
import time
from pathlib import Path

from tabular2mcap.mcap_converter import McapConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_tabular_to_mcap(
    input_path: Path,
    output_path: Path,
    config_path: Path,
    topic_prefix: str,
    converter_functions_path: Path,
    test_mode: bool = False,
    best_effort: bool = False,
    strip_file_suffix: bool = False,
) -> None:
    """
    Convert tabular and multimedia data to MCAP format.

    This is a convenience wrapper around the McapConverter class.
    For more control, use McapConverter directly.

    Args:
        input_path: Path to the input directory containing tabular data files
        output_path: Path to the output MCAP file
        config_path: Path to the config file
        topic_prefix: Optional prefix to prepend to all topic names in the generated MCAP file
        converter_functions_path: Path to the converter functions YAML file
        test_mode: Test mode: only process the first 5 rows of each CSV file
        best_effort: Continue converting even if errors occur (logs errors but doesn't stop)
        strip_file_suffix: If True, removes file extensions from topic names

    Returns:
        None
    """
    converter = McapConverter(
        config_path=config_path, converter_functions_path=converter_functions_path
    )
    converter.convert(
        input_path=input_path,
        output_path=output_path,
        topic_prefix=topic_prefix,
        test_mode=test_mode,
        best_effort=best_effort,
        strip_file_suffix=strip_file_suffix,
    )


def generate_converter_functions(
    input_path: Path,
    config_path: Path,
    converter_functions_path: Path,
) -> None:
    """
    Generate converter_functions.yaml file based on config.yaml.

    This function analyzes the config.yaml file and generates a converter_functions.yaml
    file with empty function definitions for each function_name referenced in the config.

    Args:
        input_path: Path to the input directory containing tabular data files
        config_path: Path to the config file
        converter_functions_path: Path to the output converter functions YAML file

    Returns:
        None
    """
    converter = McapConverter(config_path=config_path)
    converter.generate_converter_functions(
        input_path=input_path, output_path=converter_functions_path
    )


def main() -> None:
    program_start_time = time.time()
    parser = argparse.ArgumentParser(
        description="Convert tabular data to MCAP format", prog="tabular2mcap"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=False
    )

    # Default arguments (for convert command when no subcommand is specified)
    parser.add_argument(
        "-i", "--input", type=str, help="Input directory containing tabular data files"
    )
    parser.add_argument("-o", "--output", type=str, help="Output MCAP file path")
    parser.add_argument("-c", "--config", type=str, help="Config file path")
    parser.add_argument(
        "-t",
        "--topic-prefix",
        type=str,
        default="",
        help="Optional prefix to prepend to all topic names in the generated MCAP file",
    )
    parser.add_argument(
        "-f",
        "--functions",
        type=str,
        help="Path to converter functions YAML file",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode: only process the first 5 rows of each CSV file",
    )
    parser.add_argument(
        "--best-effort",
        action="store_true",
        help="Continue converting even if errors occur (logs errors but doesn't stop)",
    )
    parser.add_argument(
        "--strip-file-suffix",
        action="store_true",
        help="Remove file extensions from topic names",
    )

    # Subparser for gen command (generate converter_functions.yaml template)
    generate_parser = subparsers.add_parser(
        "gen",
        help="Generate converter_functions.yaml template based on config.yaml",
    )
    generate_parser.add_argument(
        "-i",
        "--input",
        type=str,
        required=True,
        help="Input directory containing tabular data files",
    )
    generate_parser.add_argument("-c", "--config", type=str, help="Config file path")
    generate_parser.add_argument(
        "-f",
        "--functions",
        type=str,
        help="Path to output converter functions YAML file",
    )

    args = parser.parse_args()
    # Convert to Path object for easier handling
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Target directory '{input_path}' does not exist")
        sys.exit(1)

    if not input_path.is_dir():
        logger.error(f"'{input_path}' is not a directory")
        sys.exit(1)

    # Handle different commands
    if args.command == "gen":
        config_path = Path(args.config) if args.config else input_path / "config.yaml"
        if not config_path.exists():
            logger.error(f"Config file '{config_path}' does not exist")
            sys.exit(1)

        converter_functions_path = (
            Path(args.functions)
            if args.functions
            else input_path / "generated_converter_functions.yaml"
        )
        generate_converter_functions(
            input_path,
            config_path,
            converter_functions_path,
        )
    else:  # Default: convert command
        config_path = Path(args.config) if args.config else input_path / "config.yaml"
        if not config_path.exists():
            logger.error(f"Config file '{config_path}' does not exist")
            sys.exit(1)

        if args.output:
            output_path = Path(args.output)
            # If output ends with a slash, treat it as a directory and add a default filename
            if output_path.is_dir() or str(output_path).endswith("/"):
                output_path = output_path / "output.mcap"
        else:
            output_path = input_path / "output.mcap"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        converter_functions_path = (
            Path(args.functions)
            if args.functions
            else input_path / "converter_functions.yaml"
        )
        convert_tabular_to_mcap(
            input_path,
            output_path,
            config_path,
            args.topic_prefix,
            converter_functions_path,
            args.test_mode,
            args.best_effort,
            args.strip_file_suffix,
        )

    # Calculate and log total program execution time
    program_end_time = time.time()
    total_program_time = program_end_time - program_start_time
    logger.info(f"Total execution time: {total_program_time:.2f} seconds")
