# Tabular2MCAP

Convert tabular CSV data to MCAP format with native support for ROS2 and JSON schemas.

Tabular2MCAP is a powerful tool that converts tabular data (CSV files) into MCAP format, enabling seamless integration with robotics workflows, data visualization in Foxglove Studio, and playback of sensor and navigation data.

## Features

- **Multi-Format Support**: Convert to ROS2 or JSON messages
- **ROS2 Message Support**: Native support for standard ROS2 message types including sensor_msgs/NavSatFix, geometry_msgs/TransformStamped, and more
- **Configuration-Driven**: YAML-based mapping system for flexible data conversion using Jinja2 templates
- **Foxglove Integration**: Native support for LocationFix, FrameTransform, and other Foxglove schemas
- **Batch Processing**: Process multiple data directories with a single command

## Quick Start

### Installation

Following the below steps to install the Tabular2MCAP converter.

```bash
# Clone repository
git clone <repository-url>
cd tabular2mcap

# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### Basic Usage

Run the below command in terminal to generate an MCAP file. Make sure to be in the `tabular2mcap` directory and not a sub-folder.

```bash
# Convert CSV files to MCAP with configuration
uv run tabular2mcap \
  -i /path/to/csv/files \
  -o output.mcap \
  -c config.yaml \
  -f converter_functions.yaml
```

## Configuration System

The tool uses YAML configuration files to define how CSV files should be processed. These are:

- **`config.yaml`**: Defines file patterns and converter function mappings
- **`converter_functions.yaml`**: Contains Jinja2 templates for data transformation

### Example Configurations

**JSON Format:**
```yaml
# config.yaml
writer_format: "json"
file_mappings:
  - file_pattern: 'data.csv'
    converter_functions:
      - function_name: "row_to_foxglove_location_fix"
        schema_name: "foxglove.LocationFix"
        topic_suffix: "LocationFix"
```

**ROS2 Format:**
```yaml
# config.yaml
writer_format: "ros2"
tabular_mappings:
  - file_pattern: '**/data.csv'
    converter_functions:
      - function_name: "row_to_nav_sat_fix"
        schema_name: "sensor_msgs/msg/NavSatFix"
        topic_suffix: "NavSatFix"
```


## Tutorial

For detailed instructions on adding support for new types of CSV data, see [TUTORIAL.md](TUTORIAL.md).

# Development

## Foxglove Schema Setup

Foxglove schemas have been already downloaded from the official foxglove-sdk repository.
To update schemas to the latest version, run:
```bash
cd tabular2mcap/external
uv run python update_foxglove_schema.py
```

This script downloads the latest JSON schema files directly from GitHub.

## Roadmap

- [x] Schema mapping configuration files
- [x] Jinja2 template system for data transformation
- [x] ROS2 message support
- [ ] ROS1 message support
- [ ] Protobuf schema support

## License

Proprietary
