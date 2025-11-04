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


## Troubleshooting

1. **Column name issues**: The tool automatically sanitizes column names by replacing spaces with `_` and removing special characters
2. **Data type conversion**: Use Jinja2 filters like `| float`, `| int`, `| tojson` for proper type conversion
3. **Missing data**: Use `<column_name> or 0` filter to handle missing values
