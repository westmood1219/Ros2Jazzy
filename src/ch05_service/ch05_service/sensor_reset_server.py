import time
import rclpy
from rclpy.node import Node
from ch05_interfaces.srv import ResetSensor   # 导入刚刚生成的接口


class SensorResetServer(Node):
    """传感器重置服务端——模拟实际的传感器复位操作"""

    # 已知的传感器列表（真实项目中从配置文件读取）
    KNOWN_SENSORS = {'lidar', 'camera', 'imu', 'ultrasound'}

    def __init__(self):
        super().__init__('sensor_reset_server')

        self._srv = self.create_service(
            ResetSensor,
            '/reset_sensor',
            self._handle_reset,
        )
        self.get_logger().info(
            f'传感器重置服务已就绪，支持：{self.KNOWN_SENSORS}'
        )

    def _handle_reset(self, request: ResetSensor.Request,
                      response: ResetSensor.Response) -> ResetSensor.Response:
        name = request.sensor_name
        self.get_logger().info(
            f'收到重置请求：sensor={name}, force={request.force_reset}'
        )

        if name not in self.KNOWN_SENSORS:
            response.success = False
            response.message = f'未知传感器：{name}'
            response.reset_time_ms = 0.0
            return response

        # 模拟重置耗时（真实场景：发串口命令、等待硬件响应）
        t0 = time.monotonic()
        reset_duration = 0.05 if request.force_reset else 0.2
        time.sleep(reset_duration)   # ⚠️ 服务回调中允许少量睡眠，但要控制在合理范围内
        elapsed_ms = (time.monotonic() - t0) * 1000

        response.success = True
        response.message = f'{name} 重置完成'
        response.reset_time_ms = round(elapsed_ms, 2)

        self.get_logger().info(
            f'{name} 重置成功，耗时 {response.reset_time_ms:.1f} ms'
        )
        return response


def main(args=None):
    rclpy.init(args=args)
    node = SensorResetServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
