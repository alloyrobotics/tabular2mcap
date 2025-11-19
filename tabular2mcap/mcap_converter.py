import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mcap.writer import Writer as McapWriter
from mcap_ros2.writer import Writer as McapRos2Writer
from tqdm import tqdm

from tabular2mcap.schemas.cache import download_and_cache_all_repos

from .converter import ConverterBase, JsonConverter, Ros2Converter
from .converter.functions import (
    ConverterFunction,
    ConverterFunctionJinja2Environment,
    generate_generic_converter_func,
)
from .converter.others import (
    LogConverter,
    compressed_image_message_iterator,
    compressed_video_message_iterator,
)
from .loader import (
    CompressedImageMappingConfig,
    CompressedVideoMappingConfig,
    ConverterFunctionDefinition,
    ConverterFunctionFile,
    LogMappingConfig,
    McapConversionConfig,
    export_converter_function_definitions,
    load_converter_function_definitions,
    load_mcap_conversion_config,
    load_tabular_data,
    load_video_data,
)

logger = logging.getLogger(__name__)

SUPPORT_WRITER_FORMATS = ["json", "ros2"]


class McapConverter:
    """Main class for converting tabular and multimedia data to MCAP format."""

    mcap_config: McapConversionConfig
    converter_functions: dict[str, Any]
    shared_jinja2_env: ConverterFunctionJinja2Environment

    _writer: McapWriter | McapRos2Writer
    _converter: ConverterBase
    _schema_ids: dict[str, int]

    def __init__(
        self,
        config_path: Path | None = None,
        converter_functions_path: Path | None = None,
    ):
        """
        Initialize the MCAP converter.

        Args:
            config_path: Path to the configuration file or McapConversionConfig object
            converter_functions_path: Path to the converter functions file
        """
        # Initialize schema IDs
        self._schema_ids = {}

        if config_path is not None:
            self.load_config(config_path)
            logger.info(f"Config: {config_path}")

        self.shared_jinja2_env = ConverterFunctionJinja2Environment()
        if converter_functions_path is not None:
            self.load_converter_functions(converter_functions_path)
            logger.info(f"Converter functions: {converter_functions_path}")
        download_and_cache_all_repos(distro="jazzy")

    def load_config(self, config_path: Path) -> None:
        """Load mapping configuration from YAML file"""
        self.mcap_config = load_mcap_conversion_config(config_path)

    def load_converter_functions(self, functions_path: Path) -> None:
        """Load converter function definitions.

        Args:
            functions_path: Path to the converter functions file
        """

        self.converter_functions = {}
        if functions_path.exists():
            converter_definitions = load_converter_function_definitions(functions_path)
            logger.info(
                f"Loaded {len(converter_definitions.functions)} converter function definitions"
            )
            self.converter_functions = {
                k: ConverterFunction(definition=v)
                for k, v in converter_definitions.functions.items()
            }
        else:
            logger.warning(f"Converter functions file {functions_path} does not exist")

        for converter_function in self.converter_functions.values():
            converter_function.jinja2_env = self.shared_jinja2_env
            converter_function.init_jinja2_template()

    def _clean_string(self, string: str) -> str:
        """Clean a string by removing special characters and replacing spaces with underscores."""
        return re.sub(r"[ .-]", "", string)

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        topic_prefix: str = "",
        test_mode: bool = False,
        best_effort: bool = False,
    ) -> None:
        """
        Convert tabular and multimedia data to MCAP format.

        Args:
            input_path: Path to the input directory
            output_path: Path to the output MCAP file
            topic_prefix: Prefix for topic names
            test_mode: If True, limits data processing for testing
            best_effort: If True, continues converting even if errors occur (logs errors)
        """
        logger.info(f"Input directory: {input_path}")
        logger.info(f"Output MCAP: {output_path}")

        if self.mcap_config.writer_format not in SUPPORT_WRITER_FORMATS:
            raise ValueError(
                f"Writer format {self.mcap_config.writer_format} is not supported"
            )

        with open(output_path, "wb") as f:
            if self.mcap_config.writer_format == "json":
                self._writer = McapWriter(f)
                self._writer.start()
                self._converter = JsonConverter(self._writer)
            elif self.mcap_config.writer_format == "ros2":
                self._writer = McapRos2Writer(f)
                self._converter = Ros2Converter(self._writer)

            # Print conversion plan
            logger.info("\n" + "=" * 60)
            logger.info("MCAP Conversion Plan")
            logger.info("=" * 60)
            logger.info(
                f"Tabular mappings:      {len(self.mcap_config.tabular_mappings)}"
            )
            logger.info(
                f"Other mappings:        {len(self.mcap_config.other_mappings)}"
            )
            logger.info(f"Attachments:           {len(self.mcap_config.attachments)}")
            logger.info(f"Metadata:              {len(self.mcap_config.metadata)}")
            logger.info("=" * 60 + "\n")

            # Prepare data for processing
            mapping_tuples = self._prepare_mapping_tuples(input_path)

            # Process all data types
            self._process_tabular_mappings(
                mapping_tuples["tabular"],
                input_path,
                topic_prefix,
                test_mode,
                best_effort,
            )
            self._process_other_mappings(
                mapping_tuples["other"], input_path, topic_prefix, best_effort
            )
            self._process_attachments(
                mapping_tuples["attachments"], input_path, best_effort
            )
            self._process_metadata(mapping_tuples["metadata"], input_path, best_effort)

            # Finish writing
            print("\n" + "=" * 60)
            print("Finalizing MCAP file...")
            print("=" * 60)
            self._writer.finish()

            # Print summary
            print("\n" + "=" * 60)
            print("[OK] Conversion completed successfully!")
            print(f"[OK] Output file: {output_path}")
            print(
                f"[OK] File size: {output_path.stat().st_size / (1024 * 1024):.2f} MB"
            )
            print("=" * 60)

    def _process_file_mappings(self, mappings: list, input_path: Path) -> list:
        """Process file mappings and return tuples of (mapping, file_path)."""
        mapping_tuples = []

        if len(mappings) > 0:
            logger.info(
                f"Processing {mappings[0].__class__.__name__} mappings: {len(mappings)} configs"
            )

        for mapping in mappings:
            logger.info(
                f"File pattern: {mapping.file_pattern}, exclude: {mapping.exclude_file_pattern}"
            )
            for input_file in input_path.glob(mapping.file_pattern):
                relative_path = input_file.relative_to(input_path)
                if mapping.exclude_file_pattern and re.match(
                    mapping.exclude_file_pattern, relative_path.name
                ):
                    logger.info(
                        f"Skipping {relative_path} because it matches exclude_file_pattern"
                    )
                else:
                    mapping_tuples.append((mapping, input_file))

        return mapping_tuples

    def _prepare_mapping_tuples(self, input_path: Path) -> dict[str, list]:
        """Prepare mapping tuples for all data types."""
        mappings = {
            "tabular": self.mcap_config.tabular_mappings,
            "other": self.mcap_config.other_mappings,
            "attachments": self.mcap_config.attachments,
            "metadata": self.mcap_config.metadata,
        }
        return {
            k: self._process_file_mappings(v, input_path) for k, v in mappings.items()
        }

    def _load_dataframe(self, input_file: Path) -> pd.DataFrame:
        """Load a dataframe from a file."""
        df = load_tabular_data(input_file)
        df.columns = df.columns.str.replace("[ .-]", "_", regex=True).str.replace(
            "[^A-Za-z0-9_]", "", regex=True
        )
        # Clean for JSON encoding: replace inf/-inf with max float32 (safe for squaring), NaN with None
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            max_float, min_float = (
                np.finfo(np.float32).max,
                np.finfo(np.float32).min,
            )  # 3.4e+38, safe when squared
            df[numeric_cols] = df[numeric_cols].replace(
                [np.inf, -np.inf], [max_float, min_float]
            )
        return df.where(pd.notna(df), None)

    def _process_tabular_mappings(
        self,
        mapping_tuples: list,
        input_path: Path,
        topic_prefix: str = "",
        test_mode: bool = False,
        best_effort: bool = False,
    ):
        """Process tabular data mappings."""

        for file_mapping, input_file in tqdm(
            mapping_tuples,
            desc="Processing tabular data",
            leave=False,
            unit="file",
        ):
            try:
                relative_path = input_file.relative_to(input_path)
                df = self._load_dataframe(input_file)

                # Apply test mode if enabled
                if test_mode:
                    original_rows = len(df)
                    df = df.head(5)
                    logger.debug(
                        f"Converting {relative_path} with {len(df)} rows (test mode: limited from {original_rows} rows)"
                    )
                else:
                    logger.debug(f"Converting {relative_path} with {len(df)} rows")

                for converter_function in file_mapping.converter_functions:
                    logger.debug(
                        f"Processing converter function: {converter_function.function_name}"
                    )

                    # Get converter function definition
                    if converter_function.function_name in self.converter_functions:
                        converter_def = self.converter_functions[
                            converter_function.function_name
                        ]

                        # Get relative path without extension
                        relative_path_no_ext = self._clean_string(str(relative_path))
                        topic_name = f"{topic_prefix}{relative_path_no_ext}/{converter_function.topic_suffix}"

                        # try to convert first row to check if the converter function is valid
                        # if not, this will raise an exception. if yes, we can proceed with the conversion.
                        converter_def.convert_row(df.iloc[0])

                        # register schema
                        if converter_function.schema_name is None:
                            if self.mcap_config.writer_format == "ros2":
                                schema_name = Ros2Converter.sanitize_schema_name(
                                    topic_name
                                )
                            else:
                                schema_name = f"table.{topic_name.replace('/', '.')}"
                            schema_id, schema_keys = (
                                self._converter.register_generic_schema(
                                    df=df,
                                    schema_name=schema_name,
                                    exclude_keys=converter_function.exclude_columns
                                    or [],
                                )
                            )
                            convert_row = generate_generic_converter_func(
                                schema_keys=schema_keys,
                                converter_func=converter_def.convert_row,
                            )
                            self._schema_ids[schema_name] = schema_id
                        elif converter_function.schema_name in self._schema_ids:
                            schema_id = self._schema_ids[converter_function.schema_name]
                            convert_row = converter_def.convert_row
                        else:
                            convert_row = converter_def.convert_row
                            schema_id = self._converter.register_schema(
                                schema_name=converter_function.schema_name,
                            )
                            self._schema_ids[converter_function.schema_name] = schema_id

                        # write messages
                        if schema_id is not None:

                            def convert_row_iterator() -> Iterable[tuple[int, dict]]:
                                for idx, row in df.iterrows():  # noqa: B023
                                    yield idx, convert_row(row)  # noqa: B023

                            self._converter.write_messages_from_iterator(
                                iterator=convert_row_iterator(),
                                topic_name=topic_name,
                                schema_id=schema_id,
                                data_length=len(df),
                                unit="msg",
                            )
                    else:
                        raise ValueError(
                            f"Unknown converter function: {converter_function.function_name}. Available functions: {list(self.converter_functions.keys())}"
                        )
            except Exception as e:
                if best_effort:
                    logger.error(
                        f"Error processing tabular file {input_file.relative_to(input_path)}: {e}"
                    )
                else:
                    raise

    def _process_other_mappings(
        self,
        mapping_tuples: list,
        input_path: Path,
        topic_prefix: str = "",
        best_effort: bool = False,
    ):
        """Process other mappings (images, videos, etc.)."""

        for other_mapping, input_file in tqdm(
            mapping_tuples,
            desc="Processing other mappings data",
            leave=False,
            unit="file",
        ):
            try:
                relative_path = input_file.relative_to(input_path)
                logger.debug(
                    f"Processing other mapping: {other_mapping.type} {relative_path}"
                )

                relative_path_no_ext = self._clean_string(
                    str(relative_path.with_suffix(""))
                )
                topic_name_prefix = f"{topic_prefix}{relative_path_no_ext}/"

                # Get or register schema
                schema_name = other_mapping.schema_name(self.mcap_config.writer_format)
                if schema_name in self._schema_ids:
                    schema_id = self._schema_ids[schema_name]
                else:
                    schema_id = self._converter.register_schema(schema_name=schema_name)
                    self._schema_ids[schema_name] = schema_id

                if isinstance(
                    other_mapping,
                    (CompressedImageMappingConfig, CompressedVideoMappingConfig),
                ):
                    video_frames, video_properties = load_video_data(input_file)
                    logger.debug(
                        f"Loaded video data from {input_file}: {len(video_frames)} frames. Video properties: {video_properties}"
                    )

                    # Create frame iterator based on type
                    if isinstance(other_mapping, CompressedImageMappingConfig):
                        frame_iterator = compressed_image_message_iterator
                    else:  # CompressedVideoMappingConfig
                        frame_iterator = compressed_video_message_iterator

                    self._converter.write_messages_from_iterator(
                        iterator=enumerate(
                            frame_iterator(
                                video_frames=video_frames,
                                fps=video_properties["fps"],
                                format=other_mapping.format,
                                frame_id=other_mapping.frame_id,
                            )
                        ),
                        topic_name=f"{topic_name_prefix}{other_mapping.topic_suffix}",
                        schema_id=schema_id,
                        data_length=len(video_frames),
                        unit="fr",
                    )
                elif isinstance(other_mapping, LogMappingConfig):
                    log_converter = LogConverter(
                        log_path=input_file,
                        format_template=other_mapping.format_template,
                        writer_format=self.mcap_config.writer_format,
                        zero_first_timestamp=True,
                        name=relative_path_no_ext,
                        datetime_format=other_mapping.datetime_format,
                    )
                    self._converter.write_messages_from_iterator(
                        iterator=enumerate(log_converter.log_iter()),
                        topic_name=(
                            "rosout"
                            if other_mapping.topic_suffix is None
                            else f"{topic_name_prefix}{other_mapping.topic_suffix}"
                        ),
                        schema_id=schema_id,
                        data_length=None,
                        unit="fr",
                    )
                else:
                    raise ValueError(
                        f"Unknown other mapping type: {other_mapping.type}"
                    )
            except Exception as e:
                if best_effort:
                    logger.error(
                        f"Error processing other mapping {input_file.relative_to(input_path)}: {e}"
                    )
                else:
                    raise

    def _process_attachments(
        self, mapping_tuples: list, input_path: Path, best_effort: bool = False
    ):
        """Process attachment data."""

        for _attachment, input_file in tqdm(
            mapping_tuples,
            desc="Processing attachments data",
            leave=False,
            unit="file",
        ):
            try:
                relative_path = input_file.relative_to(input_path)
                with open(input_file, "rb") as attachment_file:
                    data = attachment_file.read()
                    stat = input_file.stat()
                    # Convert file creation/modification time to nanoseconds (integer)
                    # Use st_birthtime (creation) if available, otherwise st_ctime (change time)
                    create_time_ns = (
                        int(stat.st_birthtime * 1_000_000_000)
                        if hasattr(stat, "st_birthtime")
                        else int(stat.st_ctime * 1_000_000_000)
                    )
                    log_time_ns = int(
                        stat.st_mtime * 1_000_000_000
                    )  # modification time
                    self._converter.writer.add_attachment(
                        create_time_ns,
                        log_time_ns,
                        str(relative_path),
                        "text/plain",
                        data,
                    )
            except Exception as e:
                if best_effort:
                    logger.error(
                        f"Error processing attachment {input_file.relative_to(input_path)}: {e}"
                    )
                else:
                    raise

    def _process_metadata(
        self, mapping_tuples: list, input_path: Path, best_effort: bool = False
    ):
        """Process metadata."""

        for metadata, input_file in tqdm(
            mapping_tuples,
            desc="Processing metadata data",
            leave=False,
            unit="file",
        ):
            try:
                relative_path = input_file.relative_to(input_path)
                with open(input_file) as metadata_file:
                    key_value_list = [
                        line.strip().split(metadata.separator)
                        for line in metadata_file.readlines()
                    ]
                    metadata_dict: dict[str, str] = {
                        kv[0].strip(): kv[1].strip()
                        for kv in key_value_list
                        if len(kv) >= 2
                    }
                    self._converter.writer.add_metadata(
                        str(relative_path), metadata_dict
                    )
            except Exception as e:
                if best_effort:
                    logger.error(
                        f"Error processing metadata {input_file.relative_to(input_path)}: {e}"
                    )
                else:
                    raise

    def generate_converter_functions(self, input_path: Path, output_path: Path) -> None:
        """Generate converter functions."""
        if self.mcap_config.writer_format == "json":
            self._converter = JsonConverter()
        elif self.mcap_config.writer_format == "ros2":
            self._converter = Ros2Converter()

        conv_func_file = ConverterFunctionFile()
        conv_func_to_file_pattern_map = {}

        for mappings in self.mcap_config.tabular_mappings:
            for conv_func in mappings.converter_functions:
                if conv_func.function_name not in conv_func_file.functions:
                    if conv_func.schema_name is None:
                        schema_json = "{}"
                    else:
                        schema_json = self._converter.get_schema_template(
                            conv_func.schema_name
                        )
                    conv_func_file.functions[conv_func.function_name] = (
                        ConverterFunctionDefinition(
                            schema_name=conv_func.schema_name,
                            log_time_template="{{ <timestamp_nanosec_column> | int }}",
                            publish_time_template=None,
                            available_columns=[],
                            template=schema_json,
                        )
                    )
                    conv_func_to_file_pattern_map[conv_func.function_name] = []
                if (
                    conv_func.schema_name
                    != conv_func_file.functions[conv_func.function_name].schema_name
                ):
                    raise TypeError(
                        "Converter function returning different schema types"
                    )
                conv_func_to_file_pattern_map[conv_func.function_name].append(
                    mappings.file_pattern
                )

        for conv_func, file_patterns in conv_func_to_file_pattern_map.items():
            conv_func_def = conv_func_file.functions[conv_func]
            for file_pattern in file_patterns:
                for input_file in input_path.glob(file_pattern):
                    relative_path = input_file.relative_to(input_path)
                    df = self._load_dataframe(input_file)

                    conv_func_def.available_columns.append(
                        f"{relative_path}: {', '.join(df.columns)}"
                    )
            logger.info(f"Converter: {conv_func} File patterns: {file_patterns}")

        export_converter_function_definitions(
            conv_func_file=conv_func_file, path=output_path
        )
        logger.info(f"Generating converter functions to {output_path}")
