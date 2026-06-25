import sys
import rclpy
from rclpy.node import Node
from ch05_interfaces.srv import ResetSensor


class SensorResetClient(Node):
    """传感器重置客户端——演示带参数的服务调用"""

    def __init__(self):
        super().__init__('sensor_reset_client')
        self._client = self.create_client(ResetSensor, '/reset_sensor')

    def reset(self, sensor_name: str, force: bool = False) -> ResetSensor.Response:
        """同步重置传感器（在 main 函数中调用，不在回调中）"""
        while not self._client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('等待 /reset_sensor 服务...')

        request = ResetSensor.Request()
        request.sensor_name = sensor_name
        request.force_reset = force

        future = self._client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        return future.result()


def main(args=None):
    rclpy.init(args=args)
    node = SensorResetClient()

    # 从命令行参数获取传感器名
    sensor = sys.argv[1] if len(sys.argv) > 1 else 'lidar'
    force  = '--force' in sys.argv

    result = node.reset(sensor, force)

    if result.success:
        node.get_logger().info(
            f'重置成功：{result.message}，耗时 {result.reset_time_ms:.1f} ms'
        )
    else:
        node.get_logger().error(f'重置失败：{result.message}')

    node.destroy_node()
    rclpy.shutdown()
