# Raspberry Pi Headless Setup (Fedora + Fish Shell)

**Target:** Raspberry Pi OS (Bookworm)
**Host:** Fedora
**Shell:** Fish
**Network:** SSID `li` / PSK `11111111`
**User:** `pi` / Password `11`

## 1. 宿主机环境准备 (Prerequisites)

```fish
# 安装 QEMU 静态模拟器 (关键)
sudo dnf install qemu-user-static

# 确认服务运行
sudo systemctl restart systemd-binfmt
```

## 2. 挂载 (Mounting)

```fish
# === 变量设置 ===
set SD_DEV "/dev/sdb"   # <--- 请根据 lsblk 修改这里！
set MNT_DIR "/mnt/pi"

# === 挂载分区 ===
sudo mkdir -p $MNT_DIR
# 挂载 Root 分区 (2)
sudo mount {$SD_DEV}2 $MNT_DIR
# 挂载 Boot 分区 (1)
sudo mount {$SD_DEV}1 $MNT_DIR/boot

# === 挂载内核文件系统 (Fish 语法) ===
for dir in sys proc dev dev/pts
    sudo mount --bind /$dir $MNT_DIR/$dir
end

# === 注入 DNS ===
sudo cp /etc/resolv.conf $MNT_DIR/etc/resolv.conf

echo "✅ 挂载完成"
```

## 3. 网络配置注入 (Network Injection)

```fish
# === 写入 WiFi 配置 ===
# Fish 允许直接使用多行字符串，这比 cat <<EOF 更稳定
echo "[connection]
id=PixelHotspot
uuid=6fad2b0b-98a7-4796-ae19-3bfd30bd3e97
type=wifi
interface-name=wlan0
permissions=

[wifi]
mode=infrastructure
ssid=li

[wifi-security]
key-mgmt=wpa-psk
psk=11111111

[ipv4]
method=auto

[ipv6]
addr-gen-mode=default
method=auto

[proxy]" | sudo tee $MNT_DIR/etc/NetworkManager/system-connections/PixelHotspot.nmconnection > /dev/null

# === 修正权限 (必须为 600) ===
sudo chmod 600 $MNT_DIR/etc/NetworkManager/system-connections/PixelHotspot.nmconnection
sudo chown root:root $MNT_DIR/etc/NetworkManager/system-connections/PixelHotspot.nmconnection

echo "✅ WiFi 配置注入完成 (SSID: li)"
```

## 4. 系统配置 (System Config via Chroot)

**这里包含了你要求的 SSH 启动和密码设置：**

```fish
# 定义配置脚本
set SETUP_SCRIPT '
# 1. 创建用户 pi
id -u pi &>/dev/null || useradd -m -s /bin/bash pi

# 2. 设置密码为 "11"
# chpasswd 可以绕过短密码检查
echo "pi:11" | chpasswd

# 3. 赋予 Sudo 权限
usermod -aG sudo,video,audio,plugdev,games,users,input,render,netdev,gpio,i2c,spi pi
# 配置免密 sudo
echo "pi ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/010_pi-nopasswd
chmod 440 /etc/sudoers.d/010_pi-nopasswd

# 4. 【关键】强制开启 SSH
systemctl enable ssh
# 删除可能存在的"禁止SSH运行"标记文件
rm -f /etc/ssh/sshd_not_to_be_run

# 5. 设置 WiFi 国家代码 (CN)
echo "REGDOMAIN=CN" > /etc/default/crda
'

# === 执行注入 ===
sudo chroot $MNT_DIR /bin/bash -c "$SETUP_SCRIPT"

echo "✅ 用户 pi (密码: 11) 已创建，SSH 已强制开启"
```

## 5. 清理与卸载 (Unmount)

```fish
# 逆序卸载
sudo umount $MNT_DIR/boot
for dir in dev/pts dev sys proc
    sudo umount $MNT_DIR/$dir
end
sudo umount $MNT_DIR

echo "🎉 完成。请拔卡上电。"
```
