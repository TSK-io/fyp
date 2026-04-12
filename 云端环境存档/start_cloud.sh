#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== ☁️ 启动藏红花云端大数据中心 ===${NC}"

echo "[1/3] 重启 MQTT 数据同步引擎..."
sudo systemctl restart mqtt-mysql.service

echo "[2/3] 清理历史遗留看板进程..."
sudo pkill -f cloud_app.py || true
sleep 1

echo "[3/3] 启动云端数字孪生大屏..."
cd ~/cloud_dashboard
nohup sudo ~/myenv/bin/python3 cloud_app.py > dashboard.log 2>&1 &

echo -e "\n${GREEN}🎉 云端服务全部一键启动成功！${NC}"
echo -e "📱 请使用手机流量访问公网看板: ${BLUE}http://104.248.150.11${NC}"
echo -e "🔎 如需查看实时收到的边缘数据，请运行: sudo journalctl -u mqtt-mysql.service -f\n"
