# ROS2 Jazzy 调试方法论

> 写给和我一样面对一堆 Topic 的 TF 和 scan 毫无头绪的人

---

## 一、我为什么会往这些方向查

调试的核心思路只有一条：**"确认每一段的物理/信息流是否通，逐段堵漏"**。

在这个 Embobot 例子里，系统链条是：

```
键盘输入 → /cmd_vel (Twist) → twist_stamper → /cmd_vel_stamped →
diff_drive_controller → gz_ros2_control → Gazebo 车轮 → 机器人移动 →
lidar 传感器 → Gazebo /scan → ros_gz_bridge → ROS /scan →
RViz 显示
        + → robot_state_publisher → TF (urdf) → RViz TF 树
        + → joint_state_broadcaster → /joint_states → robot_state_publisher → 动态 TF
        + → diff_drive_controller → /tf (odom→base_footprint)
```

每一段都**可能断**。所以我先看**哪段不通**，再去修那段。

---

## 二、用到的诊断命令

### 2.1 看 TF 树：view_frames

```bash
ros2 run tf2_tools view_frames
```

生成 PDF 文件，直观显示所有 frame 的 parent-child 关系。**第一眼看到的就是两棵独立的树**（odom→base_link 和 base_footprint 不在一起），立刻就知道 TF 断了。

### 2.2 看具体 frame 间变换：tf2_echo

```bash
ros2 run tf2_ros tf2_echo odom base_footprint
```

验证两个指定 frame 之间是否有变换通路。当这边报 "two or more unconnected trees" 时，就知道是 frame 冲突（base_link 有两个父亲）。

### 2.3 看话题发布者和订阅者：topic info

```bash
ros2 topic info /tf -v          # 看到 5 个发布者！判断有冲突
ros2 topic info /odom -v        # 看到 bridge 和 stamper 重复发
ros2 topic info /scan -v        # 看到 bridge 在发但无订阅者
ros2 topic info /cmd_vel -v     # 看到 0 个发布者（遥控消息没发出去）
```

`-v` 参数能列出所有发布者/订阅者的节点名，是排查消息链的核心命令。

### 2.4 看消息内容：topic echo

```bash
ros2 topic echo /scan --once    # 看扫描数据的 frame_id 和 range
ros2 topic echo /odom --once    # 看里程计位置 x,y
ros2 topic echo /joint_states   # 看轮子实际转动了多少
ros2 topic echo /clock --once   # 看仿真时间有没有在走
```

### 2.5 看节点状态：node list / node info

```bash
ros2 node list                  # 看所有节点是否在运行
ros2 node info /diff_drive_controller  # 看订阅/发布了哪些话题、类型
```

### 2.6 看参数：param list / param get

```bash
ros2 param list /controller_manager      # 列出所有参数
ros2 param get /controller_manager diff_drive_controller.base_frame_id
ros2 param get /diff_drive_controller base_frame_id
```

这两条是**整个调试中最关键的两行**，直接对比 controller_manager 里存的参数值和控制器实际使用的参数值，发现它们不一致，定位到了参数转发问题。

### 2.7 看 Gazebo 侧：gz topic

```bash
gz topic -l                     # 列出所有 Gazebo 话题
gz topic -i -t /scan            # 查 /scan 有没有发布者
gz topic -e -t /scan -n 1       # 看一帧扫描数据
gz topic -e -t /world/embobot_world/dynamic_pose/info -n 1  # 看机器人真实位置
```

这是诊断"机器人到底在不在地面上走"的关键。Gazebo 的 pose 信息完全独立于 ROS 的 odom，可以直接看机器人物理引擎里的真实位置。

### 2.8 查参数文件：ros2 param dump

```bash
ros2 param dump /controller_manager       # 导出全部参数
ros2 param describe /controller_manager diff_drive_controller
```

---

## 三、为什么你没有头绪

### 误区 1：把 ROS2 当黑盒

大多数人看到 "TF 树两棵" 或者 "scan 无数据" 就直接搜问题了，而不是按段检查。**
ROS2 不是黑盒**，每一步都有话题/服务/参数可以检查。

### 误区 2：只做表面排查

"scan 无数据" → 第一个直觉是话题名不对 → 改了话题名还是不行 → 放弃。但根源可能是：
- bridge 启动太早 (时序)
- 缺少 sensors 插件 (Gazebo 配置)
- sensor 类型不对 (gpu_lidar vs lidar)
- 量程不足 (walls at 5m, range at 3.5m)

每一层都要**单独确认**。

### 误区 3：不检查物理层

机器人动不了 → 查代码、查控制、查参数 → 搞了半天。
但实际问题是：**机器人 spawn 在 z=0.05（5 厘米高空），轮子根本就没着地**。
这个问题用 `gz topic -e -t /.../dynamic_pose/info` 一眼就能看出来。

### 误区 4：不做对照实验

不改代码去跑 `ros2 service call` / `ros2 topic pub` 来测试单段功能是否正常。例如：
- 发现 `/odom` 没数据 → 是 bridge 没数据还是 controller 没数据？
- 直接用 `ros2 topic echo /diff_drive_controller/odom` 检查 controller 的输出

---

## 四、关于 TwistStamped 的信息来源

没有任何官方文档告诉我 Jazzy 的 diff_drive_controller 强制用 TwistStamped。我是通过以下几个步骤**交叉推断**出来的：

### 步骤 1：怀疑消息类型不匹配

从 `ros2 node info /diff_drive_controller` 看到：

```
Subscribers:
    /diff_drive_controller/cmd_vel: geometry_msgs/msg/TwistStamped
```

而 `teleop_twist_keyboard` 默认发的是 `Twist`（unstamped）。

### 步骤 2：确认 use_stamped_vel 不存在

```bash
ros2 param get /diff_drive_controller use_stamped_vel
# → "Parameter not set"
```

旧版（Humble）中这个参数控制用 Twist 还是 TwistStamped，新版 Jazzy 没有这个参数了。

### 步骤 3：读源码确认

直接看 `/opt/ros/jazzy/include/diff_drive_controller/diff_drive_controller_parameters.hpp`：

```cpp
std::string base_frame_id = "base_link";   // line 84，确认 Jazzy 改了默认值
```

虽然没有直接读到 "TwistStamped only" 的注释，但结合 `use_stamped_vel` 不存在 + 订阅类型是 `TwistStamped`，结论显然。

### 步骤 4：验证

写一个 Python 脚本直接发 `TwistStamped` 到 `/diff_drive_controller/cmd_vel`，确认机器人动了。
再用普通 `Twist` 发到 `/cmd_vel`，机器人不动。
确认 `ros2 topic pub` 可以发出去（之前一直有 daemon 缓存问题，用 `ros2 daemon stop` 解决）。

---

## 五、总结：调试的一般方法论

### 5.1 信息流完整链条

画一条清楚的信息流，从头到尾逐段验证。节点不工作 → `ros2 node list`，话题无数据 → `ros2 topic info -v`，类型不对 → `ros2 interface show`。

### 5.2 区分"问题原因"和"问题表现"

**表现**: 墙壁点云跟随机器人移动。
很多人想到的是："scan 没对齐" → 查 scan → 无果。

**实际原因**: 机器人轮子全程没碰地面，Gazebo 引擎里机器人根本没动过，只是里程计在自嗨。

### 5.3 对照实验

- 怀疑 odom 不对 → 对比 `ros2 topic echo /diff_drive_controller/odom` 和 `gz topic -e -t /world/embobot_world/dynamic_pose/info`
- 怀疑控制器不接收命令 → 直接发 `TwistStamped` 看 odom 变不变
- 怀疑 scan 桥接不对 → 直接 `gz topic -e -t /scan` 看 Gazebo 侧有没有数据

### 5.4 三个逃不开的问题

**问对的问题：**

1. 你确认过哪一段数据流是通的？
2. 你比较过 controller_manager 的配置和实际控制器的参数吗？
3. 你在物理引擎里看过机器人的真实位置吗？

---

## 六、核心命令速查

```bash
# TF
ros2 run tf2_tools view_frames           # 看 TF 树
ros2 run tf2_ros tf2_echo <a> <b>        # 看帧间变换

# 节点
ros2 node list                           # 看所有节点
ros2 node info <node_name>               # 看节点发布/订阅

# 话题
ros2 topic list                          # 看所有话题
ros2 topic info <topic> -v               # 看发布者/订阅者
ros2 topic echo <topic> --once           # 看一帧数据
ros2 topic hz <topic>                    # 看频率
ros2 topic pub <topic> <type> <msg>      # 手动发消息

# 参数
ros2 param list <node>                   # 看参数列表
ros2 param get <node> <param>            # 读参数值
ros2 param dump <node>                   # 导全部参数

# Gazebo
gz topic -l                              # Gazebo 话题列表
gz topic -i -t <topic>                   # Gazebo 话题信息
gz topic -e -t <topic> -n 1              # 看一帧 Gazebo 数据

# 控制器
ros2 service call /controller_manager/list_controllers ...
ros2 service call /controller_manager/list_hardware_interfaces ...
ros2 run controller_manager spawner <name>  # 加载控制器

# 杂项
ros2 daemon stop                         # 清缓存
