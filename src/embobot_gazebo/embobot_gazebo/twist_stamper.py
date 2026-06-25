#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped

class TwistStamper(Node):
    def __init__(self):
        super().__init__('twist_stamper')
        self.sub = self.create_subscription(Twist, '/cmd_vel', self.cb, 10)
        self.pub = self.create_publisher(TwistStamped, '/cmd_vel_stamped', 10)

    def cb(self, msg):
        ts = TwistStamped()
        ts.header.stamp = self.get_clock().now().to_msg()
        ts.header.frame_id = 'base_link'
        ts.twist = msg
        self.pub.publish(ts)

def main():
    rclpy.init()
    rclpy.spin(TwistStamper())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
