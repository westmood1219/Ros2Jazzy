# EmboBot ROS2 Jazzy 调试修复总结

> 作者: CodeWhale AI
> 日期: 2026-06-25
> 仓库: `~/ros2_ws`
> 远程: `Ros2Jazzy` → `git@github.com:felix/Ros2Jazzy.git`

---

## 问题描述

启动 `ros2 launch embobot_gazebo embobot_gz.launch.py` 后存在两个问题：

1. **TF 树不完整** — RViz 中没有任何 TF 连接到 `odom` 帧，`base_footprint` 消失在 TF 树中，报错 "two or more unconnected trees"
2. **激光雷达无数据** — `/scan` 话题在 ROS 侧无声，`ros2 topic echo /scan --once` 无输出

---

## 根本原因及修复过程

### 问题 1：控制器无法加载

**症状**: TF 树显示 `base_link: parent odom`（100Hz），但没有 `base_footprint` 帧

**根因**: 启动文件使用 `ExecuteProcess(cmd=['ros2', 'control', 'load_controller', ...])`，但 ROS2 Jazzy 中**没有安装 `ros2controlcli` 包**，`ros2 control` 命令不存在，控制器加载静默失败。

**修复** (commit `46e59d5`):
- 将 `ExecuteProcess` + `ros2 control` 替换为 `controller_manager` 包的 `spawner` 可执行文件
- `spawner` 通过服务调用与 `ros2_control_node` 通信加载控制器

```python
# 修改前（不工作）
ExecuteProcess(cmd=['ros2', 'control', 'load_controller', '--set-state', 'active', 'diff_drive_controller'])

# 修改后（工作）
Node(package='controller_manager', executable='spawner',
     arguments=['diff_drive_controller', '--controller-manager', '/controller_manager', ...])
```

---

### 问题 2：`base_frame_id` 未被传递给控制器

**症状**: 即使控制器加载成功，TF 仍然是 `odom→base_link` 而非 `odom→base_footprint`

**根因**: 通过 `ros2 param list` 和 `ros2 param get` 发现：
- `controller_manager` 节点中存储了正确的 `diff_drive_controller.base_frame_id = "base_footprint"`
- 但 `/diff_drive_controller` 节点读取的 `base_frame_id = "base_link"`（Jazzy v4.40.1 默认值）

**Jazzy 的 diff_drive_controller 默认值变了**:
```cpp
// /opt/ros/jazzy/include/diff_drive_controller/diff_drive_controller_parameters.hpp:84
std::string base_frame_id = "base_link";  // Humble 中为 "base_footprint"
```

**控制器管理器不会自动将参数转发给子控制器**，必须通过 `spawner` 的 `--param-file` 显式传递。

**修复** (commit `7a1a13b`):
- 创建独立参数文件 `config/diff_drive_params.yaml`，结构为控制器名称作为顶层键

```yaml
diff_drive_controller:
  ros__parameters:
    left_wheel_names: ['left_wheel_joint']
    right_wheel_names: ['right_wheel_joint']
    base_frame_id: base_footprint
    odom_frame_id: odom
    enable_odom_tf: true
    ...
```

- spawner 加载时传入 `--param-file` 参数

---

### 问题 3：激光雷达 sensor 不产生数据

**症状**: `gz topic -i -t /scan` 显示 "No publishers"（Gazebo 端无发布者）

**根因两处**:

#### 3a. 缺少 `gz-sim-sensors-system` 插件

世界文件 `embobot_world.sdf` 未加载 Gazebo Harmonic 的传感器系统插件。在 Gazebo 中，sensor 插件（如 lidar, camera, IMU）需要 `gz-sim-sensors-system` 才能实际产生数据。

**修复** (commit `6363b8b`):
```xml
<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"/>
```

#### 3b. bridge 启动时序问题

`ros_gz_bridge` 的 `parameter_bridge` 在 t=0 启动，但机器人模型到 t=3 才 spawn，lidar sensor 在那时才创建。Gazebo 的 topic subscriber 若在 topic 不存在时订阅，不会在 topic 出现后自动重连。

**修复** (commit `6363b8b`):
- 将 `ros_gz_bridge` 节点放入 `TimerAction(period=4.0)`，在 robot spawn（t=3）之后启动

#### 3c. CPU 版 `lidar` 不工作

将 sensor 从 `gpu_lidar` 切换为 `lidar`（CPU版）后，topic 存在但无数据。切回 `gpu_lidar` 并添加 `<always_on>1</always_on>` 解决问题。

**修复** (commit `7a1a13b`):
```xml
<sensor name="lidar_sensor" type="gpu_lidar">
  <always_on>1</always_on>
  <topic>/scan</topic>
  ...
```

---

### 问题 4：雷达量程不足

**症状**: scan 数据全是 `inf`（空值），RViz 显示 0 个点

**根因**: 世界中的墙壁在 ±5m 处，lidar 量程仅 3.5m，无法探测到任何障碍物。

**修复** (commit `3f5939c`):
```diff
- <max>3.5</max>
+ <max>10.0</max>
```

---

## 最终结果

### TF 树
```
odom (50Hz)
 └── base_footprint (static)
      └── base_link (static)
           ├── left_wheel_link (20Hz)
           ├── right_wheel_link (20Hz)
           ├── lidar_link (static)
           ├── camera_link (static)
           │    └── camera_optical_frame (static)
           └── caster_link (static)
```

### 雷达 scan
```
频率:       ~10 Hz
量程:       0.12 ~ 10.0m
实际读数:   131 个距离值 (~4.9-5.0m) ← 四面墙
自遮挡:     128 个 (0.0，机器人自身)
"""
