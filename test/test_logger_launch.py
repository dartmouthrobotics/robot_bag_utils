import os
import shutil
import tempfile
import unittest
import pytest

from ament_index_python.packages import get_package_share_directory
import launch
from launch.actions import TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
import launch_testing
import launch_testing.actions

# Create isolated directories for both execution modes
TMP_DIR_STANDALONE = tempfile.mkdtemp()
TMP_DIR_COMPOSABLE = tempfile.mkdtemp()


@pytest.mark.launch_test
def generate_test_description():
    pkg_share = get_package_share_directory('robot_bag_utils')
    launch_file_path = os.path.join(pkg_share, 'launch', 'logger.launch.py')

    # 1. Standalone CLI Launch
    logger_standalone = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file_path),
        launch_arguments={
            'base_config': 'common_logger.yaml',
            'topic_config': 'mavros_topics.yaml',
            'root_bag_dir': TMP_DIR_STANDALONE,
            'session_dir': 'test_session_standalone',
            'use_composable': 'false',
        }.items(),
    )

    # 2. Composable Container Launch
    logger_composable = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file_path),
        launch_arguments={
            'base_config': 'common_logger.yaml',
            'topic_config': 'mavros_topics.yaml',
            'root_bag_dir': TMP_DIR_COMPOSABLE,
            'session_dir': 'test_session_composable',
            'use_composable': 'true',
            'create_container': 'true',
            'container_name': 'test_recorder_container',
        }.items(),
    )

    return (
        launch.LaunchDescription([
            logger_standalone,
            logger_composable,
            # Wait 2 seconds for both standalone CLI and container to initialize
            TimerAction(
                period=2.0,
                actions=[launch_testing.actions.ReadyToTest()]
            ),
        ]),
        {}
    )


class TestLoggerLaunchRuntime(unittest.TestCase):

    def test_recorders_spin_up(self, proc_info=None):
        """Verify both standalone and composable processes started up and remained active."""
        if proc_info is not None:
            procs = proc_info.processes()
            # We expect multiple active processes (the CLI tool + the container)
            self.assertGreater(
                len(procs), 1, "Expected both standalone and container processes to be running."
            )


@launch_testing.post_shutdown_test()
class TestLoggerLaunchShutdown(unittest.TestCase):

    def test_exit_codes(self, proc_info=None):
        """Verify all processes shut down cleanly without CLI or runtime error exit codes."""
        if proc_info is not None:
            # Allow clean exits: 0, -2 (SIGINT), -15 (SIGTERM), 130
            launch_testing.asserts.assertExitCodes(
                proc_info,
                allowable_exit_codes=[0, -2, 130, -15]
            )

        # Cleanup both directories
        if os.path.exists(TMP_DIR_STANDALONE):
            shutil.rmtree(TMP_DIR_STANDALONE, ignore_errors=True)
        if os.path.exists(TMP_DIR_COMPOSABLE):
            shutil.rmtree(TMP_DIR_COMPOSABLE, ignore_errors=True)

    def test_no_component_load_errors(self, proc_output, proc_info):
        """Verify no process logged any errors or fatal faults."""
        for proc in proc_info.processes():
            for io_record in proc_output[proc]:
                text = io_record.text.decode('utf-8', 'replace')

                # The ultimate generic catch: fail if ANY [ERROR] is logged
                self.assertNotIn(
                    "[ERROR]",
                    text,
                    f"An error was logged: {text.strip()}"
                )

                # Also catch fatal crashes
                self.assertNotIn(
                    "[FATAL]",
                    text,
                    f"A fatal fault was logged: {text.strip()}"
                )
