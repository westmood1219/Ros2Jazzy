import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from std_srvs.srv import Empty
import subprocess


class BatteryColorNode(Node):
    """订阅电量，根据电量等级设置 turtlesim 背景色"""

    def __init__(self):
        super().__init__('battery_color_node')

        # 订阅电量话题（第4章详讲 Subscriber，此处先用）
        self._sub = self.create_subscription(
            Float32,
            '/battery_level',
            self._on_battery,
            10,
        )
        self._last_level = -1.0  # 避免重复设置
        self.get_logger().info('BatteryColorNode 已启动，等待电量消息...')

    def _on_battery(self, msg: Float32):
        level = msg.data

        # 每5%变化一次才更新（减少刷新频率）
        bucket = int(level / 5) * 5
        if bucket == int(self._last_level / 5) * 5:
            return
        self._last_level = level

        # 根据电量计算背景颜色（绿→黄→红）
        if level > 50:
            r, g, b = 69, 86, 255      # 蓝绿色（充足）
        elif level > 20:
            r, g, b = 255, 200, 0      # 橙黄色（适中）
        else:
            r, g, b = 220, 50, 50      # 红色（低电量警告）

        # 用 ros2 param set 修改 turtlesim 背景色
        # 注意：这是演示用法，生产代码应使用 Service 客户端
        import subprocess
        subprocess.run([
            'ros2', 'param', 'set', '/turtlesim',
            'background_r', str(r)
        ], capture_output=True)
        subprocess.run([
            'ros2', 'param', 'set', '/turtlesim',
            'background_g', str(g)
        ], capture_output=True)
        subprocess.run([
            'ros2', 'param', 'set', '/turtlesim',
            'background_b', str(b)
        ], capture_output=True)

        self.get_logger().info(
            f'电量 {level:.1f}%，背景色更新为 RGB({r},{g},{b})'
        )


def main(args=None):
    rclpy.init(args=args)
    node = BatteryColorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
