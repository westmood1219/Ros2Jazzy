#!/usr/bin/env python3
"""
EmboBot 速度指令演示节点。
顺序执行：前进 → 原地左转 → 弧线右转 → 停止
验证控制器响应和里程计积分
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class VelocityDemo(Node):
    def __init__(self):
        super().__init__('velocity_demo')

        # 使用和 teleop_twist_keyboard 相同的公共入口。
        # 后续由 launch 中的速度转发节点或控制器配置决定如何接入底盘控制器。
        self._cmd_topic = '/cmd_vel'
        self._pub = self.create_publisher(Twist, self._cmd_topic, 10)
        self._odom_topic = '/odom'
        self._odom_sub = self.create_subscription(
            Odometry, self._odom_topic, self._odom_cb, 10
        )

        self._steps = [
            # (duration_sec, linear_x, angular_z, label)
            (2.0,  0.30,  0.0,  '直线前进  0.30 m/s'),
            (0.5,  0.0,   0.0,  '停止'),
            (3.14, 0.0,   1.0,  '原地左转  1.0 rad/s（半圈）'),
            (0.5,  0.0,   0.0,  '停止'),
            (3.0,  0.30, -0.5,  '弧线右转  R=0.60 m'),
            (0.5,  0.0,   0.0,  '停止'),
            (2.0, -0.20,  0.0,  '直线后退  0.20 m/s'),
            (0.5,  0.0,   0.0,  '停止（完成）'),
        ]
        self._step_idx = 0
        self._step_start = self.get_clock().now()
        self._odom_start = None

        self.create_timer(0.05, self._on_timer)  # 20 Hz
        self.get_logger().info(
            f'速度演示节点启动，发布到 {self._cmd_topic}，监听 {self._odom_topic}'
        )

    def _odom_cb(self, msg: Odometry):
        """里程计回调：记录起始位置"""
        if self._odom_start is None:
            self._odom_start = msg.pose.pose.position
            self.get_logger().info(
                f'起始位置: x={self._odom_start.x:.3f} '
                f'y={self._odom_start.y:.3f}'
            )

    def _on_timer(self):
        if self._step_idx >= len(self._steps):
            return

        duration, vx, wz, label = self._steps[self._step_idx]
        now = self.get_clock().now()
        elapsed = (now - self._step_start).nanoseconds * 1e-9

        # 发布当前步骤的速度指令
        twist = Twist()
        twist.linear.x  = vx
        twist.angular.z = wz
        self._pub.publish(twist)

        # 步骤完成，切换下一步
        if elapsed >= duration:
            self.get_logger().info(
                f'[{self._step_idx+1}/{len(self._steps)}] '
                f'{label}  ({duration:.1f}s 完成)'
            )
            self._step_idx += 1
            self._step_start = now

            # 演示完成：打印里程计总结
            if self._step_idx >= len(self._steps):
                self.get_logger().info('所有动作完成！查看 /odom 验证里程计。')


def main(args=None):
    rclpy.init(args=args)
    node = VelocityDemo()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 确保停止
        stop = Twist()
        node._pub.publish(stop)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
