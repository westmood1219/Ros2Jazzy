# launch/embobot_gz.launch.py
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription,
    TimerAction, ExecuteProcess,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node


def generate_launch_description():

    gz_pkg    = get_package_share_directory('embobot_gazebo')
    desc_pkg  = get_package_share_directory('embobot_description')
    ros_gz_pkg = get_package_share_directory('ros_gz_sim')

    world_file     = os.path.join(gz_pkg, 'worlds', 'embobot_world.sdf')
    xacro_file     = os.path.join(desc_pkg, 'xacro', 'embobot.urdf.xacro')
    bridge_config  = os.path.join(gz_pkg, 'config', 'ros_gz_bridge.yaml')
    rviz_config    = os.path.join(gz_pkg, 'rviz', 'embobot_gz.rviz')
    ctrl_config    = os.path.join(desc_pkg, 'config', 'embobot_controllers.yaml')
    ddc_params     = os.path.join(gz_pkg, 'config', 'diff_drive_params.yaml')
    stamper_script = os.path.join(gz_pkg, 'resource', 'twist_stamper.py')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    robot_description = Command(['xacro ', xacro_file, ' use_sim:=true'])

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_pkg, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r {world_file}', 'on_exit_shutdown': 'True'}.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher', executable='robot_state_publisher',
        name='robot_state_publisher', output='screen',
        parameters=[{'robot_description': robot_description, 'use_sim_time': use_sim_time}],
    )

    spawn_robot = TimerAction(period=3.0, actions=[
        Node(package='ros_gz_sim', executable='create', name='spawn_embobot',
             arguments=['-name', 'embobot', '-topic', '/robot_description',
                        '-x', '0.0', '-y', '0.0', '-z', '0.0',
                        '-R', '0.0', '-P', '0.0', '-Y', '0.0'],
             output='screen'),
    ])

    bridge = TimerAction(period=4.0, actions=[
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='ros_gz_bridge',
             output='screen',
             parameters=[{'config_file': bridge_config, 'use_sim_time': use_sim_time,
                          'qos_overrides./tf.publisher.reliability': 'reliable'}]),
    ])

    controller_manager = TimerAction(period=5.0, actions=[
        Node(package='controller_manager', executable='ros2_control_node', name='controller_manager',
             output='screen',
             parameters=[{'robot_description': robot_description}, ctrl_config,
                         {'use_sim_time': use_sim_time}]),
    ])

    start_jsb = TimerAction(period=7.0, actions=[
        Node(package='controller_manager', executable='spawner',
             arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager',
                        '--controller-manager-timeout', '20'],
             output='screen'),
    ])

    start_ddc = TimerAction(period=8.0, actions=[
        Node(package='controller_manager', executable='spawner',
             arguments=[
                 'diff_drive_controller',
                 '--controller-manager', '/controller_manager',
                 '--controller-manager-timeout', '20',
                 '--param-file', ddc_params,
                 
             ],
             output='screen'),
    ])

    twist_stamper = ExecuteProcess(
        cmd=['python3', stamper_script], name='twist_stamper', output='screen',
    )

    rviz = Node(package='rviz2', executable='rviz2', name='rviz2', output='screen',
                arguments=['-d', rviz_config], parameters=[{'use_sim_time': use_sim_time}])

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true', description='使用仿真时间'),
        gz_sim, robot_state_publisher, spawn_robot, bridge,
        controller_manager, start_jsb, start_ddc,
        twist_stamper, rviz,
    ])
