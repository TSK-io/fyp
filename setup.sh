#!/bin/bash

# ==========================================
# 藏红花培育系统 (Saffron Cultivation System)
# 部署脚本 - 终极一键自启版
# ==========================================

# 定义颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

set -e # 遇到错误立即停止

echo -e "${GREEN}=== 藏红花培育系统 - 智能部署工具 ===${NC}\n"

# 1. 停止后台服务与清理旧进程
echo -e "${YELLOW}[1/5] 停止后台服务与清理旧进程以释放串口...${NC}"
sudo systemctl stop saffron-server.service || true

# === 彻底清理旧的独立发送脚本，防止数据重复上云冲突 ===
sudo systemctl stop edge-publisher.service 2>/dev/null || true
sudo systemctl disable edge-publisher.service 2>/dev/null || true

# 2. 检查连接
echo -e "\n${YELLOW}[2/5] 检查 STM32 连接 (/dev/ttyACM0)...${NC}"
if [ ! -e /dev/ttyACM0 ]; then
    echo -e "${RED}错误: 未找到 /dev/ttyACM0。请检查 STM32 是否连接。${NC}"
    exit 1
fi
echo -e "${GREEN}STM32 连接正常${NC}"

# 3. 同步驱动库
echo -e "\n${YELLOW}[3/5] 同步驱动库 (firmware/lib -> /lib)...${NC}"
# 确保 mpremote 安装
if ! command -v mpremote &> /dev/null; then
    echo -e "${YELLOW}警告: 未找到全局 mpremote，尝试使用虚拟环境中的...${NC}"
    if [ -f ".venv/bin/mpremote" ]; then
        ALIAS_MPREMOTE=".venv/bin/mpremote"
    else
        echo -e "${RED}错误: 未找到 mpremote。请先运行 pip install mpremote${NC}"
        exit 1
    fi
else
    ALIAS_MPREMOTE="mpremote"
fi

$ALIAS_MPREMOTE cp -r firmware/lib/ :
echo -e "${GREEN}驱动库更新完成。${NC}"

# 4. 上传主程序
echo -e "\n${YELLOW}[4/5] 上传主程序 (firmware/main.py -> /main.py)...${NC}"
$ALIAS_MPREMOTE cp firmware/main.py :main.py

echo -e "${YELLOW}正在重置 STM32...${NC}"
$ALIAS_MPREMOTE reset
echo -e "${GREEN}主程序部署完成 (OLED 应已亮起)。${NC}"

# 5. 重建系统服务并设置开机自启
echo -e "\n${YELLOW}[5/5] 正在重建后台服务配置...${NC}"

CURRENT_DIR=$(pwd)
VENV_PYTHON="$CURRENT_DIR/.venv/bin/python"
SERVICE_PATH="/etc/systemd/system/saffron-server.service"

SERVER_FILE=""
POSSIBLE_FILES=("edge-server/app.py" "server.py" "backend/server.py" "src/server.py" "app.py")

for file in "${POSSIBLE_FILES[@]}"; do
    if [ -f "$file" ]; then
        SERVER_FILE="$file"
        break
    fi
done

if [ -z "$SERVER_FILE" ]; then
    echo -e "${YELLOW}   警告: 未检测到标准入口文件名，正在搜索根目录...${NC}"
    SERVER_FILE=$(find . -maxdepth 1 -name "*.py" | grep -v "setup" | head -n 1 | sed 's|./||')
fi

if [ -z "$SERVER_FILE" ]; then
    echo -e "${RED}错误: 无法在 $CURRENT_DIR 找到 Python 服务器入口文件。${NC}"
    exit 1
fi

echo -e "   -> 工作目录: $CURRENT_DIR"
echo -e "   -> Python环境: $VENV_PYTHON"
echo -e "   -> 入口文件: $SERVER_FILE"

SERVICE_CONTENT="[Unit]
Description=Saffron Edge Server Application
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$CURRENT_DIR
Environment=\"PATH=$CURRENT_DIR/.venv/bin:/usr/local/bin:/usr/bin:/bin\"
ExecStart=$VENV_PYTHON $CURRENT_DIR/$SERVER_FILE
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target"

# 写入文件
echo -e "   -> 正在写入 /etc/systemd/system/saffron-server.service ..."
echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_PATH" > /dev/null

# 重载、设为开机自启，并启动
echo -e "   -> 重载守护进程..."
sudo systemctl daemon-reload

# === 新增：这里真正实现了“一键部署”的灵魂，设为开机自启 ===
echo -e "   -> 设置开机自动启动..."
sudo systemctl enable saffron-server.service

echo -e "   -> 启动服务..."
sudo systemctl restart saffron-server.service

# 最终检查
sleep 3
if systemctl is-active --quiet saffron-server.service; then
    echo -e "\n${GREEN}部署成功！后台服务已在运行并设为开机自启。${NC}"
    IP_ADDR=$(hostname -I | cut -d' ' -f1)
    echo -e "请访问: http://$IP_ADDR:5000"
else
    echo -e "\n${RED}服务启动失败。日志如下：${NC}"
    sudo journalctl -u saffron-server.service -n 20 --no-pager
    exit 1
fi
