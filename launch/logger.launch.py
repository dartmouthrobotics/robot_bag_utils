"""Logger launch supporting standalone and composable recorder modes."""

from datetime import datetime

import os
import yaml

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, GroupAction, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import LoadComposableNodes
from launch_ros.descriptions import ComposableNode
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    use_composable_arg = DeclareLaunchArgument(
        "use_composable",
        default_value="false",
        description="Use composable rosbag recorder in a component container",
    )

    container_name_arg = DeclareLaunchArgument(
        "container_name",
        default_value="shared_container",
        description="Composable container name used when use_composable:=true",
    )

    bag_dir_arg = DeclareLaunchArgument(
        "bag_dir",
        default_value="/home/catabot-5/datalog/rosbag2/",
        description="Root directory where ros2 bag folders are saved",
    )

    bag_name_arg = DeclareLaunchArgument(
        "bag_name",
        default_value=f"catabot_{datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
        description="Bag folder name",
    )

    use_composable = LaunchConfiguration("use_composable")
    container_name = LaunchConfiguration("container_name")
    bag_dir = LaunchConfiguration("bag_dir")
    bag_name = LaunchConfiguration("bag_name")
    bag_prefix = PathJoinSubstitution([bag_dir, bag_name])

    # Load topics from config file
    param_file = os.path.join(
        get_package_share_directory('catabot_bringup'),
        'param/recorder_topics.yaml',
    )
    with open(param_file, 'r') as f:
        recorder_config = yaml.safe_load(f)
    topics = recorder_config['topics']

    # In composable mode, ZED streams are recorded by per-camera loggers.
    composable_topics = [topic for topic in topics if "/zed/" not in topic]

    standalone_record_cmd = ExecuteProcess(
        condition=UnlessCondition(use_composable),
        cmd=[
            "ros2", "bag", "record",
            "--output", bag_prefix,
            "-s", "mcap",
            "--max-cache-size", "104857600",
    #        "--compression-mode", "file",
    #        "--compression-format", "zstd",
        ] + topics,
        output="screen",
        # Increase the time before escalating to SIGTERM (e.g., 30 seconds)
        sigterm_timeout='30.0',
        # Increase the time before escalating to SIGKILL after SIGTERM
        sigkill_timeout='30.0'
    )

    composable_record_cmd = GroupAction(
        condition=IfCondition(use_composable),
        actions=[
            LoadComposableNodes(
            target_container=container_name,
            composable_node_descriptions=[
                ComposableNode(
                    package='rosbag2_composable_recorder',
                    plugin='rosbag2_composable_recorder::ComposableRecorder',
                    name='recorder_node',
                    parameters=[{
                        'bag_name': bag_prefix,
                        'storage_id': 'mcap',
                        'max_cache_size': 104857600,
                        'record_all': False,
                        'serialization_format': 'cdr',
                        'start_recording_immediately': True,
                        'topics': composable_topics,
                        'disable_discovery': False,
                    }],
                    remappings=[],
                    extra_arguments=[{'use_intra_process_comms': True}],
                ),
            ],
        )
        ]
    )

    return LaunchDescription([
        use_composable_arg,
        container_name_arg,
        bag_dir_arg,
        bag_name_arg,
        standalone_record_cmd,
        composable_record_cmd,
    ])
