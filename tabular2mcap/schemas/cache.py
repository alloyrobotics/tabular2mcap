#!/usr/bin/env python3
"""
Script to download and cache ROS 2 message definitions from official repositories.

This script downloads the following repositories for a specified ROS 2 distribution:
- rcl_interfaces
- common_interfaces
- geometry2

The downloaded files are cached in the user's cache directory to avoid re-downloading.
"""

import logging
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import platformdirs

logger = logging.getLogger(__name__)

# Cache directory for storing downloaded definitions
CACHE_DIR = platformdirs.user_cache_path(
    appname="tabular2mcap_schemas", ensure_exists=True
)

# Repository definitions
REPOSITORIES = [
    (
        "rcl_interfaces",
        "https://github.com/ros2/rcl_interfaces/archive/refs/heads/{distro_str}.zip",
    ),
    (
        "common_interfaces",
        "https://github.com/ros2/common_interfaces/archive/refs/heads/{distro_str}.zip",
    ),
    (
        "geometry2",
        "https://github.com/ros2/geometry2/archive/refs/heads/{distro_str}.zip",
    ),
    (
        "foxglove-sdk",
        "https://github.com/foxglove/foxglove-sdk/archive/refs/tags/sdk/v0.14.3.zip",
    ),
]


def download_file(url: str, destination: Path) -> bool:
    """
    Download a file from URL to destination path.

    Args:
        url: URL to download from
        destination: Local path to save the file

    Returns:
        True if download successful, False otherwise
    """
    try:
        logger.info(f"Downloading {url} to {destination}")
        urllib.request.urlretrieve(url, destination)
        logger.info(f"Successfully downloaded {destination.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def extract_zip(zip_path: Path, extract_to: Path) -> bool:
    """
    Extract a zip file to the specified directory.

    Args:
        zip_path: Path to the zip file
        extract_to: Directory to extract to

    Returns:
        True if extraction successful, False otherwise
    """
    try:
        logger.info(f"Extracting {zip_path} to {extract_to}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_to)
        logger.info(f"Successfully extracted to {extract_to}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract {zip_path}: {e}")
        return False


def is_repository_cached(repo_name: str, distro: str, cache_dir: Path) -> bool:
    """
    Check if a repository is already cached for the given distribution.

    Args:
        repo_name: Name of the repository
        distro: ROS 2 distribution name
        cache_dir: Cache directory path

    Returns:
        True if repository is cached, False otherwise
    """
    distro_dir = cache_dir / distro
    repo_dir = distro_dir / repo_name

    # Check if the repository directory exists and contains msg files
    if repo_dir.exists() and repo_dir.is_dir():
        msg_files = list(repo_dir.glob("**/*.msg"))
        if msg_files:
            logger.debug(
                f"Repository {repo_name} for {distro} is already cached ({len(msg_files)} msg files)"
            )
            return True

    return False


def download_and_cache_repository(
    repo_name: str, url: str, distro: str, cache_dir: Path
) -> bool:
    """
    Download and cache a single repository.

    Args:
        repo_name: Name of the repository
        url: URL template for downloading (with {distro_str} placeholder)
        distro: ROS 2 distribution name
        cache_dir: Cache directory path

    Returns:
        True if successful, False otherwise
    """
    # Check if already cached
    if is_repository_cached(repo_name, distro, cache_dir):
        return True

    # Create distribution directory
    distro_dir = cache_dir / distro
    distro_dir.mkdir(parents=True, exist_ok=True)

    # Format URL with distribution
    download_url = url.format(distro_str=distro)

    # Download to temporary file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
        temp_zip_path = Path(temp_file.name)

    try:
        # Download the file
        if not download_file(download_url, temp_zip_path):
            return False

        # Extract to temporary directory first
        with tempfile.TemporaryDirectory() as temp_extract_dir:
            temp_extract_path = Path(temp_extract_dir)

            if not extract_zip(temp_zip_path, temp_extract_path):
                return False

            # Find the extracted repository directory (it will have a name like repo_name-distro)
            extracted_dirs = [
                d
                for d in temp_extract_path.iterdir()
                if d.is_dir() and repo_name in d.name
            ]
            if not extracted_dirs:
                logger.error(f"Could not find extracted directory for {repo_name}")
                return False

            extracted_repo_dir = extracted_dirs[0]

            # Move to final cache location
            final_repo_dir = distro_dir / repo_name
            if final_repo_dir.exists():
                import shutil

                shutil.rmtree(final_repo_dir)

            import shutil

            shutil.move(str(extracted_repo_dir), str(final_repo_dir))

            logger.info(f"Successfully cached {repo_name} for {distro}")
            return True

    finally:
        # Clean up temporary zip file
        if temp_zip_path.exists():
            temp_zip_path.unlink()


def download_and_cache_all_repos(
    distro: str = "jazzy", cache_dir: Path | None = None
) -> bool:
    """
    Download and cache all ROS 2 message definition repositories.

    Args:
        distro: ROS 2 distribution name (default: "jazzy")
        cache_dir: Cache directory path (default: uses platformdirs cache)

    Returns:
        True if all repositories downloaded successfully, False otherwise
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR

    logger.debug(f"Downloading ROS 2 message definitions for distribution: {distro}")
    logger.debug(f"Cache directory: {cache_dir}")

    success_count = 0
    total_count = len(REPOSITORIES)

    for repo_name, url_template in REPOSITORIES:
        if download_and_cache_repository(repo_name, url_template, distro, cache_dir):
            success_count += 1
        else:
            logger.error(f"Failed to download {repo_name}")

    logger.debug(f"Downloaded {success_count}/{total_count} repositories successfully")
    return success_count == total_count


def list_cached_repositories(cache_dir: Path | None = None) -> None:
    """
    List all cached repositories and their message file counts.

    Args:
        cache_dir: Cache directory path (default: uses platformdirs cache)
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR

    logger.info(f"Cache directory: {cache_dir}")

    if not cache_dir.exists():
        logger.info("No cache directory found")
        return

    for distro_dir in sorted(cache_dir.iterdir()):
        if distro_dir.is_dir():
            logger.info(f"\nDistribution: {distro_dir.name}")
            for repo_dir in sorted(distro_dir.iterdir()):
                if repo_dir.is_dir():
                    msg_files = list(repo_dir.glob("**/*.msg"))
                    logger.info(f"  {repo_dir.name}: {len(msg_files)} message files")
