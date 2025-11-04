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


def load_tabular_data(file_path: Path) -> pd.DataFrame:
    """Load and preprocess tabular data"""
    if file_path.suffix == ".parquet":
        df = pd.read_parquet(file_path)
    else:
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
