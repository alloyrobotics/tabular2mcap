# Tabular2MCAP

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://alloyrobotics.github.io/tabular2mcap/)

Convert tabular data (CSV, Parquet) to MCAP format with support for ROS2 and JSON schemas, enabling seamless integration with robotics workflows, data visualization in Foxglove Studio, and playback of sensor and navigation data.

## Features

- **Multi-Format Support**: Convert to ROS2 or JSON messages with support for standard message types (e.g., `sensor_msgs/msg/NavSatFix`, `geometry_msgs/msg/TransformStamped`, `foxglove.LocationFix`, and more)
- **Configuration-Driven**: YAML-based mapping with Jinja2 templates for flexible data transformation
- **Batch Processing**: Process multiple files and directories with a single command

## Quick Start

### Installation

```bash
pip install tabular2mcap
```

### Basic Usage

```bash
tabular2mcap \
  -i /path/to/csv/files \
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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.
