import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from ch06_interfaces.action import DrawCircle


class DrawCircleClient(Node):
    def __init__(self):
        super().__init__('draw_circle_client')
        self._client = ActionClient(self, DrawCircle, 'draw_circle')
        self._goal_handle = None   # 保存 handle 以便后续取消

    def send_goal(self, radius: float, speed: float) -> None:
        """发送画圆目标——异步，不阻塞"""
        self._client.wait_for_server()

        goal = DrawCircle.Goal()
        goal.radius = radius
        goal.speed = speed

        self.get_logger().info(f'发送 Goal: r={radius:.1f}, v={speed:.1f}')

        send_future = self._client.send_goal_async(
            goal,
            feedback_callback=self._on_feedback,    # 实时进度回调
        )
        send_future.add_done_callback(self._goal_response_cb)

    def _goal_response_cb(self, future) -> None:
        """Goal 被接受/拒绝的回调"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal 被拒绝')
            return

        self.get_logger().info('Goal 已接受，等待执行...')
        self._goal_handle = goal_handle   # 保存供取消用

        # 注册 Result 回调
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._get_result_cb)

    def _on_feedback(self, feedback_msg) -> None:
        """收到 Feedback 时的回调——这里打印进度条"""
        fb = feedback_msg.feedback
        pct = int(fb.percent_complete)
        bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
        self.get_logger().info(
            f'[{bar}] {pct:3d}%  距离: {fb.distance_so_far:.2f}m'
        )

    def _get_result_cb(self, future) -> None:
        """收到最终 Result 的回调"""
        result = future.result().result
        status = future.result().status

        from action_msgs.msg import GoalStatus
        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(
                f'任务成功！总路程: {result.total_distance:.2f}m'
            )
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn(
                f'任务已取消，已行进: {result.total_distance:.2f}m'
            )
        else:
            self.get_logger().error('任务失败或中止')

    def cancel(self) -> None:
        """取消当前正在执行的目标"""
        if self._goal_handle is None:
            self.get_logger().warn('没有正在执行的目标')
            return
        self.get_logger().info('发送取消请求...')
        cancel_future = self._goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(
            lambda f: self.get_logger().info('取消请求已发送')
        )


def main(args=None):
    rclpy.init(args=args)
    node = DrawCircleClient()

    import sys
    radius = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    speed  = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    node.send_goal(radius, speed)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Ctrl+C 时尝试优雅取消
        node.cancel()
        rclpy.spin_once(node, timeout_sec=1.0)
    finally:
        node.destroy_node()
        rclpy.shutdown()
