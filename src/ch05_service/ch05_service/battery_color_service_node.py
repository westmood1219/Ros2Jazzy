import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterValue, ParameterType


class BatteryColorServiceNode(Node):
    """用 Service 正确驱动 turtlesim 背景色——替换第3章的 subprocess 版本"""

    def __init__(self):
        super().__init__('battery_color_service_node')

        from std_msgs.msg import Float32
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

        battery_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self._sub = self.create_subscription(
            Float32, '/battery_level', self._on_battery, battery_qos
        )

        # 用 SetParameters 服务修改 turtlesim 的 background_r/g/b
        self._set_param_client = self.create_client(
            SetParameters, '/turtlesim/set_parameters'
        )
        # 用 Empty 服务触发 turtlesim 重绘背景
        self._clear_client = self.create_client(Empty, '/clear')

        self._last_bucket = -1
        self.get_logger().info('BatteryColorServiceNode 已启动')

    def _on_battery(self, msg) -> None:
        level = msg.data
        bucket = int(level / 10) * 10   # 每 10% 变化一次才更新

        if bucket == self._last_bucket:
            return
        self._last_bucket = bucket

        # 根据电量计算颜色
        if level > 50:
            r, g, b = 69, 86, 255
        elif level > 20:
            r, g, b = 255, 180, 0
        else:
            r, g, b = 220, 50, 50

        # ① 异步设置参数（不在回调里同步等待）
        self._set_background(r, g, b)

    def _set_background(self, r: int, g: int, b: int) -> None:
        """异步设置 turtlesim 背景色并触发重绘"""
        if not self._set_param_client.service_is_ready():
            self.get_logger().warn('SetParameters 服务尚未就绪')
            return

        req = SetParameters.Request()
        req.parameters = [
            Parameter(name='background_r',
                      value=ParameterValue(type=ParameterType.PARAMETER_INTEGER,
                                           integer_value=r)),
            Parameter(name='background_g',
                      value=ParameterValue(type=ParameterType.PARAMETER_INTEGER,
                                           integer_value=g)),
            Parameter(name='background_b',
                      value=ParameterValue(type=ParameterType.PARAMETER_INTEGER,
                                           integer_value=b)),
        ]

        future = self._set_param_client.call_async(req)
        future.add_done_callback(self._after_set_params)

    def _after_set_params(self, future) -> None:
        """参数设置完成后，调用 /clear 触发重绘"""
        try:
            future.result()   # 检查是否有异常
        except Exception as e:
            self.get_logger().error(f'设置参数失败：{e}')
            return

        if not self._clear_client.service_is_ready():
            return

        clear_future = self._clear_client.call_async(Empty.Request())
        clear_future.add_done_callback(
            lambda f: self.get_logger().debug('背景色已刷新')
        )


def main(args=None):
    rclpy.init(args=args)
    node = BatteryColorServiceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
