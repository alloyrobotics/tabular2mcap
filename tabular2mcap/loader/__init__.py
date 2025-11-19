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

    # CSV/TSV formats
    if suffix in {".csv", ".tsv", ".txt"}:
        # Try to detect delimiter for TSV files
        delimiter = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(file_path, delimiter=delimiter)
    # Parquet format
    elif suffix == ".parquet":
        try:
            df = pd.read_parquet(file_path)
        except (ImportError, ValueError) as e:
            if "pyarrow" in str(e).lower():
                raise ImportError(
                    "Reading Parquet files requires 'pyarrow'. "
                    "Install with: pip install tabular2mcap[parquet]"
                ) from e
            raise
    # Feather format
    elif suffix == ".feather":
        try:
            df = pd.read_feather(file_path)
        except (ImportError, ValueError) as e:
            if "pyarrow" in str(e).lower():
                raise ImportError(
                    "Reading Feather files requires 'pyarrow'. "
                    "Install with: pip install tabular2mcap[feather]"
                ) from e
            raise
    # JSON formats
    elif suffix in {".json", ".jsonl"}:
        if suffix == ".jsonl":
            # JSON Lines format
            df = pd.read_json(file_path, lines=True, convert_dates=False)
        else:
            df = pd.read_json(file_path, convert_dates=False)
    # Excel formats
    elif suffix in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(file_path)
        except (ImportError, ValueError) as e:
            # ValueError can occur when required library is missing
            if "openpyxl" in str(e).lower() or "xlrd" in str(e).lower():
                raise ImportError(
                    "Reading Excel files requires 'openpyxl' (for .xlsx) or 'xlrd' (for .xls). "
                    "Install with: pip install tabular2mcap[excel] or pip install tabular2mcap[excel-legacy]"
                ) from e
            raise
    # ORC format
    elif suffix == ".orc":
        try:
            df = pd.read_orc(file_path)
        except (ImportError, ValueError) as e:
            if "pyarrow" in str(e).lower():
                raise ImportError(
                    "Reading ORC files requires 'pyarrow'. "
                    "Install with: pip install tabular2mcap[orc]"
                ) from e
            raise
    # XML format
    elif suffix == ".xml":
        try:
            df = pd.read_xml(file_path)
        except (ImportError, ValueError) as e:
            if "lxml" in str(e).lower():
                raise ImportError(
                    "Reading XML files requires 'lxml'. "
                    "Install with: pip install tabular2mcap[xml]"
                ) from e
            raise
    # Pickle formats
    elif suffix in {".pkl", ".pickle"}:
        df = pd.read_pickle(file_path)
    else:
        # Default to CSV for unknown extensions
        logger.warning(f"Unknown file extension '{suffix}'. Attempting to read as CSV.")
        df = pd.read_csv(file_path)

    return df


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
