"""Logger launch supporting session storage, namespaces, compression, and bag splitting."""

from datetime import datetime
import os
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, GroupAction, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import ComposableNodeContainer, LoadComposableNodes
from launch_ros.descriptions import ComposableNode
import yaml

def launch_setup(context, *args, **kwargs):
    base_config_val = LaunchConfiguration('base_config').perform(context)
    topic_config_val = LaunchConfiguration('topic_config').perform(context)
    use_composable = LaunchConfiguration('use_composable')
    create_container = LaunchConfiguration('create_container')
    container_name = LaunchConfiguration('container_name')
    namespace_val = LaunchConfiguration('namespace').perform(context).strip('/')

    # Format namespace for node/container execution
    node_ns = f'/{namespace_val}' if namespace_val else ''

    pkg_share = get_package_share_directory('robot_bag_utils')
    base_path = os.path.join(pkg_share, 'config', base_config_val)
    topic_path = os.path.join(pkg_share, 'config', topic_config_val)

    if not os.path.exists(base_path):
        raise FileNotFoundError(f'Base config file not found: {base_path}')
    if not os.path.exists(topic_path):
        raise FileNotFoundError(f'Topic config file not found: {topic_path}')

    # Load both YAML configuration files
    with open(base_path, 'r') as f:
        base_config = yaml.safe_load(f)
    with open(topic_path, 'r') as f:
        topic_config = yaml.safe_load(f)

    # Unwrap ROS parameters structure safely if present
    base_params = base_config.get('/**', base_config).get('ros__parameters', base_config)
    topic_params = topic_config.get('/**', topic_config).get('ros__parameters', topic_config)

    # Merge dictionaries: topic-specific configs override base configs
    recorder_config = {**base_params, **topic_params}

    # Extract settings from merged YAML (allowing launch arguments to override where applicable)
    storage_id = LaunchConfiguration('storage_id').perform(context) \
        or recorder_config.get('storage_id', 'mcap')

    max_cache_size_str = LaunchConfiguration('max_cache_size').perform(context)
    try:
        max_cache_size_bytes = int(max_cache_size_str) if max_cache_size_str \
            else int(recorder_config.get('max_cache_size', 104857600))
    except ValueError:
        raise ValueError(f'max_cache_size must be an integer (bytes), got: {max_cache_size_str}')

    preset_profile = recorder_config.get('storage_preset_profile', '')
    comp_format = recorder_config.get('compression_format', '')
    comp_mode = recorder_config.get('compression_mode', '')
    max_bag_size = int(recorder_config.get('max_bag_size', 0))
    max_bag_duration = int(recorder_config.get('max_bag_duration', 0))
    exclude_regex = recorder_config.get('exclude_regex', '') \
        or recorder_config.get('regex_to_exclude', '')
    qos_overrides = recorder_config.get('qos_profile_overrides', [])

    # Hierarchical Directory Inputs
    raw_root_dir = LaunchConfiguration('root_bag_dir').perform(context)
    raw_session_dir = LaunchConfiguration('session_dir').perform(context)
    raw_bag_name = LaunchConfiguration('bag_name').perform(context)

    # Resolve full bag folder name automatically using the topic config profile name
    now_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    profile_tag = os.path.splitext(topic_config_val)[0].replace('_topics', '')
    ns_prefix = f'{namespace_val}_' if namespace_val else ''

    if not raw_bag_name:
        bag_name = f'{ns_prefix}{profile_tag}_bag_{now_str}'
    else:
        bag_name = raw_bag_name

    # Expand user tildes and build full output prefix
    root_bag_dir = os.path.expanduser(raw_root_dir)
    full_output_dir = os.path.join(root_bag_dir, raw_session_dir)

    # Ensure the session directory exists before recording starts
    os.makedirs(full_output_dir, exist_ok=True)

    # Target path for ros2 bag output directory
    bag_prefix = os.path.join(full_output_dir, bag_name)

    raw_topics = recorder_config.get('topics', [])

    # Process relative topics with namespace if provided
    topics = []
    for t in raw_topics:
        if namespace_val and not t.startswith('/'):
            topics.append(f'/{namespace_val}/{t}')
        else:
            topics.append(t)

    # Process QoS overrides to prepend namespaces to topic paths if necessary
    processed_qos_overrides = []
    for override in qos_overrides:
        updated_override = override.copy()
        topic_name = updated_override.get('topic', '')
        if namespace_val and topic_name and not topic_name.startswith('/'):
            updated_override['topic'] = f'/{namespace_val}/{topic_name}'
        processed_qos_overrides.append(updated_override)

    # Filter out topics locally in Python if an exclude regex is provided
    if exclude_regex and topics:
        compiled_regex = re.compile(exclude_regex)
        topics = [t for t in topics if not compiled_regex.search(t)]

    # Build standalone command arguments
    cmd_args = [
        'ros2', 'bag', 'record',
        '--output', bag_prefix,
        '-s', storage_id,
        '--max-cache-size', str(max_cache_size_bytes),
    ]

    if namespace_val:
        cmd_args.extend(['--node-name', f'{namespace_val}_bag_recorder'])
    if storage_id == 'mcap' and preset_profile:
        cmd_args.extend(['--storage-preset-profile', preset_profile])
    elif comp_format and comp_mode:
        cmd_args.extend(['--compression-format', comp_format, '--compression-mode', comp_mode])
    if max_bag_size > 0:
        cmd_args.extend(['--max-bag-size', str(max_bag_size)])
    if max_bag_duration > 0:
        cmd_args.extend(['--max-bag-duration', str(max_bag_duration)])

    if exclude_regex and not topics:
        cmd_args.extend(['--exclude', exclude_regex])

    standalone_record_cmd = ExecuteProcess(
        condition=UnlessCondition(use_composable),
        cmd=cmd_args + topics,
        output='screen',
        sigterm_timeout='30.0',
        sigkill_timeout='30.0'
    )

    # Composable recorder mode parameters dictionary
    composable_params = {
        'bag_name': bag_prefix,
        'storage_id': storage_id,
        'max_cache_size': max_cache_size_bytes,
        'record_all': False,
        'serialization_format': 'cdr',
        'start_recording_immediately': True,
        'topics': topics,
        'disable_discovery': False,
    }

    if storage_id == 'mcap' and preset_profile:
        composable_params['storage_preset_profile'] = preset_profile
    elif comp_format and comp_mode:
        composable_params['compression_format'] = comp_format
        composable_params['compression_mode'] = comp_mode
    if max_bag_size > 0:
        composable_params['max_bag_size'] = max_bag_size
    if max_bag_duration > 0:
        composable_params['max_bag_duration'] = max_bag_duration
    if exclude_regex:
        composable_params['regex_to_exclude'] = exclude_regex
    if processed_qos_overrides:
        composable_params['qos_profile_overrides'] = processed_qos_overrides

    composable_record_cmd = GroupAction(
        condition=IfCondition(use_composable),
        actions=[
            ComposableNodeContainer(
                condition=IfCondition(create_container),
                name=container_name,
                namespace=node_ns,
                package='rclcpp_components',
                executable='component_container',
                composable_node_descriptions=[],
                output='screen',
            ),
            LoadComposableNodes(
                target_container=container_name,
                composable_node_descriptions=[
                    ComposableNode(
                        package='rosbag2_composable_recorder',
                        plugin='rosbag2_composable_recorder::ComposableRecorder',
                        name='recorder_node',
                        namespace=node_ns,
                        parameters=[composable_params],
                        extra_arguments=[{'use_intra_process_comms': True}],
                    ),
                ],
            )
        ]
    )

    return [standalone_record_cmd, composable_record_cmd]


def generate_launch_description():
    default_root = os.path.join(os.path.expanduser('~'), 'datalog', 'rosbag2')
    default_session = f'session_{datetime.now().strftime('%Y-%m-%d')}'

    return LaunchDescription([
        DeclareLaunchArgument(
            'namespace',
            default_value='',
            description='Optional namespace for node scoping and relative topic mapping',
        ),
        DeclareLaunchArgument(
            'base_config',
            default_value='common_logger.yaml',
            description='Base YAML filename inside config/ containing global logging settings',
        ),
        DeclareLaunchArgument(
            'topic_config',
            default_value='mavros_topics.yaml',
            description='Topic YAML filename inside config/ containing topics and overrides',
        ),
        DeclareLaunchArgument(
            'storage_id',
            default_value='',
            description='Storage plugin override (mcap, sqlite3). Blank defaults to YAML config.',
        ),
        DeclareLaunchArgument(
            'max_cache_size',
            default_value='',
            description='Max cache size bytes override. Blank defaults to YAML config.',
        ),
        DeclareLaunchArgument(
            'root_bag_dir',
            default_value=default_root,
            description='Root base directory where all mission sessions are stored',
        ),
        DeclareLaunchArgument(
            'session_dir',
            default_value=default_session,
            description='Session subfolder grouping multiple runs (defaults to date)',
        ),
        DeclareLaunchArgument(
            'bag_name',
            default_value='',
            description='Custom bag folder name (if empty, auto-generates tag + timestamp)',
        ),
        DeclareLaunchArgument(
            'use_composable',
            default_value='false',
            description='Use composable rosbag recorder in a component container',
        ),
        DeclareLaunchArgument(
            'create_container',
            default_value='false',
            description=('Launches a new container if true',
                         'or attaches to an existing one if false.'),
        ),
        DeclareLaunchArgument(
            'container_name',
            default_value='recorder_container',
            description='Composable container name used when use_composable:=true',
        ),
        OpaqueFunction(function=launch_setup),
    ])
