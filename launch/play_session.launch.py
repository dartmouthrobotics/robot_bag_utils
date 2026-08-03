"""Launch file to dynamically synchronize and play multiple ROS 2 Humble bags."""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
import yaml


def launch_setup(context, *args, **kwargs):
    raw_root_dir = LaunchConfiguration('root_bag_dir').perform(context)
    session_dir = LaunchConfiguration('session_dir').perform(context)
    rate_str = LaunchConfiguration('rate').perform(context)
    publish_clock = LaunchConfiguration('clock').perform(context)

    rate = float(rate_str)
    root_bag_dir = os.path.expanduser(raw_root_dir)
    session_path = os.path.join(root_bag_dir, session_dir)

    if not os.path.exists(session_path):
        raise FileNotFoundError(f'Session directory not found: {session_path}')

    # 1. Scan for bags and parse their starting times
    bag_data = []
    for item in os.listdir(session_path):
        item_path = os.path.join(session_path, item)
        meta_path = os.path.join(item_path, 'metadata.yaml')

        if os.path.isdir(item_path) and os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                try:
                    meta = yaml.safe_load(f)
                    info = meta['rosbag2_bagfile_information']
                    start_ns = info['starting_time']['nanoseconds_since_epoch']
                    bag_data.append({'path': item_path, 'start_ns': start_ns})
                except Exception as e:
                    raise RuntimeError(f'Failed to parse start time from {meta_path}: {e}')

    if not bag_data:
        raise RuntimeError(f'No valid ROS 2 bags found in: {session_path}')

    # 2. Find the absolute oldest bag to act as t=0
    min_start_ns = min(b['start_ns'] for b in bag_data)

    processes = []

    # 3. Spawn a process for each bag with a mathematically calculated delay
    for bag in bag_data:
        cmd_args = ['ros2', 'bag', 'play', bag['path'], '--rate', rate_str]

        # Calculate the delay in seconds, adjusted for the playback rate
        delay_sec = ((bag['start_ns'] - min_start_ns) / 1e9) / rate
        is_oldest = (bag['start_ns'] == min_start_ns)

        # ONLY the oldest bag is allowed to publish to /clock
        if is_oldest and publish_clock.lower() in ['true', 't', '1', 'yes']:
            cmd_args.append('--clock')

        proc = ExecuteProcess(
            cmd=cmd_args,
            output='screen',
            name=f"bag_play_{os.path.basename(bag['path'])}",
            sigterm_timeout='5.0',
            sigkill_timeout='5.0'
        )

        # If this bag started later than the oldest bag, delay its launch
        if delay_sec > 0.01:
            processes.append(
                TimerAction(
                    period=delay_sec,
                    actions=[proc]
                )
            )
        else:
            processes.append(proc)

    return processes


def generate_launch_description():
    default_root = os.path.join(os.path.expanduser('~'), 'datalog', 'rosbag2')

    return LaunchDescription([
        DeclareLaunchArgument(
            'root_bag_dir',
            default_value=default_root,
            description='Root base directory where all mission sessions are stored',
        ),
        DeclareLaunchArgument(
            'session_dir',
            description='Name of the session subfolder (e.g., session_2026-08-02)'
        ),
        DeclareLaunchArgument(
            'rate',
            default_value='1.0',
            description='Multiplier for the playback rate',
        ),
        DeclareLaunchArgument(
            'clock',
            default_value='true',
            description='Publish to the /clock topic during playback',
        ),
        OpaqueFunction(function=launch_setup),
    ])
