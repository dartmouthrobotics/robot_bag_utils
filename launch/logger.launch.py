"""
logger.launch.py  

* Added 
    - /zed/zed_node/left/image_rect_color/compressed
    - /zed/zed_node/left/camera_info
    - /zed/zed_node/depth/depth_registered
    - /zed/zed_node/pose, /odom
    - /zed/zed_node/imu/data       
    - /zed/zed_node/imu/data_raw    
    - /INS/ins_data  (miniAHRS)

"""

import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, EnvironmentVariable


def generate_launch_description():

    bag_dir_arg = DeclareLaunchArgument(
        "bag_dir",
        default_value="/home/catabot-5/datalog/rosbag2",
        description="Root directory where ros2 bag folders are saved",
    )

    # Timestamp baked in at launch time 
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    bag_name = f"catabot_{timestamp}"

    bag_dir = LaunchConfiguration("bag_dir")

    topics = [

        # ---------------------------------------------------------------- #
        #  Catabot servo / compass                                         #
        # ---------------------------------------------------------------- #
        "/catabot/servo/PWM_right",
        "/catabot/servo/PWM_left",
        "/catabot/compass_turn/time",

        "/mavlink/from",
        "/mavlink/to",
        "/mavros/battery",
        "/mavros/estimator_status",
        "/mavros/extended_state",
        "/mavros/global_position/compass_hdg",
        "/mavros/global_position/global",
        "/mavros/global_position/gp_origin",
        "/mavros/global_position/home",
        "/mavros/global_position/local",
        "/mavros/global_position/raw/fix",
        "/mavros/global_position/raw/gps_vel",
        "/mavros/global_position/raw/satellites",
        "/mavros/global_position/rel_alt",
        "/mavros/gpsstatus/gps1/raw",
        "/mavros/gpsstatus/gps1/rtk",
        "/mavros/gpsstatus/gps2/raw",
        "/mavros/gpsstatus/gps2/rtk",
        "/mavros/imu/data",
        "/mavros/imu/data_raw",
        "/mavros/imu/diff_pressure",
        "/mavros/imu/mag",
        "/mavros/imu/static_pressure",
        "/mavros/imu/temperature_baro",
        "/mavros/imu/temperature_imu",
        "/mavros/local_position/accel",
        "/mavros/local_position/odom",
        "/mavros/local_position/pose",
        "/mavros/local_position/pose_cov",
        "/mavros/local_position/velocity_body",
        "/mavros/local_position/velocity_local",
        "/mavros/mission/reached",
        "/mavros/mission/waypoints",
        "/mavros/radio_status",
        "/mavros/rangefinder/rangefinder",
        "/mavros/rc/in",
        "/mavros/rc/out",
        "/mavros/state",
        "/mavros/statustext/recv",
        "/mavros/time_reference",
        "/mavros/timesync_status",
        "/mavros/vfr_hud",
        "/mavros/wind_estimation",
        "/odometry/filtered",

        # ---------------------------------------------------------------- #
        #  Ouster LiDAR                                                     #
        # ---------------------------------------------------------------- #
        # "/ouster/lidar_packets",
        # "/ouster/imu_packets",
        "/ouster/metadata",
        "/ouster/points",
        "/ouster/imu",
        "/ouster/scan",

        # ---------------------------------------------------------------- #
        #  ZED X camera                                                    #
        # ---------------------------------------------------------------- #
        "/blue/zed/left/color/raw/image/compressed",
        "/blue/zed/left/color/raw/camera_info",
        "/blue/zed/right/color/raw/image/compressed",
        "/blue/zed/right/color/raw/camera_info",
        "/blue/zed/depth/depth_registered",
        "/blue/zed/pose",
        "/blue/zed/odom",
        "/blue/zed/imu/data",
        "/green/zed/left/color/raw/image/compressed",
        "/green/zed/left/color/raw/camera_info",
        "/green/zed/right/color/raw/image/compressed",
        "/green/zed/right/color/raw/camera_info",
        "/green/zed/depth/depth_registered",
        "/green/zed/pose",
        "/green/zed/odom",
        "/green/zed/imu/data",
        "/red/zed/left/color/raw/image/compressed",
        "/red/zed/left/color/raw/camera_info",
        "/red/zed/right/color/raw/image/compressed",
        "/red/zed/right/color/raw/camera_info",
        "/red/zed/depth/depth_registered",
        "/red/zed/pose",
        "/red/zed/odom",
        "/red/zed/imu/data",
        "/pink/zed/left/color/raw/image/compressed",
        "/pink/zed/left/color/raw/camera_info",
        "/pink/zed/right/color/raw/image/compressed",
        "/pink/zed/right/color/raw/camera_info",
        "/pink/zed/depth/depth_registered",
        "/pink/zed/pose",
        "/pink/zed/odom",
        "/pink/zed/imu/data",

        # ---------------------------------------------------------------- #
        #  InertialLabs miniAHRS                                            #
        # ---------------------------------------------------------------- #
        "/miniAHRS/Inertial_Labs/ins_data",
        "/miniAHRS/Inertial_Labs/sensor_data",
        "/miniAHRS/Inertial_Labs/gnss_data",
        "/miniAHRS/Inertial_Labs/gps_data",
        "/miniAHRS/Inertial_Labs/marine_data",
        "/miniAHRS/imu/data",

        # ---------------------------------------------------------------- #
        #  Surface USB camera                                               #
        # ---------------------------------------------------------------- #
        "/usb_cam_surface/image_raw/compressed",
        "/usb_cam_surface/camera_info",

        # Imagenex sidescan
        "/imagenex896/range",
        "/imagenex896/range_raw",
        # Depth transducer (sonar)
        "/depth_transducer/depth",
        "/depth_transducer/nmea_raw",
        "/depth_transducer/temperature",
        # Velodyne (fallback lidar)
        "/velodyne_packets",
        "/velodyne_points",
        "/scan",
        # Sonde
        "/sonde",
        # Underwater camera
        "/usb_cam_underwater/image_raw/compressed",
        "/usb_cam_underwater/camera_info",

        # ---------------------------------------------------------------- #
        #  TF                                                               #
        # ---------------------------------------------------------------- #
        "/tf",
        "/tf_static",

        # ---------------------------------------------------------------- #
        #  rosout                                             #
        # ---------------------------------------------------------------- #
        "/diagnostics",
        "/rosout",
    ]

    record_cmd = ExecuteProcess(
        cmd=[
            "ros2", "bag", "record",
            "--output", [bag_dir, "/", bag_name],
            "--compression-mode", "file",
            "--compression-format", "zstd",
        ] + topics,
        output="screen",
    )

    return LaunchDescription([
        bag_dir_arg,
        record_cmd,
    ])
