# Tutorial: Adding Support for New CSV Data Types

This tutorial walks you through the process of creating the config and converter files to support new types of CSV data.

The `converter_functions.yaml` is first created to reflect the column headings of the target CSV file, then the `config.yaml` file is created to the data in the target CSV to the convert functions in `converter_functions.yaml`.



## Step 1: Analyze Your CSV Data

The first step is to examine your CSV file structure to understand the data format:

```bash
# Look at the first few rows and data types
python -c "import pandas as pd; df = pd.read_csv('your_data.csv'); print(df.dtypes); print(df.head())"
```

## Step 2: Create Converter Functions

Create a `converter_functions.yaml` file with Jinja2 templates.

The strings `sensor_columnX` should be drawn from the column names found from Step 1, and `sensorX` is the label that the data will have in the final MCAP file.
It may be necessary to cast your data to an `int` or `float` which can be done with `| int ` and `| float` respectively.

```yaml
# converter_functions.yaml
functions:
  sensor_data_to_foxglove:
    description: "Convert sensor readings to Foxglove format"
    template: |
      {
        "timestamp": {{ timestamp | int }},
        "frame_id": "{{ frame_id | default('sensor') }}",
        "sensor1": {{ sensor_column1 }}
        "sensor2": {{ sensor_column2 }}
      }

  gps_to_location_fix:
    description: "Convert GPS coordinates to Foxglove LocationFix"
    template: |
      {
        "timestamp": {{ timestamp | int }},
        "frame_id": "{{ frame_id | default('gps') }}",
        "latitude": {{ latitude | float }},
        "longitude": {{ longitude | float }},
        "altitude": {{ altitude | float | default(0) }},
        "position_covariance": [0,0,0,0,0,0,0,0,0],
        "position_covariance_type": 0
      }
```

## Step 3: Create Configuration File

Now the converter functions have been established in Step 2, the data in the target CSV must be mapped to those functions.
This is done by creating a `config.yaml` file as shown below:

```yaml
# config.yaml
writer_format: "json"

tabular_mappings:
  - file_pattern: "sensor_*.csv"
    converter_functions:
      - function_name: "sensor_data_to_foxglove"
        schema_name: "foxglove.RawMessage"
        topic_suffix: "SensorData"
        exclude_columns: ["unused_column"]

  - file_pattern: "gps_*.csv"
    converter_functions:
      - function_name: "gps_to_location_fix"
        schema_name: "foxglove.LocationFix"
        topic_suffix: "LocationFix"

# Optional: Add attachments and metadata
attachments:
  - file_pattern: "*.jpg"
    mime_type: "image/jpeg"
  - file_pattern: "*.mp4"
    mime_type: "video/mp4"

metadata:
  - file_pattern: "config.txt"
    separator: "="
```

## Step 4: (Optimal) Advanced Jinja2 Templates

Use Jinja2's templating features for complex data transformations:

```yaml
functions:
  advanced_sensor_conversion:
    template: |
      {
        "timestamp": {{ timestamp | int }},
        "frame_id": "{{ frame_id | default('sensor') }}",
        {% if row.temperature is defined %}
        "temperature": {{ row.temperature | float }},
        {% endif %}
        "status": "{{ 'healthy' if row.error_code == 0 else 'error' }}",
        {% if row.raw_data is defined %}
        "raw_data": {{ row.raw_data | from_json | default([]) }},
        {% endif %}
        "metadata": {
          {% for key, value in row.items() %}
          {% if key.startswith('meta_') %}
          "{{ key[5:] }}": {{ value | tojson }}{% if not loop.last %},{% endif %}
          {% endif %}
          {% endfor %}
        }
      }
```

## Step 5: Run the Conversion
The conversion can now be executed using your custom configuration yaml files:

```bash
# Basic conversion
uv run tabular2mcap -i /path/to/your/data -o output.mcap -c config.yaml -f converter_functions.yaml

# With topic prefix and test mode
uv run tabular2mcap -i /path/to/your/data -o output.mcap -c config.yaml -f converter_functions.yaml -t "my_robot/" --test-mode
```

## Step 6: Validate Output

Foxglove is a capable tool to validate the conversion output is correct.

First, [download and install Foxglove Studio](https://foxglove.dev/download).
Then, using the below command, open the generated MCAP file in Foxglove Studio to validate your data conversion:

```bash
foxglove-studio output.mcap
```

## Troubleshooting

1. **Column name issues**: The tool automatically sanitizes column names by replacing spaces with `_` and removing special characters
2. **Data type conversion**: Use Jinja2 filters like `| float`, `| int`, `| tojson` for proper type conversion
3. **Missing data**: Use `| default()` filter to handle missing values
