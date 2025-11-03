import logging
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import numpy as np
from jinja2 import Template

from tabular2mcap.converter.common import ConvertedRow
from tabular2mcap.loader.models import WRITER_FORMATS

logger = logging.getLogger(__name__)


def compressed_image_message_iterator(
    video_frames: list[np.ndarray], fps: float, format: str, frame_id: str
) -> Iterable[ConvertedRow]:
    """Generate compressed image messages from video frames."""
    try:
        import cv2
    except ImportError as e:
        raise ImportError(
            "OpenCV is not installed. Please install it using `uv sync --group others`"
        ) from e

    supported_formats = {"jpeg", "png", "webp", "avif"}
    if format not in supported_formats:
        raise ValueError(
            f"CompressedImage unsupported format: {format}. Supported formats: {supported_formats}"
        )

    # Process each video frame as a compressed image
    for frame_idx, frame in enumerate(video_frames):
        if format in ["jpeg", "jpg"]:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            _, encoded_img = cv2.imencode(".jpg", frame, encode_param)
        elif format in ["png", "webp", "avif"]:
            _, encoded_img = cv2.imencode(f".{format}", frame)

        # Calculate timestamp based on video properties
        frame_timestamp = frame_idx / fps

        # Create compressed image message
        yield ConvertedRow(
            data={
                "timestamp": {
                    "sec": int(frame_timestamp),
                    "nsec": int((frame_timestamp % 1) * 1_000_000_000),
                },
                "frame_id": frame_id,
                "data": encoded_img.tobytes(),  # base64.b64encode(encoded_img.tobytes()).decode("utf-8"),
                "format": format,
            },
            log_time_ns=int(frame_timestamp * 1_000_000_000),
            publish_time_ns=int(frame_timestamp * 1_000_000_000),
        )


def compressed_video_message_iterator(
    video_frames: list[np.ndarray], fps: float, format: str, frame_id: str
) -> Iterable[ConvertedRow]:
    """Generate compressed video messages from video frames."""
    try:
        import av
        import cv2
    except ImportError as e:
        raise ImportError(
            "PyAV or OpenCV is not installed. Please install it using `uv sync --group others`"
        ) from e

    # Get frame dimensions from first frame
    height, width = video_frames[0].shape[:2]
    supported_formats = {"h264", "h265", "vp9", "av1"}
    if format not in supported_formats:
        raise ValueError(
            f"CompressedVideo unsupported format: {format}. Supported formats: {supported_formats}"
        )
    elif format not in av.codecs_available:
        raise ValueError(
            f"Installed ffmped does not support format: {format}. Supported formats: {set(av.codecs_available) & supported_formats}"
        )

    # Create codec context based on format
    codec = av.codec.CodecContext.create(format, "w")
    codec.width = width
    codec.height = height
    codec.framerate = int(fps)

    # Set pixel format based on codec
    if format in ["h264", "h265"] or format == "vp9" or format == "av1":
        codec.pix_fmt = "yuv420p"

    codec.open()

    # Encode frames
    frame_timestamp = 0
    frame_timestamp_step = 1 / fps
    for frame_idx, frame in enumerate(video_frames):
        # Convert BGR to RGB (OpenCV uses BGR, PyAV expects RGB)
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame
        # Create PyAV frame
        av_frame = av.VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        av_frame.pts = frame_idx

        # Encode frame
        packets = codec.encode(av_frame)
        for packet in packets:
            yield ConvertedRow(
                data={
                    "timestamp": {
                        "sec": int(frame_timestamp),
                        "nsec": int((frame_timestamp % 1) * 1_000_000_000),
                    },
                    "frame_id": frame_id,
                    "data": bytes(
                        packet
                    ),  # base64.b64encode(bytes(packet)).decode("utf-8"),
                    "format": format,
                },
                log_time_ns=int(frame_timestamp * 1_000_000_000),
                publish_time_ns=int(frame_timestamp * 1_000_000_000),
            )
            frame_timestamp += frame_timestamp_step

    packets = codec.encode(None)
    for packet in packets:
        yield ConvertedRow(
            data={
                "timestamp": {
                    "sec": int(frame_timestamp),
                    "nsec": int((frame_timestamp % 1) * 1_000_000_000),
                },
                "frame_id": frame_id,
                "data": bytes(
                    packet
                ),  # base64.b64encode(bytes(packet)).decode("utf-8"),
                "format": format,
            },
            log_time_ns=int(frame_timestamp * 1_000_000_000),
            publish_time_ns=int(frame_timestamp * 1_000_000_000),
        )
        frame_timestamp += frame_timestamp_step


def to_foxglove_log_level(level: str) -> int:
    """Convert log level string to foxglove.Log level constant.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, FATAL)

    Returns:
        Integer level constant for foxglove.Log:
            - DEBUG: 1
            - INFO: 2
            - WARNING: 3
            - ERROR: 4
            - FATAL: 5
            - Unknown: 0
    """
    level = level.strip().upper()
    if level == "DEBUG":  # noqa: SIM116
        return 1
    elif level == "INFO":
        return 2
    elif level == "WARNING":
        return 3
    elif level == "ERROR":
        return 4
    elif level == "FATAL":
        return 5
    else:
        return 0


def to_ros2_log_level(level: str) -> int:
    """Convert log level string to ROS2 log level constant.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, FATAL)

    Returns:
        Integer level constant for ROS2 log
    """
    level = level.strip().upper()
    if level == "DEBUG":  # noqa: SIM116
        return 10
    elif level == "INFO":
        return 20
    elif level == "WARNING":
        return 30
    elif level == "ERROR":
        return 40
    elif level == "FATAL":
        return 50
    else:
        return 0


class LogConverter:
    """Converter for parsing log files into MCAP log messages.

    Parses log files using regex patterns defined in a Jinja2 template format.
    Handles multi-line log entries by detecting log entry starts.

    Attributes:
        log_path: Path to the log file to parse
        name: Name identifier for the log source (default: "Log")
        datetime_format: Format of the timestamp in the log file (default: "%Y-%m-%d %H:%M:%S")
        zero_first_timestamp: If True, the first timestamp will be 0
    """

    log_path: Path
    name: str = "Log"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    zero_first_timestamp: bool = True
    _log_parser: re.Pattern | None = None
    _first_timestamp: float | None = None

    def __init__(
        self,
        log_path: Path,
        format_template: str,
        writer_format: WRITER_FORMATS,
        zero_first_timestamp: bool = False,
        name: str = "Log",
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
    ):
        """Initialize log converter.

        Args:
            log_path: Path to the log file to parse
            format_template: Jinja2 template string for regex pattern. Uses variables:
                levelname, message, asctime (default format: 'YYYY-MM-DD HH:MM:SS'), filename, lineno
            writer_format: Writer format to use for the log messages
            zero_first_timestamp: If True, the first timestamp will be 0
            name: Name identifier for the log source
            datetime_format: Format of the timestamp in the log file (default: "%Y-%m-%d %H:%M:%S")
        """
        self.log_path = log_path
        self.name = name
        self.datetime_format = datetime_format
        self.zero_first_timestamp = zero_first_timestamp

        template = Template(format_template)
        regex_str = template.render(
            levelname=r"(?P<levelname>INFO|DEBUG|WARNING|ERROR|FATAL|TRACE|WARN)",
            message=r"(?P<message>.*)",
            asctime=r"(?P<asctime>.*)",
            filename=r"(?P<filename>.*)",
            lineno=r"(?P<lineno>\d+)",  # Use raw string to avoid escape sequence warning
        )
        # Use re.DOTALL so .* matches newlines (for multi-line log entries)
        self._log_parser = re.compile(regex_str, re.DOTALL)

        if writer_format == "json":
            # rcl_interfaces/Log format
            def convert_msg_to_data(gd: dict, timestamp: float) -> dict:
                return {
                    "timestamp": {
                        "sec": int(timestamp),
                        "nsec": int((timestamp % 1) * 1_000_000_000),
                    },
                    "level": to_foxglove_log_level(gd.get("levelname", "")),
                    "message": gd.get("message", ""),
                    "name": self.name,
                    "file": gd.get("filename", ""),
                    "line": int(gd.get("lineno", 0)),
                }

        elif writer_format == "ros2":

            def convert_msg_to_data(gd: dict, timestamp: float) -> dict:
                return {
                    "stamp": {
                        "sec": int(timestamp),
                        "nanosec": int((timestamp % 1) * 1_000_000_000),
                    },
                    "level": to_ros2_log_level(gd.get("levelname", "")),
                    "msg": gd.get("message", ""),
                    "name": self.name,
                    "file": gd.get("filename", ""),
                    "line": int(gd.get("lineno", 0)),
                }

        else:
            raise ValueError(f"Unsupported writer format: {writer_format}")
        self._convert_msg_to_data = convert_msg_to_data

    def _parse_and_get_timestamp(self, line: str) -> tuple[dict, float]:
        """Parse a log line and return the timestamp and dictionary of groups."""
        match = self._log_parser.match(line)
        if match:
            gd = match.groupdict()
            # Parse timestamp: 'YYYY-MM-DD HH:MM:SS' to epoch time
            try:
                dt = datetime.strptime(gd["asctime"], self.datetime_format)
                timestamp = dt.timestamp()
                if self.zero_first_timestamp:
                    if self._first_timestamp is None:
                        self._first_timestamp = timestamp
                    timestamp -= self._first_timestamp
                return gd, timestamp
            except (ValueError, KeyError):
                return {}, 0
        return {}, 0

    def _convert_log_to_msg(self, line: str) -> ConvertedRow | None:
        """Convert a log line into a ConvertedRow object."""
        match = self._log_parser.match(line)
        if match:
            gd = match.groupdict()
            # Parse timestamp: 'YYYY-MM-DD HH:MM:SS' to epoch time
            try:
                dt = datetime.strptime(gd["asctime"], self.datetime_format)
                timestamp = dt.timestamp()
                if self.zero_first_timestamp:
                    if self._first_timestamp is None:
                        self._first_timestamp = timestamp
                    timestamp -= self._first_timestamp
            except (ValueError, KeyError):
                timestamp = 0

            return ConvertedRow(
                data=self._convert_msg_to_data(gd, timestamp),
                log_time_ns=int(timestamp * 1_000_000_000),
                publish_time_ns=int(timestamp * 1_000_000_000),
            )
        return None

    def log_iter(self) -> Iterable[ConvertedRow]:
        """Generate log messages from log data.

        Parses log file entries and yields ConvertedRow objects containing
        foxglove.Log format messages. Handles multi-line log entries.

        Yields:
            ConvertedRow with log message data in foxglove.Log format.
            Each entry contains timestamp (epoch time), level, message, file, and line.
        """

        with open(self.log_path) as log_file:
            current_entry = []
            while True:
                line = log_file.readline()
                if not line:
                    break

                match = self._log_parser.match(line)
                if match:
                    # Yield previous entry if exists
                    if current_entry:
                        result = self._convert_log_to_msg("".join(current_entry))
                        if result:
                            yield result
                    current_entry = [line]
                else:
                    current_entry.append(line)
            # Yield last entry
            if current_entry:
                result = self._convert_log_to_msg("".join(current_entry))
                if result:
                    yield result
