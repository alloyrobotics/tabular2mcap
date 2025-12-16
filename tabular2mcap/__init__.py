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


# =============================================================================
# CLI Utilities - Composable functions for building CLIs
# =============================================================================


def create_base_parser(
    description: str = "Convert tabular data to MCAP format",
    prog: str = "tabular2mcap",
    include_gen_subcommand: bool = True,
) -> argparse.ArgumentParser:
    """Create base argument parser with common arguments.

    This function creates a reusable argument parser with all the standard
    CLI arguments. Subpackages (e.g., tabular2mcap-pro) can use this to
    build their CLIs without duplicating argument definitions.

    Args:
        description: CLI description for help text
        prog: Program name for help text
        include_gen_subcommand: Whether to include the 'gen' subcommand

    Returns:
        Configured ArgumentParser with common arguments
    """
    parser = argparse.ArgumentParser(description=description, prog=prog)

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
    if include_gen_subcommand:
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
        generate_parser.add_argument(
            "-c", "--config", type=str, help="Config file path"
        )
        generate_parser.add_argument(
            "-f",
            "--functions",
            type=str,
            help="Path to output converter functions YAML file",
        )

    return parser


def validate_input_path(input_path: Path | None, log: logging.Logger) -> bool:
    """Validate that input path exists and is a directory.

    Args:
        input_path: Path to validate
        log: Logger instance for error messages

    Returns:
        True if valid, False otherwise (with error logged)
    """
    if input_path is None:
        log.error("Input path is required")
        return False
    if not input_path.exists():
        log.error(f"Target directory '{input_path}' does not exist")
        return False
    if not input_path.is_dir():
        log.error(f"'{input_path}' is not a directory")
        return False
    return True


def resolve_paths(
    args: argparse.Namespace,
    input_path: Path,
    default_funcs_filename: str = "converter_functions.yaml",
) -> tuple[Path, Path, Path]:
    """Resolve config, output, and converter functions paths from CLI args.

    Args:
        args: Parsed CLI arguments (must have config, output, functions attrs)
        input_path: Validated input directory path
        default_funcs_filename: Default converter functions filename

    Returns:
        Tuple of (config_path, output_path, converter_functions_path)
    """
    config_path = Path(args.config) if args.config else input_path / "config.yaml"

    if args.output:
        output_path = Path(args.output)
        # If output ends with a slash, treat it as a directory and add a default filename
        if output_path.is_dir() or str(output_path).endswith("/"):
            output_path = output_path / "output.mcap"
    else:
        output_path = input_path / "output.mcap"

    converter_functions_path = (
        Path(args.functions) if args.functions else input_path / default_funcs_filename
    )

    return config_path, output_path, converter_functions_path


# =============================================================================
# Main CLI Entry Point
# =============================================================================


def main() -> None:
    program_start_time = time.time()
    parser = create_base_parser()
    args = parser.parse_args()

    # Convert to Path object for easier handling
    input_path = Path(args.input) if args.input else None
    if not validate_input_path(input_path, logger):
        sys.exit(1)
    assert input_path is not None  # Guaranteed by validate_input_path

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
        config_path, output_path, converter_functions_path = resolve_paths(
            args, input_path
        )

        if not config_path.exists():
            logger.error(f"Config file '{config_path}' does not exist")
            sys.exit(1)

        output_path.parent.mkdir(parents=True, exist_ok=True)

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
