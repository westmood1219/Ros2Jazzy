#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped
from nav_msgs.msg import Odometry

class TwistStamper(Node):
    def __init__(self):
        super().__init__('twist_stamper')
        # Twist → TwistStamped for Jazzy's diff_drive_controller
        self.sub = self.create_subscription(Twist, '/cmd_vel', self.cb, 10)
        self.pub = self.create_publisher(TwistStamped, '/diff_drive_controller/cmd_vel', 10)
        # /diff_drive_controller/odom → /odom relay
        self.odom_sub = self.create_subscription(Odometry, '/diff_drive_controller/odom', self.odom_cb, 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)

    def cb(self, msg):
        ts = TwistStamped()
        ts.header.stamp = self.get_clock().now().to_msg()
        ts.header.frame_id = 'base_link'
        ts.twist = msg
        self.pub.publish(ts)

    def odom_cb(self, msg):
        self.odom_pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(TwistStamper())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
