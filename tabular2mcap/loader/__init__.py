import logging
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

from tabular2mcap.loader.models import (
    CompressedImageMappingConfig,
    CompressedVideoMappingConfig,
    ConverterFunctionDefinition,
    ConverterFunctionFile,
    FileMatchingConfig,
    LogMappingConfig,
    McapConversionConfig,
    OtherMappingTypes,
    TabularMappingConfig,
)

logger = logging.getLogger(__name__)


def load_tabular_data(file_path: Path, suffix: str | None = None) -> pd.DataFrame:
    """Load and preprocess tabular data from various formats.

    Supported formats:
    - CSV/TSV: .csv, .tsv, .txt (comma or tab delimited) - always available
    - Parquet: .parquet (requires: pip install tabular2mcap[parquet])
    - Feather: .feather (requires: pip install tabular2mcap[feather])
    - JSON: .json, .jsonl - always available
    - Excel: .xlsx, .xls (requires: pip install tabular2mcap[excel])
    - ORC: .orc (requires: pip install tabular2mcap[orc])
    - XML: .xml (requires: pip install tabular2mcap[xml])
    - Pickle: .pkl, .pickle - always available

    For all formats: pip install tabular2mcap[all-formats]

    Args:
        file_path: Path to the tabular data file
        suffix: Suffix of the file to load. If not provided, it will be inferred from the file extension.

    Returns:
        DataFrame containing the loaded data

    Raises:
        ValueError: If the file format is not supported
        ImportError: If required optional dependencies are missing
    """
    suffix = suffix or file_path.suffix.lower()

    def _try_read_with_optional_dep(reader_func, format_name: str, dep_name: str):
        """Helper to handle optional dependency imports."""
        try:
            return reader_func()
        except (ImportError, ValueError) as e:
            if dep_name in str(e).lower():
                raise ImportError(
                    f"Reading {format_name.title()} files requires '{dep_name}'. "
                    f"Install with: pip install tabular2mcap[{format_name}]"
                ) from e
            raise

    # CSV/TSV formats (always available)
    if suffix in {".csv", ".tsv", ".txt"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        return pd.read_csv(file_path, delimiter=delimiter)

    # JSON formats (always available)
    if suffix in {".json", ".jsonl"}:
        lines = suffix == ".jsonl"
        return pd.read_json(file_path, lines=lines, convert_dates=False)

    # Pickle formats (always available)
    if suffix in {".pkl", ".pickle"}:
        return pd.read_pickle(file_path)

    # Formats requiring optional dependencies
    if suffix == ".parquet":
        return _try_read_with_optional_dep(
            lambda: pd.read_parquet(file_path), "parquet", "pyarrow"
        )

    if suffix == ".feather":
        return _try_read_with_optional_dep(
            lambda: pd.read_feather(file_path), "feather", "pyarrow"
        )

    if suffix == ".orc":
        return _try_read_with_optional_dep(
            lambda: pd.read_orc(file_path), "orc", "pyarrow"
        )

    if suffix == ".xml":
        return _try_read_with_optional_dep(
            lambda: pd.read_xml(file_path), "xml", "lxml"
        )

    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(file_path)
        except (ImportError, ValueError) as e:
            if "openpyxl" in str(e).lower() or "xlrd" in str(e).lower():
                extra = "excel" if suffix == ".xlsx" else "excel-legacy"
                raise ImportError(
                    f"Reading Excel files requires 'openpyxl' (.xlsx) or 'xlrd' (.xls). "
                    f"Install with: pip install tabular2mcap[{extra}]"
                ) from e
            raise

    # Unknown format - try CSV
    logger.warning(f"Unknown file extension '{suffix}'. Attempting to read as CSV.")
    return pd.read_csv(file_path)


def load_video_data(file_path: Path) -> tuple[list[np.ndarray], dict]:
    cap = cv2.VideoCapture(file_path)
    logger.debug(f"Loaded video data from {file_path}")

    # Get video properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_props = {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
    }

    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames, video_props


def load_mcap_conversion_config(config_path: Path) -> McapConversionConfig:
    """Load and validate mapping configuration from YAML file"""
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return McapConversionConfig.model_validate(config)


def load_converter_function_definitions(path: Path) -> ConverterFunctionFile:
    """Load and validate converter function definitions from YAML file"""
    with open(path) as f:
        definitions = yaml.safe_load(f)
    return ConverterFunctionFile.model_validate(definitions)


def str_presenter(dumper, data):
    if "\n" in data:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.SafeDumper.add_representer(str, str_presenter)


def export_converter_function_definitions(
    conv_func_file: ConverterFunctionFile, path: Path
) -> None:
    """Export converter function definitions to YAML file.

    Args:
        conv_func_file: Converter function file
        path: Path to the converter functions file.
    """
    with open(path, "w") as f:
        yaml.safe_dump(
            data=conv_func_file.model_dump(),
            stream=f,
            default_flow_style=False,
            width=float("inf"),  # Prevent automatic line wrapping
        )


__all__ = [
    "AttachmentConfig",
    "CompressedImageMappingConfig",
    "CompressedVideoMappingConfig",
    "ConverterFunctionDefinition",
    "ConverterFunctionFile",
    "FileMatchingConfig",
    "LogMappingConfig",
    "McapConversionConfig",
    "MetadataConfig",
    "OtherMappingTypes",
    "TabularMappingConfig",
    "load_converter_function_definitions",
    "load_mcap_conversion_config",
    "load_tabular_data",
    "load_video_data",
]
