import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile, ReliabilityPolicy,
    DurabilityPolicy, HistoryPolicy,
)
from std_msgs.msg import Float32, String


# 警报等级常量（避免魔法字符串）
class AlertLevel:
    OK       = 'OK'
    WARNING  = 'WARNING'
    CRITICAL = 'CRITICAL'


class AlertNode(Node):
    """订阅电量话题，触发分级警报并重新发布"""

    # 与发布者保持一致的 QoS（TRANSIENT_LOCAL 确保晚订阅也能收到）
    _BATTERY_QOS = QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )

    # 阈值配置
    WARN_THRESHOLD     = 20.0  # 低于此值发出 WARNING
    CRITICAL_THRESHOLD = 5.0   # 低于此值发出 CRITICAL

    def __init__(self):
        super().__init__('alert_node')

        # ① 订阅电量话题
        self._sub = self.create_subscription(
            Float32,
            '/battery_level',
            self._on_battery,     # 回调函数
            self._BATTERY_QOS,
        )

        # ② 发布警报话题（普通 RELIABLE 即可，不需要 TRANSIENT_LOCAL）
        self._alert_pub = self.create_publisher(String, '/battery_alert', 10)

        # ③ 内部状态：记录上一次警报等级，避免重复发布相同警报
        self._last_level = AlertLevel.OK

        self.get_logger().info(
            f'AlertNode 已启动，阈值：'
            f'WARNING < {self.WARN_THRESHOLD}%，'
            f'CRITICAL < {self.CRITICAL_THRESHOLD}%'
        )

    def _on_battery(self, msg: Float32) -> None:
        """电量消息回调——保持轻量，快速返回"""
        level = msg.data
        alert = self._classify(level)

        # 仅在等级变化时重新发布，避免话题泛洪
        if alert != self._last_level:
            self._publish_alert(alert, level)
            self._last_level = alert

        # 日志按等级着色，方便终端快速识别
        if alert == AlertLevel.CRITICAL:
            self.get_logger().error(f'[CRITICAL] 电量 {level:.1f}%')
        elif alert == AlertLevel.WARNING:
            self.get_logger().warn(f'[WARNING]  电量 {level:.1f}%')
        else:
            self.get_logger().debug(f'[OK]       电量 {level:.1f}%')

    def _classify(self, level: float) -> str:
        """纯函数：根据电量值返回警报等级，便于单独测试"""
        if level <= self.CRITICAL_THRESHOLD:
            return AlertLevel.CRITICAL
        if level <= self.WARN_THRESHOLD:
            return AlertLevel.WARNING
        return AlertLevel.OK

    def _publish_alert(self, alert: str, level: float) -> None:
        msg = String()
        msg.data = f'{alert}: battery at {level:.1f}%'
        self._alert_pub.publish(msg)
        self.get_logger().info(f'发布警报：{msg.data}')


def main(args=None):
    rclpy.init(args=args)
    node = AlertNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

