#!/usr/bin/env python3
"""
Update Foxglove schema files by downloading them directly from the Foxglove SDK repository.
This script downloads JSON schema files from the foxglove-sdk GitHub repository.
"""

import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_script_dir():
    """Get the directory where this script is located."""
    return Path(__file__).parent.absolute()


def download_file(url, output_path):
    """Download a file from URL to output path using urllib.request."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            # Check if response is successful (status code 200-299)
            if response.status >= 200 and response.status < 300:
                with open(output_path, "wb") as f:
                    f.write(response.read())
                return True
            else:
                logger.error(f"HTTP error {response.status}: {response.reason}")
                return False
    except urllib.error.URLError as e:
        logger.error(f"URL error: {e}")
        return False
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error {e.code}: {e.reason}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False


def get_schema_list():
    """Get the list of JSON schema files from the Foxglove SDK repository."""

    # GitHub API URL to get the contents of the schemas/jsonschema directory
    api_url = (
        "https://api.github.com/repos/foxglove/foxglove-sdk/contents/schemas/jsonschema"
    )

    try:
        with urllib.request.urlopen(api_url, timeout=30) as response:
            if response.status >= 200 and response.status < 300:
                data = response.read().decode("utf-8")
                return json.loads(data)
            else:
                logger.warning(
                    f"GitHub API returned status {response.status}: {response.reason}"
                )
    except urllib.error.URLError as e:
        logger.warning(f"URL error fetching schema list: {e}")
    except urllib.error.HTTPError as e:
        logger.warning(f"HTTP error {e.code} fetching schema list: {e.reason}")
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error fetching schema list: {e}")

    logger.warning("Using fallback list of common schema files")

    # Fallback: return a hardcoded list of common schema files
    return [
        {
            "name": "LocationFix.json",
            "download_url": "https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/LocationFix.json",
        },
        {
            "name": "FrameTransform.json",
            "download_url": "https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/FrameTransform.json",
        },
        {
            "name": "Timestamp.json",
            "download_url": "https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/Timestamp.json",
        },
        {
            "name": "PackedElementField.json",
            "download_url": "https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/PackedElementField.json",
        },
        {
            "name": "SceneUpdate.json",
            "download_url": "https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/SceneUpdate.json",
        },
    ]


def update_foxglove_schemas():
    """Update Foxglove schemas by downloading them from the GitHub repository."""

    # Get script directory
    script_dir = get_script_dir()

    # Define destination directory
    dest_dir = script_dir / "foxglove-sdk" / "schemas" / "jsonschema"

    # Create destination directory if it doesn't exist
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching schema list from Foxglove SDK repository...")

    # Get list of schema files
    schema_files = get_schema_list()

    if not schema_files:
        logger.error("Could not retrieve schema file list")
        return False

    logger.info(f"Found {len(schema_files)} schema files to download")
    logger.info(f"Downloading to: {dest_dir}")

    downloaded_count = 0
    failed_count = 0

    for schema_info in schema_files:
        schema_name = schema_info["name"]
        download_url = schema_info.get(
            "download_url",
            f"https://raw.githubusercontent.com/foxglove/foxglove-sdk/main/schemas/jsonschema/{schema_name}",
        )

        dest_file = dest_dir / schema_name

        logger.info(f"Downloading: {schema_name}")

        try:
            if download_file(download_url, dest_file):
                logger.info(f"✅ Downloaded: {schema_name}")
                downloaded_count += 1
            else:
                logger.error(f"❌ Failed to download: {schema_name}")
                failed_count += 1
        except Exception as e:
            logger.error(f"❌ Error downloading {schema_name}: {e}")
            failed_count += 1

    logger.info(
        f"Download complete: {downloaded_count} successful, {failed_count} failed"
    )

    if downloaded_count > 0:
        return True
    else:
        logger.error("❌ No schemas were downloaded")
        return False


def main():
    """Main function."""
    logger.info("🔄 Updating Foxglove schemas from GitHub repository...")

    try:
        success = update_foxglove_schemas()
        if success:
            logger.info("✅ Schema update completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Schema update failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
