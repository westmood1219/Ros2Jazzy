import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool


class LedControlClient(Node):
    """LED 控制客户端——演示异步调用的正确模式"""

    def __init__(self):
        super().__init__('led_control_client')

        # create_client 只需两个参数：服务类型和服务名
        self._client = self.create_client(SetBool, '/led_control')

        # 等待服务端上线（最多 5 秒）
        # 这是启动时的一次性等待，可以阻塞
        while not self._client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('等待 /led_control 服务上线...')

        self.get_logger().info('已连接到 /led_control 服务')

    def toggle_led(self, state: bool) -> None:
        """发起异步请求，通过 done_callback 处理结果"""
        request = SetBool.Request()
        request.data = state

        # call_async 立即返回 Future，不阻塞
        future = self._client.call_async(request)

        # 添加完成回调（Future 完成时由事件循环调用）
        future.add_done_callback(self._on_response)

    def _on_response(self, future) -> None:
        """Future 完成时的回调"""
        try:
            response = future.result()
            if response.success:
                self.get_logger().info(f'服务调用成功：{response.message}')
            else:
                self.get_logger().warn(f'服务调用失败：{response.message}')
        except Exception as e:
            self.get_logger().error(f'服务调用异常：{e}')


def main(args=None):
    rclpy.init(args=args)
    node = LedControlClient()

    # 发送两次请求演示
    node.toggle_led(True)   # 开启 LED
    rclpy.spin_once(node, timeout_sec=1.0)   # 等待响应处理

    node.toggle_led(False)  # 关闭 LED
    rclpy.spin_once(node, timeout_sec=1.0)

    node.destroy_node()
    rclpy.shutdown()

