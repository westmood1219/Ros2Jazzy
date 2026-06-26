# EmboBot ROS2 Jazzy 调试修复总结

> 作者: CodeWhale AI
> 日期: 2026-06-25
> 仓库: `~/ros2_ws`
> 远程: `Ros2Jazzy` → `git@github.com:felix/Ros2Jazzy.git`

---

## 问题描述

启动 `ros2 launch embobot_gazebo embobot_gz.launch.py` 后存在多个问题：

1. **TF 树不完整** — RViz 中没有任何 TF 连接到 `odom` 帧，`base_footprint` 消失在 TF 树中
2. **激光雷达无数据** — `/scan` 话题无声，`ros2 topic echo /scan --once` 无输出
3. **机器人无法遥控** — `teleop_twist_keyboard` 按键无反应
4. **扫描点云跟着机器人动** — 激光点云不和墙壁锁定，随着机器人一起移动
5. **里程计（/odom）无声** — `ros2 topic echo /odom --once` 无数据

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
- Jazzy 的 diff_drive_controller v4.40.1 将默认 `base_frame_id` 从 `"base_footprint"` 改为 **`"base_link"`**
- 控制器管理器 **不会自动将参数转发给子控制器**，必须通过 spawner 的 `--param-file` 显式传递

```cpp
// /opt/ros/jazzy/include/diff_drive_controller/diff_drive_controller_parameters.hpp:84
std::string base_frame_id = "base_link";  // Humble 中为 "base_footprint"
```

**修复** (commit `7a1a13b`):
- 创建独立参数文件 `config/diff_drive_params.yaml`，结构为控制器名称作为顶层键
- spawner 加载时传入 `--param-file` 参数

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

#### 3c. 缺少 `<always_on>1</always_on>`

lidar sensor 默认不持续产生数据，加 `<always_on>1</always_on>` 让它无论有无订阅都输出。

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

### 问题 5：Jazzy diff_drive 要求 TwistStamped

**症状**: `/odom` 话题无声、`teleop_twist_keyboard` 遥控无反应

**根因**: ROS2 Jazzy 的 diff_drive_controller **废弃了 `use_stamped_vel` 参数**，强制使用 `geometry_msgs/msg/TwistStamped` 类型的 `cmd_vel`。而 `teleop_twist_keyboard` 默认输出 `geometry_msgs/msg/Twist`（无时间戳）。

此外，`diff_drive_controller` 节点创建在 `/diff_drive_controller` 命名空间下，其发布/订阅的话题都带有此前缀（`/diff_drive_controller/odom`、`/diff_drive_controller/cmd_vel`），而非全局 `/odom` 和 `/cmd_vel`。

**修复** (commit `5c326c5`):
- 创建 `twist_stamper` 转发节点，完成两个功能：
  - `Twist → TwistStamped` 转换（`/cmd_vel → /diff_drive_controller/cmd_vel`）
  - Odom 主题中继（`/diff_drive_controller/odom → /odom`）

```python
class TwistStamper(Node):
    def __init__(self):
        self.set_parameters([Parameter('use_sim_time', Type.BOOL, True)])
        self.pub = create_publisher(TwistStamped, '/diff_drive_controller/cmd_vel')
        self.odom_pub = create_publisher(Odometry, '/odom')
        self.sub = create_subscription(Twist, '/cmd_vel', self.cb)
        self.odom_sub = create_subscription(Odometry, '/diff_drive_controller/odom', self.odom_cb)
```

---

### 问题 6：机器人无法在 Gazebo 中真实移动（最终根因）

**症状**: 里程计显示走了 3.6m（`odom x=3.6`），但 Gazebo 中机器人位置一直是 `x≈0`，扫描距离也始终是 4.9m 不变。遥控机器人时点云跟着一起漂移。

**根因**: **三维几何错误叠加**导致机器人轮子全程悬空打滑：

#### 6a. 初始 spawn 高度过高
```
ros_gz_sim create -z '0.05'  →  机器人离地5cm
```
轮子半径 0.033m，离地 5cm → 全程悬空，轮子空转。

#### 6b. base_link 位置错误导致 body 插地
```
base_footprint_joint: z = wheel_radius = 0.033
base_link cylinder: height=0.070, center at z=0.033
Body bottom: z = 0.033 - 0.035 = -0.002（地下2mm!）
```
车体插入地面 → 物理引擎不断向上推 → 车体抬升 → 轮子离地 → 轮子打滑 → 里程计疯狂累加但车不动。

#### 6c. scan 点云跟着里程计漂移的完整链条
```
robot spawn z=0.05 → 轮子悬空 → 发送 cmd_vel →
只是代码里的轮子关节在转（joint_states: 178rad），
Gazebo 物理引擎里机器人根本没动（pose x≈0）→
scan 数据（来自Gazebo真实位置） vs TF（来自里程计）不一致 →
RViz 按里程计 TF 去显示 scan 点 → 点云位置全错 →
用户遥控时里程计误差不断累积 → 点云跟着一起漂
```

**修复** (commit `ff1944d`):
1. spawn 高度归零：`-z '0.0'`
2. base_link 上移：`base_footprint_joint: z = base_height/2 + wheel_radius`
   - body 底部在 `z = wheel_radius = 0.033`（离地3.3cm）
3. 轮子接头下移：`wheel_joint: z = -base_height/2`
   - 轮子中心在 `z = 0.033`，轮底在 `z = 0.0`（正好地面）

最终几何关系：
```
z=0.103 → base_link cylinder 顶部
z=0.068 → base_link 中心
z=0.033 → body 底部 / 车轮中心
z=0.000 → 地面 / 车轮底部
```

---

### 问题 7：`/joint_states` 桥接冲突

**症状**: 关节状态出现 NaN 或 QoS 丢失警告

**根因**: `ros_gz_bridge` 的 `/joint_states` 桥接和 `joint_state_broadcaster` 同时发布到同一话题，QoS 策略不兼容导致消息丢失。

**修复** (commit `ff1944d`):
- 删除 bridge 配置中的 `/joint_states` 桥接条目，只保留 `joint_state_broadcaster` 作为唯一发布者

---

### 问题 8：运动时 RViz 雷达出现半边 0.3m 假墙

**症状**:
- 键盘按 `i` 前进时，雷达前进方向约 180 度能正常看到远处墙壁，另一半方向显示一面约 `0.3m` 的近墙
- 停车后，近墙方向会反过来
- 按 `<` 后退时，现象再次随车体运动状态翻转
- Gazebo 中机器人位置看起来正常，问题主要体现在 RViz 的 LaserScan 显示

**根因**: 前方万向轮没有真正接地，机器人只靠左右驱动轮形成两点支撑。加速、减速或停车时，车体会绕轮轴前后俯仰，导致水平激光雷达扫描平面向下倾斜，部分光束打到地面。RViz 中这些地面交点被显示成一面约 `0.3m` 的近距离“假墙”。

第一次修复后，前万向轮已经接地，但质心仍接近左右驱动轮轴线，车体在动态运动中偶尔还会俯仰。因此最终采用前后双万向轮支撑，让支撑多边形覆盖车体前后方向。

原几何关系：
```
base_link 高度 = base_height/2 + wheel_radius = 0.035 + 0.033 = 0.068m
旧 caster_joint z = -(base_height/2 - caster_radius) = -0.020m
caster 球心世界高度 = 0.068 - 0.020 = 0.048m
caster 底部高度 = 0.048 - 0.015 = 0.033m
```

也就是说，万向轮底部离地约 `3.3cm`，它没有提供第三个接地点。

**修复**:
将万向轮中心放到世界高度 `caster_radius`，保证球体底部正好接触地面：

```xml
<origin xyz="${caster_x} 0.0 ${caster_radius - (base_height/2 + wheel_radius)}" rpy="0 0 0"/>
```

同时增加后万向轮：

```xml
<origin xyz="${-caster_x} 0.0 ${caster_radius - (base_height/2 + wheel_radius)}" rpy="0 0 0"/>
```

展开后：
```xml
<origin xyz="0.08 0.0 -0.053000000000000005"/>
<origin xyz="-0.08 0.0 -0.053000000000000005"/>
```

最终几何关系：
```
base_link 世界高度 = 0.068m
caster 球心世界高度 = 0.068 - 0.053 = 0.015m
caster 底部世界高度 = 0.015 - 0.015 = 0.000m
前后两个万向轮分别位于 x=0.08m 和 x=-0.08m，减少加减速时的俯仰
```

---

## 最终结果

### TF 树
```
odom (50Hz)
 └── base_footprint
      └── base_link (static)
           ├── left_wheel_link (20Hz)
           ├── right_wheel_link (20Hz)
           ├── lidar_link (static)
           ├── camera_link (static)
           │    └── camera_optical_frame (static)
           └── caster_link (static)
```

### 验证数据
```
ODOM 里程计:          x=0.954
Gazebo 真实位置:      x=0.959   ← 一致！
SCAN 最小值:          0.64m     ← 机器人靠近墙后数据变化
SCAN 最大值:          7.85m     ← 远离另一面墙
```

### 系统架构
```
teleop_twist_keyboard → /cmd_vel (Twist)
                            ↓
                     twist_stamper
                            ↓
              /diff_drive_controller/cmd_vel (TwistStamped)
                            ↓
                   diff_drive_controller
                  ↙                    ↘
    /diff_drive_controller/odom      gz_ros2_control → Gazebo
              ↓
         twist_stamper
              ↓
           /odom
```

---

## 提交历史

```
ff1944d fix: 车体高度修正+轮子位置修正实现Gazebo内真实移动
5c326c5 fix: 添加 TwistStamped 转发 + /odom 桥接
213e5b9 docs: 添加调试修复总结文档
3f5939c fix: lidar range 3.5-10m
7a1a13b fix: 修复 TF odom-base_footprint 链和 lidar scan 数据
6363b8b fix: spawner --param-file + world sensors plugin
1169af2 fix: 设置 base_frame_id, lidar 类型 gpu_lidar->lidar, 恢复 /scan 桥接
46e59d5 fix: 替换 ros2 control load_controller 为 spawner (Jazzy 兼容)
902b28a fix: 修正激光雷达桥接话题名 /lidar -> /scan
2e84be2 chore: initial commit - embobot robot setup
```

---

## 关键要点

1. **Jazzy 变了**：`base_frame_id` 默认值从 `base_footprint` 变成 `base_link`，需显式设置
2. **spawner 传参**：Jazzy 中 `spawner` 必须加 `--param-file` 才会将参数传递给子控制器
3. **TwistStamped**：Jazzy 废弃了 `use_stamped_vel`，强制用 `TwistStamped`
4. **URDF 几何**：`base_footprint_joint` 的 `z` 值决定了机器人所有部件的地面接触，必须精算
5. **Gazebo sensors**：必须加载 `gz-sim-sensors-system` 插件 sensor 才工作
6. **bridge 时序**：`parameter_bridge` 需在 robot spawn 后启动，否则订阅不到 Gazebo topic
7. **假障碍不一定是雷达错**：运动时出现随加减速翻转的近距离“墙”，优先检查车体俯仰、接地点和传感器扫描平面是否打到地面；两轮差速底盘要让支撑点覆盖质心前后方向
