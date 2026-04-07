# 基于边缘计算的藏红花智能培育系统
# Saffron Intelligent Cultivation System

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
