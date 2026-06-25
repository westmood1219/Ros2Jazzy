import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import Float32


class BatteryNode(Node):
    """模拟机器人电池节点，周期性发布电量百分比"""

    # QoS：电量是状态数据，用 TRANSIENT_LOCAL 让晚订阅的节点也能立即读到最新值
    BATTERY_QOS = QoSProfile(
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )

    def __init__(self):
        super().__init__('battery_node')

        # ① 声明并读取节点参数（第7章详讲，此处预习用法）
        self.declare_parameter('discharge_rate', 0.5)   # 每秒放电百分比
        self.declare_parameter('initial_level', 100.0)  # 初始电量

        rate = self.get_parameter('discharge_rate').value
        level = self.get_parameter('initial_level').value

        self._level = float(level)
        self._rate = float(rate)

        # ② 创建发布者
        self._pub = self.create_publisher(
            Float32,
            '/battery_level',
            self.BATTERY_QOS,
        )

        # ③ 1 Hz 定时器
        self._timer = self.create_timer(1.0, self._publish)

        self.get_logger().info(
            f'BatteryNode 启动：初始电量={self._level:.1f}%，'
            f'放电速率={self._rate:.2f}%/s'
        )

    def _publish(self):
        # 电量不低于 0
        self._level = max(0.0, self._level - self._rate)

        msg = Float32()
        msg.data = self._level
        self._pub.publish(msg)

        # 分级日志：不同电量用不同日志等级
        if self._level <= 5.0:
            self.get_logger().error(f'电量危急！{self._level:.1f}%')
        elif self._level <= 20.0:
            self.get_logger().warn(f'电量低：{self._level:.1f}%')
        else:
            self.get_logger().info(f'电量：{self._level:.1f}%')


def main(args=None):
    rclpy.init(args=args)
    node = BatteryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
