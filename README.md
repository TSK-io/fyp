# 项目名称：基于边缘计算的藏红花全生长周期智能培育系统设计与实现

```
智能科技学院2026届本科毕业设计功能实现要求:

1.软硬件系统设计

可设计移动应用系统、基于智能硬件的应用系统、Web应用系统。

具体要求：

（1）能使用所学C/Python等程序设计语言解决相对复杂的综合问题，目标集中，要有较为完整的主体业务逻辑（总体目标）；

（2）要采用合适的分层架构、视图和代码分离（总体架构）；

（3）要考虑系统所需要的用户界面适配显示效果（前端用户接口UI）；

（4）要使用MySQL/SQLServer/Oracle等数据库持久化的功能，其中移动应用系统、Web应用系统 !!!!重点:至少应包含6张业务逻辑关联数据表!!!!，并涉及到存储过程、触发器等技术点的应用（后端存储）；系统页面须实现响应式设计；整个系统须由前端页面和后台管理系统组成，后台管理系统能区分不同角色入口及对应管理权限；

（5）系统应该设计测试用例，通过测试，能反馈系统的稳定性和健壮性（系统测试），说明软/硬件系统核心功能是否达到预期；

（6）以微控制器（单片机51/STM32，推荐型号STM32L431RCT6，不建议使用型号STM32F103C8T6）为核心的智能应用系统，能够采用微控制器编写程序，实现传感器数据采集、设备终端数据显示、存储，系统应!!!!重点:具有联网功能!!!!、数据通讯、网络控制、数据处理等功能，设备终端硬件需个人独立设计（底板可用面包板设计或PCB设计；各功能模块在底板集成基础上开发并实现对应功能），系统设计时应体现不同方案的对比以及如何完成各器件的选型，设计应贴合具体应用场景，避免同质化套壳设计；

（7）以微处理器（ARM）为核心的智能应用系统，采用ARM处理器编写程序，实现传感器数据采集、设备终端数据显示及存储，系统具有!!!!重点:联网功能!!!!、数据通讯、网络控制、数据处理等功能，设备终端硬件需个人独立设计（底板可用面包板设计或PCB设计；各功能模块在底板上集成基础上开发并实现对应功能），系统设计时应体现不同方案的对比以及如何完成各器件的选型；

（8）智能物联网应用系统，针对特定的应用场景，采用物联网技术，将传感器、控制器、智能设备、互联网等多种物联网组件进行有机结合，实现对各种物品、设备、场所、人员的智能化管理和监控，要求选用合理的物联网中间件技术、系统运行安全稳定可靠，要求设备端硬件需个人独立设计（底板可用面包板设计，或PCB设计；各功能模块在底板上集成基础上开发并实现对应功能），系统设计时应体现不同方案的对比以及如何完成各器件的选型。

(9) !!!!重点:三端互通(移动端,云端,硬件端)!!!!

适用专业：计算机科学与技术（1-7）、智能科学与技术（1-8）、物联网工程（1-8）、信息管理与信息系统（1-5）
知网地址:https://co2.cnki.net/Login.html?dp=tfswufe&r=1685087871577
账户为学号例如:42212346
密码例如:let*********3(星号为加密部分)
```

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20STM32-orange.svg)]()

本项目是一个集环境监测、自动化控制、AI 视觉分析与边缘计算于一体的物联网（IoT）解决方案，专为藏红花全生长周期培育设计。系统采用分层架构：**STM32** 负责底层硬件控制与手势识别，**树莓派 (Raspberry Pi 4B 4GB)** 负责边缘计算、Web 服务与 AI 图像处理, Qwen3.5 0.8B自然语言模型。

---

## 安装与部署指南

### 1. 硬件连接
确保 STM32 通过 USB 线连接到树莓派的 USB 口（作为虚拟串口 `/dev/ttyACM0` 供电及通信）。

### 2. 环境准备 (Raspberry Pi)

由于 `picamera2` 深度依赖系统底层库，**强烈建议**在 Raspberry Pi OS (Bookworm 或更高版本) 上按以下步骤操作：

```bash
# 1. 更新系统并安装必要的系统依赖
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv libatlas-base-dev python3-libcamera fish
chsh -s $(which fish)

# 2. 克隆本项目
git clone https://github.com/free514dom/fyp.git
cd fyp

# 3. 创建允许使用系统包的虚拟环境 (关键步骤!)
# 注意：必须使用 --system-site-packages 否则无法加载摄像头驱动
python3 -m venv .venv --system-site-packages

# 4. 激活环境
source .venv/bin/activate.fish

# 5. 安装 Python 依赖
# 注意：如果提示 numpy 版本冲突，请先卸载 pip 安装的 numpy
pip install -r edge-server/requirements.txt
pip uninstall numpy -y  # 强制使用系统自带的稳定版 numpy 以兼容 picamera2
```

### 3. STM32 固件部署
确保 STM32F411 已刷入 MicroPython 固件 (v1.20+)。

```bash
# 使用 setup.sh 脚本自动同步 /firmware/lib 和 main.py 到 STM32
# 该脚本会自动停止后台服务、同步代码并重启 MCU
chmod +x setup.sh
./setup.sh
```

### 4. 启动系统
如果 `setup.sh` 执行成功，它会自动注册并启动 `saffron-server` 系统服务。

*   **手动启动/重启服务**:
    ```bash
    sudo systemctl restart saffron-server.service
    ```
*   **查看运行日志**:
    ```bash
    sudo journalctl -u saffron-server.service -f
    ```

---

## 常见问题排查 (Troubleshooting)

**Q: 报错 `ValueError: numpy.dtype size changed`?**
*   **A:** 这是因为 `pip` 安装的新版 `numpy` (2.x) 与树莓派系统自带的 `picamera2` 不兼容。解决方法：
    ```bash
    source .venv/bin/activate
    pip uninstall numpy -y
    ```
    卸载后，Python 会自动回退使用系统自带的 `numpy` (通常是 1.24.x)，此时即可正常工作。

接线SCL一定要接PB6,SDA一定要接PB7
---
