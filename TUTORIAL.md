# Tutorial: Setting up the config to convert CSV to MCAP

Learn how to create configuration files that convert your CSV data to MCAP format.

> **Example**: See a complete working example in the [alloy dataset folder](https://github.com/alloyrobotics/tabular2mcap/tree/main/tests/data/alloy) which includes sample CSV files, config files, and converter functions for both JSON and ROS2 formats.

## Step 1: Analyze Your CSV Data

Suppose you have data from a wheeled robot with GPS, sensor readings, and camera:

```
data/
├── location.csv        # contains headers timestamp_sec, latitude, longitude, altitude, latitude_error, longitude_error, altitude_error
├── sensor.csv          # contains headers timestamp_sec, pressure1, pressure2, sensor3, sensor4
├── video.mp4
├── attachment1.txt
└── attachment2.txt
```



## Step 2: Create Configuration File

Map your CSV files to MCAP topics and message types using `config.yaml`:

```yaml
# config.yaml
writer_format: "ros2"

tabular_mappings:
  - file_pattern: "location.csv"
    converter_functions:
      - function_name: "row_to_location_fix"
        schema_name: "sensor_msgs/msg/NavSatFix"
        topic_suffix: "LocationFix"

  - file_pattern: "sensor.csv"
    converter_functions:
      - function_name: "row_to_timestamp"
        schema_name: null
        topic_suffix: "Data"
        exclude_columns:
        # Exclude timestamp_sec; all other columns (pressure1, pressure2, sensor3, sensor4) are included
        - "timestamp_sec"

# Optional: Add attachments and metadata
attachments:
  - file_pattern: "attachment*.txt"
    exclude_file_pattern: '(attachment2).txt'  # Excludes attachment2.txt, attaches only attachment1.txt

metadata:
  - file_pattern: "attachment2.txt"
    separator: ":"
```

## Step 3: Create Converter Functions

Auto-generate `converter_functions.yaml` from your `config.yaml`:

```bash
tabular2mcap gen -i /path/to/data/directory -c config.yaml -f converter_functions.yaml
```

This generates template converter functions with empty Jinja2 templates. Edit the generated file to fill in your transformation logic using `| int` and `| float` filters for type conversion.

```yaml
# converter_functions.yaml (auto-generated, then customized)
functions:
  row_to_location_fix:
    description: "Convert GPS coordinates to ROS2 NavSatFix"
    template: |
      {
        "header": {
          "stamp": {
            "sec": {{ timestamp_sec | int }},
            "nanosec": {{ ((timestamp_sec % 1) * 1_000_000_000) | int }}
          },
          "frame_id": "gps"
        },
        "status": {
          "status": 0,
          "service": 1
        },
        "latitude": {{ latitude | float }},
        "longitude": {{ longitude | float }},
        "altitude": {{ altitude | float }},
        "position_covariance": [
          {{ (latitude_error or 0) ** 2 }},
          0, 0,
          0,
          {{ (longitude_error or 0) ** 2 }},
          0,
          0, 0,
          {{ (altitude_error or 0) ** 2 }}
        ],
        "position_covariance_type": 2
      }

  row_to_timestamp:
    description: "Convert timestamp"
    template: "{}"
    log_time_template: "{{ (timestamp_sec * 1_000_000_000) | int }}"
    publish_time_template: "{{ (timestamp_sec * 1_000_000_000) | int }}"

```

## Step 4: Run the Conversion

```bash
# Basic conversion
tabular2mcap -i /path/to/data/directory -o output.mcap -c config.yaml -f converter_functions.yaml

# With topic prefix and test mode
tabular2mcap -i /path/to/data/directory -o output.mcap -c config.yaml -f converter_functions.yaml -t "my_robot/" --test-mode
```

## Step 5: Validate Output

Open your generated MCAP file in [Foxglove Studio](https://foxglove.dev/download) to verify the conversion.

## Step 6: Bonus - Add 3D Transform for GPS Visualization

You can add multiple converter functions for the same CSV file to create different message types. For example, you can generate a 3D transform from GPS coordinates to visualize the robot's position with altitude on a map in Foxglove Studio.

### Update config.yaml

Add a second converter function to the `location.csv` mapping:

```yaml
tabular_mappings:
  - file_pattern: "location.csv"
    converter_functions:
      - function_name: "row_to_location_fix"
        schema_name: "sensor_msgs/msg/NavSatFix"
        topic_suffix: "LocationFix"
      - function_name: "row_to_transform"
        schema_name: "geometry_msgs/msg/TransformStamped"
        topic_suffix: "Transform"
```

### Add to converter_functions.yaml

Add the transform converter function:

```yaml
functions:
  # ... existing functions ...

  row_to_transform:
    available_columns:
    - 'location.csv: timestamp_sec, latitude, longitude, altitude, latitude_error, longitude_error, altitude_error'
    log_time_template: '{{ (timestamp_sec * 1_000_000_000) | int }}'
    publish_time_template: null
    schema_name: geometry_msgs/msg/TransformStamped
    template: |-
      {
        "header": {
          "stamp": {
            "sec": {{ (timestamp_sec) | int }},
            "nanosec": {{ ((timestamp_sec % 1) * 1_000_000_000) | int }}
          },
          "frame_id": "world"
        },
        "child_frame_id": "gps",
        "transform": {
          "translation": {{ latlon_to_utm(latitude, longitude, altitude) | safe }},
          "rotation": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "w": 1.0
          }
        }
      }
```

This creates a transform from the `world` frame to the `gps` frame, converting GPS coordinates to UTM coordinates for 3D visualization. In Foxglove Studio, you can view the robot's path with elevation using the 3D view panel with a map overlay.

## Troubleshooting

1. **Missing data**: Use `<column_name> or 0` filter to handle missing values in your converter function templates
