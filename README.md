# Tabular2MCAP

[![Documentation](https://img.shields.io/badge/docs-mkdocs-2d62ff?style=flat&labelColor=f8f9fa&color=2d62ff)](https://alloyrobotics.github.io/tabular2mcap/)
[![Supported by Alloy](https://img.shields.io/badge/Supported%20by-Alloy-2d62ff?style=flat&labelColor=f8f9fa&color=2d62ff)](https://usealloy.ai)

Convert tabular data (CSV, Parquet, Excel, and more) to MCAP format with support for ROS2 and JSON schemas, enabling seamless integration with robotics workflows, data visualization in Foxglove Studio, and playback of sensor and navigation data.

> **Please ⭐ if this helps you today!**

## Features

- **Multi-Format Support**: Convert to ROS2 or JSON messages with support for standard message types (e.g., `sensor_msgs/msg/NavSatFix`, `geometry_msgs/msg/TransformStamped`, `foxglove.LocationFix`, and more)
- **Configuration-Driven**: YAML-based mapping with Jinja2 templates for flexible data transformation
- **Batch Processing**: Process multiple files and directories with a single command

## Quick Start

### Installation

```bash
# Basic installation (CSV, TSV, JSON, Pickle)
pip install tabular2mcap

# With optional formats
pip install tabular2mcap[parquet]      # Parquet files
pip install tabular2mcap[feather]      # Feather files
pip install tabular2mcap[orc]          # ORC files
pip install tabular2mcap[excel]        # Excel files (.xlsx)
pip install tabular2mcap[excel-legacy] # Excel files (.xls)
pip install tabular2mcap[xml]          # XML files
pip install tabular2mcap[all-formats]  # All formats
```

### Basic Usage

```bash
tabular2mcap \
  -i /path/to/data/directory \
  -o output.mcap \
  -c config.yaml \
  -f converter_functions.yaml
```

### Configuration System

The tool uses YAML configuration files to define how CSV files should be processed. These are:

- **`config.yaml`**: Defines file patterns and converter function mappings
- **`converter_functions.yaml`**: Contains Jinja2 templates for data transformation

#### Example Configurations

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

For detailed instructions on adding support for new types of CSV data, see the [Tutorial](https://alloyrobotics.github.io/tabular2mcap/tutorial/) in the documentation.

## Supported By

<a href="https://usealloy.ai" target="_blank">
  <img src="https://cdn.prod.website-files.com/68c02115d6be7142be8a1553/68e70108f9c8d1c5629ce407_logo-padding-256px.png" alt="Alloy" style="background-color: white; padding: 0px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); height: 56px" />
</a>

This project is supported by [Alloy](https://usealloy.ai) - Search all your robot data in plain english. Alloy provides a platform to unify image, time-series, and log search for robotics teams.

## License

GNU General Public License v3.0 - see [LICENSE](https://github.com/alloyrobotics/tabular2mcap/blob/main/LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.
