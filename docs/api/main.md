# Main API

High-level functions for converting tabular data to MCAP format.

## Architecture

The conversion process uses three main components:

1. **`loader`** - Loads data and configuration files
2. **`schemas`** - Manages and writes message schemas to MCAP
3. **`converter`** - Transforms data into the target message format (JSON or ROS2)


::: tabular2mcap.convert_tabular_to_mcap
    options:
      show_root_heading: true
      show_source: false

::: tabular2mcap.McapConverter
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - convert
