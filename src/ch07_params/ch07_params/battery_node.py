import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.msg import ParameterDescriptor, FloatingPointRange, SetParametersResult
from std_msgs.msg import Float32
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy


class ConfigurableBatteryNode(Node):
    """
    可配置的电量节点——第3章 BatteryNode 的完整升级版。
    所有"魔法数字"都变成了可在运行时修改的参数。
    """

    _BATTERY_QOS = QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )

    def __init__(self):
        super().__init__('battery_node')

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ① 声明参数，使用 ParameterDescriptor 添加约束和说明
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self.declare_parameter(
            'discharge_rate',
            0.5,
            ParameterDescriptor(
                description='每秒放电百分比',
                floating_point_range=[FloatingPointRange(
                    from_value=0.01,
                    to_value=10.0,
                    step=0.01,
                )]
            )
        )
        self.declare_parameter(
            'initial_level',
            100.0,
            ParameterDescriptor(
                description='初始电量（0–100）',
                floating_point_range=[FloatingPointRange(
                    from_value=0.0,
                    to_value=100.0,
                )]
            )
        )
        self.declare_parameter('warn_threshold', 20.0,
            ParameterDescriptor(description='低电量警告阈值'))
        self.declare_parameter('crit_threshold', 5.0,
            ParameterDescriptor(description='危急电量阈值'))
        self.declare_parameter('enable_color', True,
            ParameterDescriptor(description='是否启用背景色联动'))

        # ② 读取参数初始值
        self._load_params()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ③ 注册参数变更回调——每次外部修改参数时自动触发
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        self.add_on_set_parameters_callback(self._on_params_change)

        self._pub = self.create_publisher(Float32, '/battery_level', self._BATTERY_QOS)
        self._timer = self.create_timer(1.0, self._publish)

        self.get_logger().info(
            f'ConfigurableBatteryNode 已启动\n'
            f'  放电速率: {self._rate} %/s\n'
            f'  初始电量: {self._level}%\n'
            f'  警告阈值: {self._warn_thr}%\n'
            f'  危急阈值: {self._crit_thr}%'
        )

    def _load_params(self) -> None:
        """从参数服务器读取所有参数到内部变量"""
        self._rate     = self.get_parameter('discharge_rate').value
        self._level    = self.get_parameter('initial_level').value
        self._warn_thr = self.get_parameter('warn_threshold').value
        self._crit_thr = self.get_parameter('crit_threshold').value
        self._color_on = self.get_parameter('enable_color').value

    def _on_params_change(self, params: list) -> SetParametersResult:
        """
        参数变更回调：
        - 在这里做合法性校验
        - 校验通过后更新内部状态（让参数立即生效）
        - 返回 SetParametersResult 告知框架是否接受此次变更
        """
        for p in params:
            # 校验：warn_threshold 必须大于 crit_threshold
            if p.name == 'warn_threshold':
                crit = self.get_parameter('crit_threshold').value
                if p.value <= crit:
                    return SetParametersResult(
                        successful=False,
                        reason=f'warn_threshold ({p.value}) 必须大于 crit_threshold ({crit})'
                    )
            if p.name == 'crit_threshold':
                warn = self.get_parameter('warn_threshold').value
                if p.value >= warn:
                    return SetParametersResult(
                        successful=False,
                        reason=f'crit_threshold ({p.value}) 必须小于 warn_threshold ({warn})'
                    )

        # 所有参数均合法，更新内部状态
        self._load_params()
        self.get_logger().info(f'参数已更新：rate={self._rate}, warn={self._warn_thr}')
        return SetParametersResult(successful=True)

    def _publish(self) -> None:
        self._level = max(0.0, self._level - self._rate)
        msg = Float32()
        msg.data = self._level
        self._pub.publish(msg)

        if self._level <= self._crit_thr:
            self.get_logger().error(f'[CRITICAL] 电量 {self._level:.1f}%')
        elif self._level <= self._warn_thr:
            self.get_logger().warn(f'[WARNING]  电量 {self._level:.1f}%')
        else:
            self.get_logger().debug(f'电量 {self._level:.1f}%')


def main(args=None):
    rclpy.init(args=args)
    node = ConfigurableBatteryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
