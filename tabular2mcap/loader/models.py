from typing import Annotated, Literal

from pydantic import BaseModel, Field

WRITER_FORMATS = Literal["ros1", "ros2", "json", "protobuf"]


class FileMatchingConfig(BaseModel):
    file_pattern: str = Field(
        description="The regex pattern to match files for mapping (e.g., '.*\\.csv')"
    )
    exclude_file_pattern: str | None = Field(
        description="Optional regex pattern to exclude files from mapping",
        default=None,
    )


class ConverterFunctionConfig(BaseModel):
    function_name: str = Field(
        description="The name of the converter function to use for the mapping. Must be a valid function name."
    )
    schema_name: str | None = Field(
        description="The name of the Foxglove schema to use for the mapping (e.g., 'LocationFix', 'FrameTransform')",
        default=None,
    )
    topic_suffix: str = Field(
        description="The suffix to append to the topic name for the mapping (e.g., 'LocationFix', 'FrameTransform')"
    )
    exclude_columns: list[str] | None = Field(
        description="The columns to exclude from the mapping", default=None
    )


class TabularMappingConfig(FileMatchingConfig):
    converter_functions: list[ConverterFunctionConfig] = Field(
        description="List of converter functions to apply to matched files. Each function generates a different topic",
        default_factory=list,
    )


class CompressedImageMappingConfig(FileMatchingConfig):
    type: Literal["compressed_image"] = "compressed_image"
    topic_suffix: str = Field(
        description="The suffix to append to the topic name for the mapping (e.g., 'CompressedImage')"
    )
    frame_id: str = Field(
        description="The frame ID to use for the mapping (e.g., 'camera')"
    )
    format: Literal["jpeg", "png", "webp", "avif"] = Field(
        description="The format of the image (e.g., 'jpeg', 'png', 'webp', 'avif')",
        default="jpeg",
    )

    def schema_name(self, writer_format: WRITER_FORMATS) -> str:
        if writer_format == "ros1":
            return "foxglove_msgs/CompressedImage"
        elif writer_format == "ros2":
            return "foxglove_msgs/msg/CompressedImage"
        else:
            return "foxglove.CompressedImage"


class CompressedVideoMappingConfig(FileMatchingConfig):
    type: Literal["compressed_video"] = "compressed_video"
    topic_suffix: str = Field(
        description="The suffix to append to the topic name for the mapping (e.g., 'CompressedVideo')"
    )
    frame_id: str = Field(
        description="The frame ID to use for the mapping (e.g., 'camera')"
    )
    format: Literal["h264", "h265", "vp9", "av1"] = Field(
        description="The format of the video (e.g., 'h264', 'h265', 'vp9', 'av1')",
        default="h264",
    )

    def schema_name(self, writer_format: WRITER_FORMATS) -> str:
        if writer_format == "ros1":
            return "foxglove_msgs/CompressedVideo"
        elif writer_format == "ros2":
            return "foxglove_msgs/msg/CompressedVideo"
        else:
            return "foxglove.CompressedVideo"


class LogMappingConfig(FileMatchingConfig):
    type: Literal["log"] = "log"
    topic_suffix: str | None = Field(
        description="The suffix to append to the topic name for the mapping. If none, the full topic name will be 'rosout'",
        default=None,
    )
    format_template: str = Field(
        description="The Jinja2 template to use for the format of the log. Uses variables: levelname, asctime, filename, lineno, message.",
        default=r"^{{levelname}}\s{{asctime}}\s{{filename}}:{{lineno}}\s{{message}}$",
    )
    datetime_format: str = Field(
        description="The format of the timestamp in the log file (default: '%Y-%m-%d %H:%M:%S')",
        default="%Y-%m-%d %H:%M:%S",
    )

    def schema_name(self, writer_format: WRITER_FORMATS) -> str:
        if writer_format == "ros1":
            return "rosgraph_msgs/Log"
        elif writer_format == "ros2":
            return "rcl_interfaces/msg/Log"
        else:
            return "foxglove.Log"


OtherMappingTypes = Annotated[
    CompressedImageMappingConfig | CompressedVideoMappingConfig | LogMappingConfig,
    Field(discriminator="type"),
]


class AttachmentConfig(FileMatchingConfig):
    mime_type: str | None = Field(
        description="The MIME type of the attachment. If not provided, the MIME type will be inferred from the file extension.",
        default=None,
    )


class MetadataConfig(FileMatchingConfig):
    separator: str = Field(description="The separator to use for the metadata file.")


class McapConversionConfig(BaseModel):
    writer_format: WRITER_FORMATS = Field(
        default="json",
        description="The writer format for the MCAP file. Currently only 'json' is fully supported.",
    )
    tabular_mappings: list[TabularMappingConfig] = Field(
        description="List of file mapping configurations. Files are processed in order.",
        default_factory=list,
    )
    other_mappings: list[OtherMappingTypes] = Field(
        description="List of other mapping configurations.",
        default_factory=list,
    )
    attachments: list[AttachmentConfig] = Field(
        description="List of attachment configurations.",
        default_factory=list,
    )
    metadata: list[MetadataConfig] = Field(
        description="List of metadata configurations.",
        default_factory=list,
    )


class ConverterFunctionDefinition(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    schema_name: str | None = Field(
        description="The name of the schema to use for the mapping. If none, schema type is not checked.",
        default=None,
    )
    template: str = Field(
        description="The Jinja2 template to use for the mapping.", default="{}"
    )
    log_time_template: str | None = Field(
        description="Jinja2 template to use to map columns to log time ns. If none, the log time will be taken from timestamp or header.stamp",
        default=None,
    )
    publish_time_template: str | None = Field(
        description="Jinja2 template to use to map columns to publish time ns. If none, the publish time will be log_time",
        default=None,
    )
    available_columns: list[str] = Field(
        description="The columns that are available for the mapping. Not yet used. Placeholder for future template validation.",
        default=list,
    )


class ConverterFunctionFile(BaseModel):
    functions: dict[str, ConverterFunctionDefinition] = Field(
        description="The dictionary of converter function definitions.",
        default_factory=dict,
    )
