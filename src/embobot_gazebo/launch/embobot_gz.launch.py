# launch/embobot_gz.launch.py
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration, Command, PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # ── 包路径 ──────────────────────────────────────────────
    gz_pkg    = get_package_share_directory('embobot_gazebo')
    desc_pkg  = get_package_share_directory('embobot_description')
    ros_gz_pkg = get_package_share_directory('ros_gz_sim')

    # ── 文件路径 ────────────────────────────────────────────
    world_file    = os.path.join(gz_pkg, 'worlds', 'embobot_world.sdf')
    xacro_file    = os.path.join(desc_pkg, 'xacro', 'embobot.urdf.xacro')
    bridge_config = os.path.join(gz_pkg, 'config', 'ros_gz_bridge.yaml')
    rviz_config   = os.path.join(gz_pkg, 'rviz', 'embobot_gz.rviz')
    ctrl_config   = os.path.join(desc_pkg, 'config', 'embobot_controllers.yaml')

    # ── 参数 ────────────────────────────────────────────────
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    robot_description = Command(['xacro ', xacro_file, ' use_sim:=true'])

    # ① 启动 Gazebo Harmonic（加载世界文件）
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_pkg, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': f'-r {world_file}',  # -r 自动开始运行
            'on_exit_shutdown': 'True',
        }.items(),
    )

    # ② robot_state_publisher（将 URDF 发布到 /robot_description）
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }],
    )

    # ③ 生成 EmboBot（从 /robot_description 话题读取 URDF）
    spawn_robot = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='ros_gz_sim',
                executable='create',
                name='spawn_embobot',
                arguments=[
                    '-name', 'embobot',
                    '-topic', '/robot_description',
                    '-x', '0.0',
                    '-y', '0.0',
                    '-z', '0.05',
                    '-R', '0.0',
                    '-P', '0.0',
                    '-Y', '0.0',
                ],
                output='screen',
            ),
        ],
    )

    # ④ ros_gz_bridge（话题桥接）
    #    延迟到 robot spawn 之后（t=4s），确保 lidar sensor 等 topic 已就绪
    bridge = TimerAction(
        period=4.0,
        actions=[
            Node(
                package='ros_gz_bridge',
                executable='parameter_bridge',
                name='ros_gz_bridge',
                output='screen',
                parameters=[{
                    'config_file': bridge_config,
                    'use_sim_time': use_sim_time,
                    'qos_overrides./tf.publisher.reliability': 'reliable',
                }],
            ),
        ],
    )

    # ⑤ controller_manager（ros2_control）
    controller_manager = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                name='controller_manager',
                output='screen',
                parameters=[
                    {'robot_description': robot_description},
                    ctrl_config,
                    {'use_sim_time': use_sim_time},
                ],
            ),
        ],
    )

    # ⑥ 启动控制器
    start_jsb = TimerAction(
        period=7.0,
        actions=[
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=[
                    'joint_state_broadcaster',
                    '--controller-manager', '/controller_manager',
                    '--controller-manager-timeout', '20',
                ],
                output='screen',
            ),
        ],
    )
    start_ddc = TimerAction(
        period=8.0,
        actions=[
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=[
                    'diff_drive_controller',
                    '--controller-manager', '/controller_manager',
                    '--controller-manager-timeout', '20',
                    # 显式传递参数文件，Jazzy 不会自动从 controller_manager 转发
                    '--param-file', ctrl_config,
                ],
                output='screen',
            ),
        ],
    )

    # ⑦ RViz2
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time', default_value='true',
            description='使用仿真时间',
        ),
        gz_sim,
        robot_state_publisher,
        spawn_robot,
        bridge,
        controller_manager,
        start_jsb,
        start_ddc,
        rviz,
    ])