from launch import LaunchDescription
from launch.actions import TimerAction
from launch_ros.actions import Node
from launch.substitutions import Command
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    desc_pkg = get_package_share_directory('embobot_description')
    xacro_file = os.path.join(desc_pkg, 'xacro', 'embobot.urdf.xacro')
    ctrl_config = os.path.join(desc_pkg, 'config', 'embobot_controllers.yaml')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file,
                 ' use_sim:=false use_mock:=true']),  # 关键：use_mock=true
        value_type=str,
    )

    return LaunchDescription([
        # robot_state_publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': False,   # 无仿真时钟
            }],
        ),
        # controller_manager（直接作为 ROS 2 节点，无需 Gazebo）
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            parameters=[
                {'robot_description': robot_description},
                ctrl_config,
            ],
            output='screen',
        ),
        # 先启动 joint_state_broadcaster，再启动 diff_drive_controller，避免并发 spawner 竞态
        TimerAction(period=1.0, actions=[
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=['joint_state_broadcaster', '--controller-manager',
                           '/controller_manager', '--controller-manager-timeout', '20'],
                output='screen',
            ),
        ]),
        TimerAction(period=2.0, actions=[
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=['diff_drive_controller', '--controller-manager',
                           '/controller_manager', '--controller-manager-timeout', '20'],
                output='screen',
            ),
        ]),
        # Jazzy 的 diff_drive_controller 订阅 TwistStamped。
        # 保留 /cmd_vel 作为外部 Twist 入口，由官方 twist_stamper 加时间戳后转发。
        Node(
            package='twist_stamper',
            executable='twist_stamper',
            name='twist_stamper',
            remappings=[
                ('/cmd_vel_in', '/cmd_vel'),
                ('/cmd_vel_out', '/diff_drive_controller/cmd_vel'),
            ],
            output='screen',
        ),
    ])
