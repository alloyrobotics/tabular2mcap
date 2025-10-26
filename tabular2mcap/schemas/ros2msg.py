import logging
import re
from pathlib import Path

import platformdirs
from mcap_ros2._vendor.rosidl_adapter import parser as ros2_parser

logger = logging.getLogger(__name__)

CACHE_DIR = platformdirs.user_cache_path(
    appname="tabular2mcap_schemas", ensure_exists=True
)


def _get_dep_types(pkg_name: str, msg_name: str, msg_txt: str) -> list[str]:
    dep_types = []
    msg_def = ros2_parser.parse_message_string(pkg_name, msg_name, msg_txt)
    for field in msg_def.fields:
        f_type = field.type
        if field.type.is_primitive_type():
            continue

        # builtin_interfaces are expected to be known by the parser
        if f_type.pkg_name == "builtin_interfaces":
            continue

        dep_types.append(f"{f_type.pkg_name}/{f_type.type}")
    return dep_types


def _get_msg_def(
    msg_type: str, distro: str = "jazzy", folder: Path | None = None
) -> tuple[str, list[str]]:
    if folder is None:
        folder = CACHE_DIR
    target_path = folder / distro

    # Parse msg_type with regex: pkg_name/msg_name or pkg_name/msg/msg_name
    # First / is pkg_name, second / is msg_name with optional '/msg/' in between
    match = re.match(r"^([^/]+)/(?:msg/)?([^/]+)$", msg_type)
    if not match:
        logger.error(f"Invalid message type format: {msg_type}")
        return None, []

    pkg_name, msg_name = match.groups()
    if pkg_name == "foxglove_msgs":
        search_str = f"**/foxglove-sdk/**/ros2/{msg_name}.msg"
    else:
        search_str = f"**/{pkg_name}/msg/{msg_name}.msg"
    msg_txt = None
    for file in target_path.glob(search_str):
        with open(file) as f:
            msg_txt = f.read()
        break

    # Extract data types from msg_txt
    if msg_txt:
        dep_types = _get_dep_types(pkg_name, msg_name, msg_txt)
        return msg_txt, dep_types
    else:
        raise TypeError(f"Couldn't find {pkg_name}/{msg_name}")


def get_schema_definition(
    msg_type: str,
    distro: str = "jazzy",
    folder: Path | None = None,
    custom_msg_txt: str | None = None,
) -> str | None:
    if custom_msg_txt is None:
        msg_txt, dep_types = _get_msg_def(msg_type, distro, folder)
    else:
        msg_txt = custom_msg_txt
        dep_types = _get_dep_types("custom", "Custom", msg_txt)
    defined_types = {msg_type}
    while len(dep_types) > 0:
        cur_type = dep_types.pop(0)
        msg_txt += "=" * 80 + "\n"
        msg_txt += f"MSG: {cur_type}\n"
        cur_msg_txt, cur_dep_types = _get_msg_def(cur_type, distro, folder)
        msg_txt += cur_msg_txt
        dep_types.extend(set(cur_dep_types) - defined_types)

    return msg_txt
