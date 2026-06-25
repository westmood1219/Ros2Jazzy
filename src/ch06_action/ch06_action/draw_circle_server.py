import math
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from geometry_msgs.msg import Twist
from ch06_interfaces.action import DrawCircle


class DrawCircleServer(Node):
    """让 turtlesim 画圆的 Action Server"""

    def __init__(self):
        super().__init__('draw_circle_server')

        # Action Server 需要 ReentrantCallbackGroup，允许 execute 在独立线程运行
        self._cb_group = ReentrantCallbackGroup()

        self._action_server = ActionServer(
            self,
            DrawCircle,             # Action 类型
            'draw_circle',          # Action 名称
            execute_callback=self._execute,           # 执行回调
            goal_callback=self._goal_callback,        # 接受/拒绝 Goal
            cancel_callback=self._cancel_callback,    # 响应取消请求
            callback_group=self._cb_group,
        )

        self._cmd_pub = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        self.get_logger().info('DrawCircleServer 已就绪，等待 Goal...')

    def _goal_callback(self, goal_request) -> GoalResponse:
        """判断是否接受 Goal，可以在此做参数合法性检查"""
        r = goal_request.radius
        v = goal_request.speed
        if r <= 0 or v <= 0:
            self.get_logger().warn(f'拒绝无效 Goal: radius={r}, speed={v}')
            return GoalResponse.REJECT
        self.get_logger().info(f'接受 Goal: radius={r:.1f}m, speed={v:.1f}m/s')
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle) -> CancelResponse:
        """响应取消请求——这里简单地总是接受取消"""
        self.get_logger().info('收到取消请求，准备停止')
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle) -> DrawCircle.Result:
        """
        核心执行函数：运行在独立线程，可以阻塞。
        周期发布速度指令，同时推送 Feedback，检测取消请求。
        """
        r = goal_handle.request.radius
        v = goal_handle.request.speed
        omega = v / r               # 角速度 = 线速度 / 半径
        period = 0.1                # 控制周期 10 Hz
        total_time = 2 * math.pi * r / v   # 画完整一圈的理论时间
        total_steps = int(total_time / period)

        self.get_logger().info(
            f'开始画圆: r={r:.1f}m, v={v:.1f}m/s, 预计 {total_time:.1f}s'
        )

        feedback = DrawCircle.Feedback()
        result = DrawCircle.Result()
        distance_traveled = 0.0

        for step in range(total_steps):
            # ① 检测取消请求
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                self.get_logger().info(f'已取消，完成 {step}/{total_steps} 步')
                self._stop_turtle()
                result.completed = False
                result.total_distance = distance_traveled
                return result

            # ② 发布速度指令
            cmd = Twist()
            cmd.linear.x = v
            cmd.angular.z = omega
            self._cmd_pub.publish(cmd)

            # ③ 更新并发布 Feedback（每 10 步一次，避免消息洪泛）
            distance_traveled += v * period
            pct = (step + 1) / total_steps * 100
            if step % 10 == 0:
                feedback.percent_complete = round(pct, 1)
                feedback.distance_so_far = round(distance_traveled, 3)
                goal_handle.publish_feedback(feedback)

            time.sleep(period)

        # ④ 任务完成
        self._stop_turtle()
        goal_handle.succeed()
        result.completed = True
        result.total_distance = round(distance_traveled, 3)
        self.get_logger().info(f'画圆完成，总路程 {result.total_distance:.2f}m')
        return result

    def _stop_turtle(self) -> None:
        """停止海龟运动"""
        self._cmd_pub.publish(Twist())


def main(args=None):
    rclpy.init(args=args)
    # MultiThreadedExecutor 让 execute 回调运行在独立线程
    from rclpy.executors import MultiThreadedExecutor
    node = DrawCircleServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
