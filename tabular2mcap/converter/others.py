from collections.abc import Iterable

import numpy as np


def compressed_image_message_iterator(
    video_frames: list[np.ndarray], fps: float, format: str, frame_id: str
) -> Iterable[dict]:
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
        yield {
            "timestamp": {
                "sec": int(frame_timestamp),
                "nsec": int((frame_timestamp % 1) * 1_000_000_000),
            },
            "frame_id": frame_id,
            "data": encoded_img.tobytes(),  # base64.b64encode(encoded_img.tobytes()).decode("utf-8"),
            "format": format,
        }


def compressed_video_message_iterator(
    video_frames: list[np.ndarray], fps: float, format: str, frame_id: str
) -> Iterable[dict]:
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
            yield {
                "timestamp": {
                    "sec": int(frame_timestamp),
                    "nsec": int((frame_timestamp % 1) * 1_000_000_000),
                },
                "frame_id": frame_id,
                "data": bytes(
                    packet
                ),  # base64.b64encode(bytes(packet)).decode("utf-8"),
                "format": format,
            }
            frame_timestamp += frame_timestamp_step

    packets = codec.encode(None)
    for packet in packets:
        yield {
            "timestamp": {
                "sec": int(frame_timestamp),
                "nsec": int((frame_timestamp % 1) * 1_000_000_000),
            },
            "frame_id": frame_id,
            "data": bytes(packet),  # base64.b64encode(bytes(packet)).decode("utf-8"),
            "format": format,
        }
        frame_timestamp += frame_timestamp_step
