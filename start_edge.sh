#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== 🌱 启动边缘网关与核心控制服务 ===${NC}"

echo "[1/2] 正在清理多余的旧进程..."
sudo systemctl stop edge-publisher.service 2>/dev/null || true

echo "[2/2] 正在重启边缘主程序 (包含采集/控制/MQTT上云)..."
sudo systemctl restart saffron-server.service

# 获取树莓派的局域网 IP
IP_ADDR=$(hostname -I | awk '{print $1}')

echo -e "\n${GREEN}🎉 边缘端服务一键启动成功！${NC}"
echo -e "💻 请在电脑浏览器访问本地控制台: ${BLUE}http://$IP_ADDR:5000${NC}"
echo -e "🔎 如需查看边缘端实时运行日志，请运行: sudo journalctl -u saffron-server.service -f\n"
