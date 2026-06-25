import rclpy
from rclpy.node import Node
from std_srvs.srv import SetBool


class LedControlServer(Node):
    """控制 LED 灯的服务端（用 SetBool 模拟开关）"""

    def __init__(self):
        super().__init__('led_control_server')

        # create_service 的三个参数：
        #   ① 服务类型类
        #   ② 服务名称（客户端用同一名称连接）
        #   ③ 请求处理回调
        self._srv = self.create_service(
            SetBool,
            '/led_control',
            self._handle_led,
        )
        self._led_state = False
        self.get_logger().info('LED 控制服务已就绪：/led_control')

    def _handle_led(self, request: SetBool.Request,
                    response: SetBool.Response) -> SetBool.Response:
        """
        服务回调的固定签名：(self, request, response) -> response
        必须返回填好字段的 response 对象
        """
        self._led_state = request.data
        state_str = '开启' if request.data else '关闭'

        response.success = True
        response.message = f'LED 已{state_str}'

        self.get_logger().info(f'收到请求：LED {state_str}')
        return response  # 不能忘记 return！


def main(args=None):
    rclpy.init(args=args)
    node = LedControlServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
