# Robot Bagging Utilities (`robot_bag_utils`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![ROS 2](https://img.shields.io/badge/ROS_2-Jazzy-34a853.svg)](#)
[![ROS 2 CI](https://github.com/dartmouthrobotics/robot_bag_utils/actions/workflows/ros2_ci.yml/badge.svg)](https://github.com/dartmouthrobotics/robot_bag_utils/actions/workflows/ros2_ci.yml)

A robust ROS 2 package designed for flexible, high-performance data logging in field robotics. It supports both **Standalone CLI** and **Composable Node** execution modes, modular **Base + Override YAML configurations**, and comprehensive integration testing via `launch_testing`.

---

## Features

* **Dual Execution Modes:** Seamlessly toggle between running as an isolated CLI process (`ros2 bag record`) or as a high-performance C++ Composable Node (`rosbag2_composable_recorder`) inside a component container.
* **Modular Base + Override Configuration:** Separate global logging parameters (compression, cache limits, chunk sizes) from domain-specific topic lists and QoS profile overrides.
* **Namespace & Regex Filtering:** Automatically handles node scoping, relative topic prefixing, and pattern-based topic exclusion.
* **Automated Launch Testing:** Integrated `launch_testing` scripts that validate process runtimes, exit codes, and catch YAML parsing or component-loading errors.

---

## Package Structure

```text
robot_bag_utils/
├── config/
│   ├── common_logger.yaml       # Global storage, cache, and chunk defaults
│   ├── mavros_topics.yaml       # Telemetry topic profile
│   └── zed_topics.yaml          # Multi-camera topic profile & QoS overrides
├── launch/
│   └── logger.launch.py         # Dynamic launch engine supporting CLI & Composable modes
├── test/
│   └── test_logger_launch.py    # Automated launch test suite
├── package.xml
└── setup.py
```

---

## Configuration Files (`config/`)

Configurations follow the standard ROS 2 `ros__parameters` syntax. The launch system loads `common_logger.yaml` first, then overlays the specified topic profile (`*_topics.yaml`).

### Example Base Profile (`common_logger.yaml`)

```yaml
/**:
  ros__parameters:
    storage_id: "mcap"
    max_cache_size: 104857600       # 100 MB RAM cache
    max_bag_size: 2147483648        # 2 GB split limit
    max_bag_duration: 1800          # 30-minute time split limit
    storage_preset_profile: "zstd_fast"
```

### Example Sensor Profile with QoS Overrides (`zed_topics.yaml`)

```yaml
/**:
  ros__parameters:
    regex_to_exclude: ".*(uncompressed|depth).*"
    topics:
      - "/zed1/zed_node/left/image_rect_color/compressed"
      - "/zed1/zed_node/right/image_rect_color/compressed"
      - "/tf"
      - "/tf_static"
    
    qos_profile_overrides:
      - topic: "/zed1/zed_node/left/image_rect_color/compressed"
        reliability: "best_effort"
```

---

## Usage & Launch Arguments

### Launch Arguments Table

| Argument | Default | Description |
| :--- | :--- | :--- |
| `base_config` | `common_logger.yaml` | Base YAML file containing global logger parameters. |
| `topic_config` | `mavros_topics.yaml` | Topic YAML file containing target streams and QoS rules. |
| `namespace` | `""` | Optional namespace for node scoping and relative topic mapping. |
| `storage_id` | `""` | Storage plugin override (`mcap`, `sqlite3`). Blank defaults to YAML config. |
| `root_bag_dir` | `~/datalog/rosbag2` | Root destination folder for mission logs. |
| `session_dir` | `session_YYYY-MM-DD` | Subfolder grouping multiple recording runs. |
| `bag_name` | `""` | Custom bag folder name (auto-generates a timestamped tag if empty). |
| `use_composable` | `false` | Set to `true` to run as a C++ component node inside a container. |
| `create_container` | `false` | Launches a new container if `true`, or attaches to an existing one if `false`. |
| `container_name` | `recorder_container` | Name of the component container. |

---

## Execution Examples

### 1. Standalone CLI Mode (Telemetry)

Runs `ros2 bag record` with the MAVROS topic profile:

```bash
ros2 launch robot_bag_utils logger.launch.py topic_config:=mavros_topics.yaml use_composable:=false
```

### 2. Composable Node Mode (High-Bandwidth Cameras)

Spins up a component container and loads the composable recorder with ZED camera configurations and Best-Effort QoS profiles:

```bash
ros2 launch robot_bag_utils logger.launch.py topic_config:=zed_topics.yaml use_composable:=true create_container:=true
```

### 3. Attaching Multiple Loggers to an Existing Container

You can run multiple independent recorders (e.g., Lidar and Telemetry) inside the same shared component container to optimize thread synchronization and system resources:

```bash
# Terminal 1: Create container and load Ouster logger
ros2 launch robot_bag_utils logger.launch.py topic_config:=ouster_topics.yaml use_composable:=true create_container:=true container_name:=robot_container

# Terminal 2: Attach MAVROS logger to the existing container
ros2 launch robot_bag_utils logger.launch.py topic_config:=mavros_topics.yaml use_composable:=true create_container:=false container_name:=robot_container
```

---

## Running Tests

To verify that both standalone processes and component containers spin up correctly, parse YAML configuration files without error, and shut down cleanly:

```bash
# Build package
colcon build --packages-select robot_bag_utils
source install/setup.bash

# Run tests via colcon
colcon test --packages-select robot_bag_utils --event-handlers console_direct+ --return-code-on-test-failure

# Alternatively, run via launch_test directly
launch_test src/robot_bag_utils/test/test_logger_launch.py
```

## License & Authors

Licensed under the MIT License. See [LICENSE](LICENSE). 
