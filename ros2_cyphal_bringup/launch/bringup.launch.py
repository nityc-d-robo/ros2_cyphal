import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.event_handlers import OnProcessStart
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # Get package paths
    hardware_pkg = get_package_share_directory('ros2_cyphal_hardware')
    bringup_pkg = get_package_share_directory('ros2_cyphal_bringup')

    # Paths to files
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            os.path.join(hardware_pkg, "urdf", "robot.xacro"),
        ]
    )
    robot_description = {"robot_description": ParameterValue(robot_description_content, value_type=str)}

    robot_controllers = os.path.join(bringup_pkg, "config", "controllers.yaml")

    # Nodes
    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[robot_description, robot_controllers],
        output="both",
    )

    robot_state_pub_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[robot_description],
    )

    joint_state_broadcaster_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
    )

    joint_position_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_position_controller", "--controller-manager", "/controller_manager"],
    )

    # Delay start of joint_state_broadcaster_spawner after control_node
    delay_joint_state_broadcaster_spawner_after_control_node = RegisterEventHandler(
        event_handler=OnProcessStart(
            target_action=control_node,
            on_start=[joint_state_broadcaster_spawner],
        )
    )

    # Delay start of joint_position_controller_spawner after joint_state_broadcaster_spawner
    delay_joint_position_controller_spawner_after_joint_state_broadcaster_spawner = RegisterEventHandler(
        event_handler=OnProcessStart(
            target_action=joint_state_broadcaster_spawner,
            on_start=[joint_position_controller_spawner],
        )
    )

    nodes = [
        control_node,
        robot_state_pub_node,
        delay_joint_state_broadcaster_spawner_after_control_node,
        delay_joint_position_controller_spawner_after_joint_state_broadcaster_spawner,
    ]

    return LaunchDescription(nodes)
