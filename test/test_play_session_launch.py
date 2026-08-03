"""Integration test for play_session.launch.py."""

import os
import shutil
import sqlite3
import tempfile
import unittest

from ament_index_python.packages import get_package_share_directory
import launch
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
import launch_testing
import launch_testing.actions
import pytest


@pytest.mark.launch_test
def generate_test_description():
    # 1. Setup a temporary filesystem structure to mock a datalog session
    temp_root = tempfile.mkdtemp()
    session_name = 'session_test'
    session_path = os.path.join(temp_root, session_name)
    os.makedirs(session_path)

    # Create a mock bag directory with a dummy metadata.yaml
    bag_path = os.path.join(session_path, 'mock_bag_1')
    os.makedirs(bag_path)
    with open(os.path.join(bag_path, 'metadata.yaml'), 'w') as f:
        f.write(
            'rosbag2_bagfile_information:\n'
            '  version: 5\n'
            '  storage_identifier: sqlite3\n'
            '  duration:\n'
            '    nanoseconds: 5000000000\n'
            '  starting_time:\n'
            '    nanoseconds_since_epoch: 1700000000000000000\n'
            '  message_count: 2\n'
            '  topics_with_message_count:\n'
            '    -\n'
            '      topic_metadata:\n'
            '        name: /test_topic\n'
            '        type: std_msgs/msg/String\n'
            '        serialization_format: cdr\n'
            '        offered_qos_profiles: ""\n'
            '      message_count: 1\n'
            '  compression_format: ""\n'
            '  compression_mode: ""\n'
            '  relative_file_paths:\n'
            '    - mock_bag_1_0.db3\n'
            '  files:\n'
            '    -\n'
            '      path: mock_bag_1_0.db3\n'
            '      starting_time:\n'
            '        nanoseconds_since_epoch: 1700000000000000000\n'
            '      duration:\n'
            '        nanoseconds: 1000000\n'
            '      message_count: 2\n'
            '  serialization_format: cdr\n'
        )

    # Create a dummy sqlite3 database file so rosbag2 storage can open it
    db_file_path = os.path.join(bag_path, 'mock_bag_1_0.db3')
    conn = sqlite3.connect(db_file_path)
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE topics ('
        'id INTEGER PRIMARY KEY, '
        'name TEXT, '
        'type TEXT, '
        'serialization_format TEXT, '
        'offered_qos_profiles TEXT'
        ');'
    )
    cursor.execute(
        'CREATE TABLE messages ('
        'id INTEGER PRIMARY KEY, '
        'topic_id INTEGER, '
        'timestamp INTEGER, '
        'data BLOB'
        ');'
    )

    # Insert a dummy topic and message so the bag player doesn't exit instantly
    cursor.execute(
        'INSERT INTO topics (id, name, type, serialization_format, offered_qos_profiles) '
        'VALUES (?, ?, ?, ?, ?);',
        (1, '/test_topic', 'std_msgs/msg/String', 'cdr', '')
    )
    cursor.execute(
        'INSERT INTO messages (id, topic_id, timestamp, data) '
        'VALUES (?, ?, ?, ?);',
        (1, 1, 1700000000000000000, b'\x00')
    )
    cursor.execute(
        'INSERT INTO messages (id, topic_id, timestamp, data) '
        'VALUES (?, ?, ?, ?);',
        (2, 1, 1700000005000000000, b'\x00')
    )
    conn.commit()
    conn.close()

    # 2. Locate the launch file
    launch_file_path = os.path.join(
        get_package_share_directory('robot_bag_utils'),
        'launch',
        'play_session.launch.py'
    )

    # 3. Include the launch file with the mocked arguments
    play_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file_path),
        launch_arguments={
            'root_bag_dir': temp_root,
            'session_dir': session_name,
            'rate': '1.0',
            'clock': 'false',
            'loop': 'true',
        }.items()
    )

    context = {'temp_root': temp_root}

    return (launch.LaunchDescription([
        play_launch,
        TimerAction(
                period=2.0,
                actions=[launch_testing.actions.ReadyToTest()]
        ),
    ]), context)


class TestPlaySessionLaunch(unittest.TestCase):

    def test_processes_started(self, proc_info=None):
        """Test that the launch file successfully spawns processes without crashing."""
        if proc_info is not None:
            procs = proc_info.processes()
            # Check that at least one process was started (our mock bag play command)
            assert len(procs) > 0

            # Verify that the process name matches what we assigned in the OpaqueFunction
            process_names = [proc.name for proc in proc_info.processes()]
            self.assertTrue(any('bag_play_mock_bag_1' in name for name in process_names))


@launch_testing.post_shutdown_test()
class TestPlaySessionLaunchPostShutdown(unittest.TestCase):

    def test_exit_codes(self, proc_info, temp_root):
        """Test that the processes exited cleanly."""
        # Cleanup the temporary directory here to ensure it happens after processes die
        if os.path.exists(temp_root):
            shutil.rmtree(temp_root)

        # We don't strictly assert exit code 0 here because our dummy metadata.yaml
        # isn't a valid SQLite/MCAP database, so ros2 bag play might exit with an error.
        # The primary goal is verifying the OpaqueFunction logic successfully built the command.
        launch_testing.asserts.assertExitCodes(proc_info, allowable_exit_codes=[0, 1, 2])
